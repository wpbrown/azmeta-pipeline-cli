#### Monkey Patching Bugs in SDK ####
def _download_initial_monkey(self, scope, metric=None, custom_headers=None, raw=False, **operation_config):
    import uuid # Monkey: import for monkey
    from msrest.pipeline import ClientRawResponse # Monkey: import for monkey
    from azure.mgmt.consumption import models # Monkey: import for monkey

    # Construct URL
    url = self.download.metadata['url']
    path_format_arguments = {
        'scope': self._serialize.url("scope", scope, 'str', skip_quote=True)
    }
    url = self._client.format_url(url, **path_format_arguments)

    # Construct parameters
    query_parameters = {}
    query_parameters['api-version'] = self._serialize.query("self.api_version", self.api_version, 'str')
    if metric is not None:
        query_parameters['metric'] = self._serialize.query("metric", metric, 'str')

    # Construct headers
    header_parameters = {}
    header_parameters['Accept'] = 'application/json'
    if self.config.generate_client_request_id:
        header_parameters['x-ms-client-request-id'] = str(uuid.uuid1())
    if custom_headers:
        header_parameters.update(custom_headers)
    if self.config.accept_language is not None:
        header_parameters['accept-language'] = self._serialize.header("self.config.accept_language", self.config.accept_language, 'str')

    # Construct and send request
    request = self._client.get(url, query_parameters, header_parameters) # Monkey: change POST to GET
    response = self._client.send(request, stream=False, **operation_config)
    response.request.method = 'POST' # Monkey: report that we did a POST

    if response.status_code not in [200, 202]:
        raise models.ErrorResponseException(self._deserialize, response)

    deserialized = None
    header_dict = {}

    if response.status_code == 200:
        deserialized = self._deserialize('UsageDetailsDownloadResponse', response)
        header_dict = {
            'Location': 'str',
            'Retry-After': 'str',
            'Azure-AsyncOperation': 'str',
        }

    if raw:
        client_raw_response = ClientRawResponse(deserialized, response)
        client_raw_response.add_headers(header_dict)
        return client_raw_response

    return deserialized


from azure.mgmt.consumption.operations.usage_details_operations import UsageDetailsOperations
from msrestazure.polling import arm_polling

UsageDetailsOperations._download_initial = _download_initial_monkey # Monkey: apply above function
arm_polling.FINISHED = frozenset(['succeeded', 'canceled', 'failed', 'completed']) # Monkey: detect completed as valid status
arm_polling.SUCCEEDED = frozenset(['succeeded', 'completed']) # Monkey: detect completed as valid status
#### /Monkey Patching Bugs in SDK ####