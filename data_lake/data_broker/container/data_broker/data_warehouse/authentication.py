import hashlib

from rest_framework import authentication
from rest_framework import exceptions

from data_broker.common.logging import get_client_ip_logger
from data_broker.data_warehouse.models import BenchlingUser, DataLakeKey

from .logging import log_authentication


class ApiKeyAuthentication(authentication.BaseAuthentication):
    @log_authentication
    def authenticate(self, event, request):
        log = get_client_ip_logger(__name__, request)
        log.debug("attempting api_key based authentication")

        api_key = request.META.get("HTTP_APIKEY", "")
        event.api_key = api_key
        if not api_key:
            _raise_auth_failed(event, log, "no API key")

        hasher = hashlib.sha256()
        hasher.update(api_key.encode("utf-8"))
        api_key = hasher.hexdigest()

        event.username = DataLakeKey.get_username(api_key)
        if event.username is None:
            _raise_auth_failed(event, log, "unknown API key")

        try:
            # FIXME: This seems potentially fragile!
            handle = event.username.split("@", 1)[0]
            user = BenchlingUser.objects.get(handle=handle)
        except BenchlingUser.DoesNotExist:
            _raise_auth_failed(event, log, "unknown user")

        if not user.is_active:
            _raise_auth_failed(event, log, "inactive user")

        log.info("authentication succeeded for %r", user.username)
        return (user, api_key)


def _raise_auth_failed(event, log, message):
    event.response_info = message
    log.warning("authentication failed: %s", message)

    raise exceptions.AuthenticationFailed()
