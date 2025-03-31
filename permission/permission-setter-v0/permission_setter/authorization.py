import os
from os import PathLike
from typing import List, Dict, Protocol

from permission_setter.schemas.exceptions import Unauthorised, InternalServerError
from permission_setter.schemas.models import Acl, PathClient
from permission_setter.settings import Principals


class AclAuthorizationCheck(Protocol):
    def __call__(
            self,
            *,
            principal_id: str,
            container: str,
            path: PathLike,
            path_client: PathClient,
            acl: Acl
    ) -> bool:
        ...


class NotRoot(AclAuthorizationCheck):
    def __call__(self, *, path: PathLike, **_) -> None:
        if os.path.realpath(path or '/') == '/':
            raise Unauthorised('Not allowed to change ACLs on root path.')


class OnlyOwn(AclAuthorizationCheck):
    def __call__(self, *, path_client: PathClient, principal_id: str, **_) -> None:
        access_control_properties = path_client.get_access_control()
        if access_control_properties['owner'] != principal_id:
            raise Unauthorised('Not allowed to change ACLs on paths not owned by the principal.')


ACL_PRINCIPAL_AUTHORISATION_RULES: Dict[Principals, List[AclAuthorizationCheck]] = {
    Principals.ckan_data_catalog: [
        # ckan_data_catalog can change ACLs on any path within the container (but not the container itself)
        NotRoot()
    ]
}

ACL_OTHERS_AUTHORISATION_RULES: List[AclAuthorizationCheck] = [
    # Others can change ACLs on any path within the container (but not the container itself)
    OnlyOwn()
]


def check_can_change_acl(principal_id: str, **kwargs) -> None:
    try:
        known_principal = Principals(principal_id)
        principal_rules = ACL_PRINCIPAL_AUTHORISATION_RULES[known_principal]
    except (KeyError, ValueError):
        for rule in ACL_OTHERS_AUTHORISATION_RULES:
            rule(principal_id=principal_id, **kwargs)
    else:
        for rule in principal_rules:
            rule(principal_id=principal_id, **kwargs)


