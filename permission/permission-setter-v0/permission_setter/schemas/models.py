from typing import NamedTuple, Iterable, Sequence

from azure.storage import filedatalake


class AclRecord(NamedTuple):
    tag: str
    qualifier: str
    permissions: str


Acl = Sequence[AclRecord]

PathClient = filedatalake.DataLakeFileClient | filedatalake.DataLakeDirectoryClient
