import json

from django.utils import timezone

from rest_framework import exceptions
from rest_framework import status

from ipware import get_client_ip

from .models import DataBrokerLog


def log_authentication(func):
    def _inner_wrapper(self, request):
        event = DataBrokerLog()
        event.requested_at = timezone.now()
        event.api_endpoint = "login"
        event.arguments = {}
        event.ip_address, _is_routable = get_client_ip(request)
        caught_exception = False

        # Record start-time for api logging below
        request.requested_at = event.requested_at

        try:
            return func(self, event, request)
        except exceptions.APIException as error:
            caught_exception = True
            event.http_response = error.status_code
            if not event.response_info:
                event.response_info = error.default_code
            raise
        except Exception as error:
            caught_exception = True
            event.http_response = status.HTTP_500_INTERNAL_SERVER_ERROR
            event.set_response_info_from_exception(error)
            raise
        finally:
            if caught_exception:
                event.arguments = json.dumps(event.arguments)
                event.response_at = timezone.now()
                event.save()

    return _inner_wrapper


def log_api_endpoint(api_endpoint):
    def _outer_wrapper(func):
        def _inner_wrapper(self, request, **kwargs):
            event = DataBrokerLog()
            event.requested_at = request.requested_at
            event.api_endpoint = api_endpoint
            event.arguments = {}
            event.ip_address, _is_routable = get_client_ip(request)
            event.username = request.user.username
            event.api_key = request.auth

            # User provided arguments
            if request.query_params:
                event.arguments["query"] = request.query_params

            # Arguments from path (filenames), etc.
            if kwargs:
                event.arguments["url"] = kwargs

            try:
                response = func(self, request, **kwargs)
                event.http_response = response.status_code

                return response
            except exceptions.APIException as error:
                event.http_response = error.status_code
                if not event.response_info:
                    event.response_info = error.default_code
                raise
            except Exception as error:
                event.http_response = status.HTTP_500_INTERNAL_SERVER_ERROR
                event.set_response_info_from_exception(error)
                raise
            finally:
                event.arguments = json.dumps(event.arguments)
                event.response_at = timezone.now()
                event.save()

        return _inner_wrapper

    return _outer_wrapper
