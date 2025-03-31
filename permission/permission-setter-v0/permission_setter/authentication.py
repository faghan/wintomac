from permission_setter.schemas.exceptions import BadRequest


def get_principal_id(headers) -> str:
    if "X-MS-CLIENT-PRINCIPAL-ID" in headers:
        return headers["X-MS-CLIENT-PRINCIPAL-ID"]
    else:
        raise BadRequest("No principal id found in headers - are you running in Authorised Azure function?")
