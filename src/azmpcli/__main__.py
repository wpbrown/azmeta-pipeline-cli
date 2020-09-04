import datetime
import itertools
import json
import uuid
from typing import Any, Collection, Iterable, List

import click
from azure.common.client_factory import get_client_from_cli_profile
from azure.common.credentials import get_cli_profile
from azure.mgmt.billing import BillingManagementClient
from azure.mgmt.billing.models import BillingPeriod

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


def generate_onetime_export(
    client: BillingManagementClient,
    billing_account_name: str,
    billing_period: BillingPeriod,
    storage_account_resource_id: str,
) -> str:
    service_client = client._client
    name = f"onetime{str(uuid.uuid1()).replace('-', '')}"
    url = service_client.format_url(
        "/providers/Microsoft.Billing/billingAccounts/{enrollmentId}"
        "/providers/Microsoft.CostManagement/exports/{name}",
        enrollmentId=billing_account_name,
        name=name,
    )
    query_parameters = {"api-version": "2020-06-01"}
    header_parameters = {"Content-Type": "application/json"}
    content = {
        "properties": {
            "definition": {
                "dataSet": {"granularity": "Daily"},
                "timePeriod": {
                    "from": f"{billing_period.billing_period_start_date.strftime('%Y-%m-%d')}T00:00:00Z",
                    "to": f"{billing_period.billing_period_end_date.strftime('%Y-%m-%d')}T23:59:59Z",
                },
                "timeframe": "Custom",
                "type": "AmortizedCost",
            },
            "deliveryInfo": {
                "destination": {
                    "container": "usage-final",
                    "resourceId": storage_account_resource_id,
                    "rootFolderPath": "export",
                }
            },
            "format": "Csv",
            "schedule": {"status": "Inactive"},
        }
    }
    request = service_client.put(url, query_parameters, header_parameters, content)
    response = service_client.send(request, stream=False)
    if response.status_code != 201:
        raise Exception("Failed to create export.")
    result = json.loads(response.content)
    return result["id"]


def start_onetime_export(client: BillingManagementClient, export_resource_id: str) -> None:
    service_client = client._client
    url = service_client.format_url("/{resourceId}/run", resourceId=export_resource_id)
    query_parameters = {"api-version": "2020-06-01"}
    request = service_client.post(url, query_parameters)
    response = service_client.send(request, stream=False)
    if response.status_code != 200:
        raise Exception("Failed to start export.")


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
@click.option(
    "-s", "--storage", "storage_account_resource_id", help="Storage account resource id.", required=True
)
@click.option(
    "-a", "--account", "billing_account_name", help="EA billing account number.", show_default="Auto-detect"
)
@click.argument("billing_periods", nargs=-1)
def cli(
    storage_account_resource_id: str,
    billing_account_name: str,
    billing_periods: Collection[str],
) -> None:
    billing_client: BillingManagementClient = get_client_from_cli_profile(BillingManagementClient)

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

        print(f"Create onetime export for {export_label}...")
        resource_id = generate_onetime_export(
            billing_client, billing_account_name, period, storage_account_resource_id
        )
        start_onetime_export(billing_client, resource_id)

    print("Queued all exports.")


if __name__ == "__main__":
    cli()
