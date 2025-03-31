from permission_setter.schemas.models import AclRecord, Acl


def decode_acl(acl_str: str) -> Acl:
    return tuple(AclRecord(*record_str.split(':')) for record_str in acl_str.split(','))


def encode_acl(acl: Acl) -> str:
    return ','.join(f"{tag}:{qualifier}:{permissions}" for tag, qualifier, permissions in acl)
