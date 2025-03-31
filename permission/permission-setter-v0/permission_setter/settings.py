import os
from enum import Enum

from azure.identity import DefaultAzureCredential

DATA_STORAGE_ACCOUNT = os.getenv('DATA_STORAGE_ACCOUNT', "biosustaindls")

APP_CREDENTIALS = DefaultAzureCredential()


class Principals(Enum):
    ckan_data_catalog = '31b1160f-fd35-41a8-ae8f-838a78c1cc1b'
