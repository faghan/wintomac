import os

if os.getenv("PYCHARM_DEBUG"):
    import pydevd_pycharm

    pydevd_pycharm.settrace('localhost', port=12345, stdoutToServer=True, stderrToServer=True)

from http import HTTPStatus
from functools import wraps

from azure.functions import HttpResponse, HttpRequest, FunctionApp
from marshmallow import Schema, fields, validate, ValidationError
from marshmallow.validate import Validator

from msgraph.generated.models.user import User

from permission_setter.authentication import get_principal_id
from permission_setter.schemas.exceptions import ServerError, BadRequest
from permission_setter.schemas.models import Acl
from permission_setter.schemas.parsers import encode_acl, decode_acl
from permission_setter.schemas.responses import AclChangeRecursiveResponse, AclChangeResponse
from permission_setter.storage import get_acl, set_acl, set_acl_recursive, update_acl_recursive
from permission_setter.user import get_user_by_mail

app = FunctionApp()


# region Exception handling
def exception_handler(func):
    @wraps(func)
    def wrapper(*args, **kwargs):
        try:
            return func(*args, **kwargs)
        except ServerError as e:
            return HttpResponse(str(e), status_code=e.status_code)
        except ValidationError as e:
            return HttpResponse(str(e), status_code=400)
        except Exception as e:
            return HttpResponse(str(e), status_code=500)

    return wrapper


def async_exception_handler(func):
    @wraps(func)
    async def wrapper(*args, **kwargs):
        try:
            return await func(*args, **kwargs)
        except ServerError as e:
            return HttpResponse(
                str(e),
                status_code=e.status_code,
                mimetype="text/plain"
            )
        except ValidationError as e:
            return HttpResponse(
                str(e),
                status_code=HTTPStatus.BAD_REQUEST,
                mimetype="application/json"
            )
        except Exception as e:
            return HttpResponse(str(e), status_code=500)

    return wrapper


# endregion


class AzureFunctionParams(Schema):
    # Azure functions uses optional argument "code" to authenticate requests.
    code = fields.Str(required=False)


# region Get user id by email
class EmailToUserRequestParams(AzureFunctionParams):
    email = fields.Email(required=True)


def parse_get_user_id_response(user: User) -> str:
    return user.id


@app.route(route="get_user_id", methods=["GET"], auth_level="anonymous")
@async_exception_handler
async def user_id_request(req: HttpRequest) -> HttpResponse:
    params = EmailToUserRequestParams().load(req.params)
    user = await get_user_by_mail(params['email'])
    resp = parse_get_user_id_response(user)
    return HttpResponse(resp, headers={"Content-Type": "text/plain"})


# endregion


# region Acl
class GetAclParams(AzureFunctionParams):
    container = fields.Str(required=True)
    path = fields.Str(required=True)


async def get_acl_request(req: HttpRequest) -> HttpResponse:
    params = GetAclParams().load(req.params)
    acl = await get_acl(**params)
    resp = encode_acl(acl)
    return HttpResponse(resp, headers={"Content-Type": "text/plain"})


class AclField(fields.Field):
    """Field that serializes to a acl string and deserializes to a acl record list.
    """

    def _serialize(self, value: Acl, attr, obj, **kwargs) -> str:
        return encode_acl(value)

    def _deserialize(self, value: str, attr, data, **kwargs) -> Acl:
        return decode_acl(value)


class EmailAclValidator(Validator):
    email_validator: validate.Email

    def __init__(self):
        self.email_validator = validate.Email(error="Acl qualifier '{input}' is not a valid email.")
        super().__init__()

    def __call__(self, value: Acl) -> Acl:
        for acl_record in value:
            if acl_record.qualifier:
                self.email_validator(acl_record.qualifier)
        return value


class AclChangeRequestParams(GetAclParams):
    acl = AclField(required=True, validate=EmailAclValidator())
    recursive = fields.Bool(required=False, missing=False)


async def set_acl_request(req: HttpRequest) -> HttpResponse:
    principal_id = get_principal_id(req.headers)
    params = AclChangeRequestParams().load(req.params)
    if params.pop('recursive'):
        result = await set_acl_recursive(
            principal_id=principal_id,
            **params
        )
        resp = AclChangeRecursiveResponse().dumps(result)
    else:
        result = await set_acl(
            principal_id=principal_id,
            **params
        )
        resp = AclChangeResponse().dumps(result)
    return HttpResponse(resp, headers={"Content-Type": "application/json"})


class AclUpdateRequestParams(GetAclParams):
    acl = AclField(required=True, validate=EmailAclValidator())
    recursive = fields.Bool(required=False, missing=False,
                            validate=validate.Equal(True))  # Must be true for PATCH requests


async def update_acl_recursive_request(req: HttpRequest) -> HttpResponse:
    principal_id = get_principal_id(req.headers)
    params = AclChangeRequestParams().load(req.params)
    if not params['recursive']:
        raise BadRequest("Recursive parameter must be true for PATCH requests.")
    result = await update_acl_recursive(
        principal_id=principal_id,
        **params
    )
    resp = AclChangeRecursiveResponse().dumps(result)
    return HttpResponse(resp, headers={"Content-Type": "application/json"})


@app.route(route="acl", methods=["GET", "PUT", "PATCH"], auth_level="anonymous")
@async_exception_handler
async def acl_request(req: HttpRequest) -> HttpResponse:
    if req.method == "GET":
        return await get_acl_request(req)
    elif req.method == "PUT":
        return await set_acl_request(req)
    elif req.method == "PATCH":
        return await update_acl_recursive_request(req)
    else:
        raise NotImplementedError(f"Method {req.method} not implemented.")


# endregion


# region Misc
@app.route(route="me", methods=["GET"], auth_level="anonymous")
@exception_handler
def me_request(req: HttpRequest) -> HttpResponse:
    principal_id = get_principal_id(req.headers)
    return HttpResponse(principal_id, headers={"Content-Type": "text/plain"})


@app.route(route="health", methods=["GET"], auth_level="anonymous")
@exception_handler
def health_request(req: HttpRequest) -> HttpResponse:
    return HttpResponse("OK", headers={"Content-Type": "text/plain"})

# endregion
