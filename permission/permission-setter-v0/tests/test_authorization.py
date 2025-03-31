import unittest
from unittest.mock import patch, Mock

import azure.functions as func
from azure.storage.filedatalake import DataLakeFileClient
from httpx import AsyncClient, Response

from function_app import set_acl_request
from permission_setter.schemas.exceptions import Unauthorised
from permission_setter.settings import Principals
from tests.mocks import MOCK_USER, MOCK_OTHER_USER

TEST_PATH = "permission-setter-test"


class TestAclAuthorisationFunction(unittest.IsolatedAsyncioTestCase):
    request_base = dict(
        method="GET",
        url="/api/set_acl",
        body=b"",
    )
    func = set_acl_request

    @patch.object(DataLakeFileClient, "set_access_control")
    @patch.object(AsyncClient, "send")
    async def test_ckan_data_catalog_cannot_set_acl_on_root(self, mock_send: Mock, mock_access_control: Mock):
        # Construct a mock HTTP request.
        req = func.HttpRequest(**{
            **self.request_base,
            'headers': {
                "X-MS-CLIENT-PRINCIPAL-ID": Principals.ckan_data_catalog.value,
            },
            'params': {
                "container": "sandbox", "path": "/", "acl": 'user::rwx,group::r-x,other::---'
            },
        })
        # Call the function.
        func_call = self.func.build().get_user_function()
        resp = await func_call(req)
        self.assertEqual(resp.status_code, 401)
