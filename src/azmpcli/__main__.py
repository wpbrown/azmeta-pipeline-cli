import datetime
import itertools
import json
import time
from typing import Any, Collection, Iterable, List

import click
from azure.common.client_factory import get_client_from_cli_profile
from azure.common.credentials import get_azure_cli_credentials, get_cli_profile
from azure.mgmt.billing import BillingManagementClient
from azure.mgmt.billing.models import BillingPeriod
from azure.mgmt.consumption import ConsumptionManagementClient
from azure.storage.blob import BlobServiceClient

from . import _patch  # noqa: F401


def select_billing_period(client: BillingManagementClient) -> BillingPeriod:
    top_billing_periods_paged = client.billing_periods.list(top=5)
    top_billing_periods = itertools.islice(top_billing_periods_paged, 5)

    today = datetime.date.today()
    active_period = next(top_billing_periods)
    while today < (active_period.billing_period_end_date + datetime.timedelta(days=5)):
        active_period = next(top_billing_periods)

    print(
        "Selected billing period: {} ({} - {})".format(
            active_period.name, active_period.billing_period_start_date, active_period.billing_period_end_date
        )
    )
    return active_period


def get_billing_periods(client: BillingManagementClient, names: Iterable[str]) -> List[BillingPeriod]:
    top_billing_periods = {p.name: p for p in client.billing_periods.list(top=36)}

    selected_periods = [top_billing_periods[name] for name in names]

    return selected_periods


def generate_usage_blob_data(
    client: ConsumptionManagementClient, billing_account_name: str, billing_period: str
) -> str:
    download_operation = client.usage_details.download(
        "/providers/Microsoft.Billing/billingAccounts/{}/providers/Microsoft.Billing/"
        "billingPeriods/{}".format(billing_account_name, billing_period),
        metric="amortizedcost",
    )
    while not download_operation.done():
        download_operation.wait(30)
        print("Generate data status: {}".format(download_operation.status()))
    download_result = download_operation.result()
    print("Got URL to blob: {}".format(download_result.download_url))
    return download_result.download_url


def get_billing_accounts(client: BillingManagementClient) -> List[str]:
    service_client = client._client
    url = service_client.format_url("/providers/Microsoft.Billing/billingAccounts")
    query_parameters = {"api-version": "2019-10-01-preview"}
    request = service_client.get(url, query_parameters)
    response = service_client.send(request, stream=False)
    if response.status_code != 200:
        raise Exception("Failed to enumerate billing accounts.")
    raw_accounts = json.loads(response.content)["value"]
    return [
        a["name"]
        for a in raw_accounts
        if a.get("properties", {}).get("agreementType") == "EnterpriseAgreement"
    ]


def get_azure_cli_credentials_non_default_sub(resource: str, subscription: str) -> Any:
    profile = get_cli_profile()
    cred, _, _ = profile.get_login_credentials(resource=resource, subscription_id=subscription)
    return cred


@click.command()
@click.option("-s", "--storage", "storage_account_name", help="Storage account name.", required=True)
@click.option(
    "--storage-subscription",
    "storage_account_subscription",
    help="CLI account subscription to access storage (not required).",
)
@click.option(
    "-a", "--account", "billing_account_name", help="EA billing account number.", show_default="Auto-detect"
)
@click.argument("billing_periods", nargs=-1)
def cli(
    storage_account_name: str,
    billing_account_name: str,
    billing_periods: Collection[str],
    storage_account_subscription: str,
) -> None:
    billing_client = get_client_from_cli_profile(BillingManagementClient)

    if billing_account_name is None:
        accounts = get_billing_accounts(billing_client)
        if len(accounts) == 0:
            print("No Enterprise Agreement account access detected on this user.")
            exit(1)
        elif len(accounts) > 1:
            print(
                "Multiple Enterprise Agreement account access detected on this user.",
                "You must specify the account with --account= .",
            )
            exit(1)
        billing_account_name = accounts[0]

    print("Account Selected:", billing_account_name)

    if len(billing_periods) == 0:
        billing_periods_objects = [select_billing_period(billing_client)]
    else:
        billing_periods_objects = get_billing_periods(billing_client, billing_periods)

    for period in billing_periods_objects:
        export_label = "{}-{}".format(
            period.billing_period_start_date.strftime("%Y%m%d"),
            period.billing_period_end_date.strftime("%Y%m%d"),
        )

        print("Generating usage data (this can take 5 to 10 minutes)...")
        cm_client = get_client_from_cli_profile(ConsumptionManagementClient)
        generated_blob_url = generate_usage_blob_data(cm_client, billing_account_name, period.name)

        blob_account_url = "https://{}.blob.core.windows.net/".format(storage_account_name)
        storage_resource = "https://storage.azure.com/"
        if storage_account_subscription is None:
            credential, _ = get_azure_cli_credentials(resource=storage_resource)
        else:
            credential = get_azure_cli_credentials_non_default_sub(
                resource=storage_resource, subscription=storage_account_subscription
            )
        service = BlobServiceClient(account_url=blob_account_url, credential=credential)
        container = service.get_container_client("usage-final")
        blob = container.get_blob_client("export/finalamortized/{}/manual_load.csv".format(export_label))
        blob.start_copy_from_url(generated_blob_url)
        while True:
            props = blob.get_blob_properties()
            if props.copy is None:
                time.sleep(5)
                continue
            if props.copy.status == "pending":
                print(
                    "Blob is transferring... ",
                    props.copy.status,
                    props.copy.progress,
                    props.copy.status_description,
                )
                time.sleep(10)
                continue

            print(
                "Transfer ended... ",
                props.copy.status,
                props.copy.progress,
                props.copy.status_description if props.copy.status_description else "",
            )
            break

    print("Data load complete.")


if __name__ == "__main__":
    cli()
