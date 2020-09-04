#### Monkey Patching Bugs in SDK ####
def get_token(self, *scopes, **kwargs):  # pylint:disable=unused-argument
    from azure.core.credentials import AccessToken # Monkey: import for monkey
    import time # Monkey: import for monkey

    _, token, full_token, _ = self._get_token()

    return AccessToken(token, int(full_token['expires_on'] if 'expires_on' in full_token else full_token['expiresIn'] + time.time())) # Monkey: check for expires_on in cloud shell


from azure.cli.core.adal_authentication import AdalAuthentication
AdalAuthentication.get_token = get_token
#### /Monkey Patching Bugs in SDK ####