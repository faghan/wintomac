import asyncio
import logging
from datetime import datetime
from os import PathLike
from typing import Callable, Coroutine, cast, Any, Dict, Union

from azure.storage.filedatalake import DataLakeServiceClient, AccessControlChangeResult

from permission_setter.authorization import check_can_change_acl
from permission_setter.schemas.exceptions import NotFound
from permission_setter.schemas.models import AclRecord, Acl, PathClient
from permission_setter.schemas.parsers import decode_acl, encode_acl
from permission_setter.schemas.responses import AclChangeRecursiveResponse, AclChangeResponse
from permission_setter.settings import DATA_STORAGE_ACCOUNT, APP_CREDENTIALS
from permission_setter.user import get_user_by_mail, get_user_by_id

# Initialize DataLakeServiceClient
service_client = DataLakeServiceClient(
    account_url=f"https://{DATA_STORAGE_ACCOUNT}.dfs.core.windows.net",
    credential=APP_CREDENTIALS
)


async def map_acl(acl: Acl, map_function: Callable[[AclRecord], Coroutine[Any, Any, AclRecord]]) -> Acl:
    acl = await asyncio.gather(*(map_function(record) for record in acl))
    return cast(Acl, acl)


async def record_acl_email_to_id(record: AclRecord) -> AclRecord:
    if record.qualifier:
        # Initially wrong email was giving warning, however since ACL can be restrictive we cannot simply skip it.
        entity = await get_user_by_mail(record.qualifier)
        return AclRecord(record.tag, entity.id, record.permissions)
    else:
        return record


def email_acl_to_id_acl(email_acl: Acl) -> Coroutine[Any, Any, Acl]:
    return map_acl(email_acl, record_acl_email_to_id)


async def record_acl_id_to_email(record: AclRecord) -> AclRecord:
    if record.qualifier:
        # Initially wrong email was giving warning, however since ACL can be restrictive we cannot simply skip it.
        entity = await get_user_by_id(record.qualifier)
        return AclRecord(record.tag, entity.mail, record.permissions)
    else:
        return record


def id_acl_to_email_acl(id_acl: Acl) -> Coroutine[Any, Any, Acl]:
    return map_acl(id_acl, record_acl_id_to_email)


def get_path_client(container: str, path: PathLike) -> PathClient:
    # Get a reference to the file system
    file_system_client = service_client.get_file_system_client(container)

    # Get a reference to the file
    file_client = file_system_client.get_file_client(str(path))

    if not file_client.exists():
        raise NotFound(f"The {path} does not exist.")

    return file_client


def get_acl(container: str, path: PathLike) -> Coroutine[Any, Any, Acl]:
    # Get a reference to the file system
    path_client = get_path_client(container, path)

    # Get the ACL
    access_control_properties = path_client.get_access_control()

    id_acl = decode_acl(access_control_properties['acl'])

    email_acl = id_acl_to_email_acl(id_acl)

    return email_acl


async def prepare_authorised_client_and_acl_str(principal_id: str, container: str, path: PathLike, acl: Acl) -> (
        PathClient, str):
    # Get a reference to the file system
    path_client = get_path_client(container, path)

    # Translate the ACL
    azure_acl = await email_acl_to_id_acl(acl)

    check_can_change_acl(
        principal_id=principal_id,
        container=container,
        path=path,
        path_client=path_client,
        acl=azure_acl
    )

    # Prepare the ACL string
    acl_str = encode_acl(azure_acl)

    return path_client, acl_str


async def set_acl(principal_id: str, container: str, path: PathLike, acl: Acl) -> Dict[str, Union[str, datetime]]:
    path_client, acl_str = await prepare_authorised_client_and_acl_str(principal_id, container, path, acl)
    result = path_client.set_access_control(acl=acl_str)

    logging.debug("ACL set result: ", AclChangeResponse().dump(result))
    return result


async def set_acl_recursive(principal_id: str, container: str, path: PathLike, acl: Acl) -> AccessControlChangeResult:
    path_client, acl_str = await prepare_authorised_client_and_acl_str(principal_id, container, path, acl)
    result = path_client.set_access_control_recursive(acl=acl_str)

    logging.debug("ACL set recursive result: ", AclChangeRecursiveResponse().dump(result))
    return result


async def update_acl_recursive(principal_id: str, container: str, path: PathLike,
                               acl: Acl) -> AccessControlChangeResult:
    path_client, acl_str = await prepare_authorised_client_and_acl_str(principal_id, container, path, acl)
    result = path_client.update_access_control_recursive(acl=acl_str)

    logging.debug("ACL set recursive result: ", AclChangeRecursiveResponse().dump(result))
    return result
