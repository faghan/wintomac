import abc
import unittest
from abc import abstractmethod
from typing import Dict, Any
from unittest.mock import patch, Mock

import azure.functions as func
from azure.functions.decorators.function_app import FunctionBuilder
from azure.storage.filedatalake import DataLakeFileClient
from httpx import Response, AsyncClient
from marshmallow import ValidationError

from function_app import get_acl_request, set_acl_request, set_acl_recursive_request, update_acl_recursive_request
from tests.mocks import MOCK_USER

TEST_PATH = "permission-setter-test"


class TestAclFunctionBase(abc.ABC, unittest.IsolatedAsyncioTestCase):
    __test__ = False

    @property
    @abstractmethod
    def request_base(self) -> Dict[str, Any]:
        ...

    @property
    @abstractmethod
    def func(self) -> FunctionBuilder:
        ...

    async def test_request_no_params(self):
        # Construct a mock HTTP request.
        req = func.HttpRequest(**{
            **self.request_base,
            "params": {},
        })
        # Call the function.
        func_call = self.func.build().get_user_function()
        resp = await func_call(req)
        self.assertEqual(resp.status_code, 400)

    async def test_request_no_container(self):
        # Construct a mock HTTP request.
        req = func.HttpRequest(**{
            **self.request_base,
            "params": {
                k: v for k, v in self.request_base["params"].items() if k != "container"
            },
        })
        # Call the function.
        func_call = self.func.build().get_user_function()
        resp = await func_call(req)
        self.assertEqual(resp.status_code, 400)

    async def test_request_no_path(self):
        # Construct a mock HTTP request.
        req = func.HttpRequest(**{
            **self.request_base,
            "params": {
                k: v for k, v in self.request_base["params"].items() if k != "path"
            },
        })
        # Call the function.
        func_call = self.func.build().get_user_function()
        resp = await func_call(req)
        self.assertEqual(resp.status_code, 400)

    async def test_request_not_existing_path(self):
        # Construct a mock HTTP request.
        req = func.HttpRequest(**{
            **self.request_base,
            "params": {
                **self.request_base["params"],
                "path": "not-existing-path",
            },
        })
        # Call the function.
        func_call = self.func.build().get_user_function()
        resp = await func_call(req)
        self.assertEqual(resp.status_code, 404)

    async def test_request_extra_params(self):
        # Construct a mock HTTP request.
        req = func.HttpRequest(**{
            **self.request_base,
            "params": {
                **self.request_base["params"],
                "extra": "extra",
            },
        })
        # Call the function.
        func_call = self.func.build().get_user_function()
        resp = await func_call(req)
        self.assertEqual(resp.status_code, 400)


class TestGetAclFunction(TestAclFunctionBase):
    __test__ = True
    request_base = dict(
        method="GET",
        url="/api/get_acl",
        body=b"",
        params={"container": "sandbox", "path": TEST_PATH},
    )
    func = get_acl_request

    @patch.object(DataLakeFileClient, "get_access_control")
    @patch.object(AsyncClient, "send")
    async def test_get_acl_request(self, mock_send: Mock, mock_access_control: Mock):
        mock_send.return_value = Response(
            status_code=200,
            json={
                "@odata.context": "https://graph.microsoft.com/v1.0/$metadata#users(id,mail,displayName)",
                "value": [MOCK_USER],
            },
        )
        mock_access_control.return_value = dict(
            acl=f'user:{MOCK_USER["id"]}:rwx,group::r-x,other::---'
        )
        # Construct a mock HTTP request.
        req = func.HttpRequest(**self.request_base)
        # Call the function.
        func_call = self.func.build().get_user_function()
        resp = await func_call(req)
        resp_body = resp.get_body()
        self.assertEqual(resp_body, b'user:test@test.test:rwx,group::r-x,other::---')


class TestChangeAclFunctionBase(TestAclFunctionBase):
    __test__ = False
    request_base: Dict[str, Any]
    func: FunctionBuilder

    async def test_request_no_acl(self):
        # Construct a mock HTTP request.
        req = func.HttpRequest(**{
            **self.request_base,
            "params": {
                k: v for k, v in self.request_base["params"].items() if k != "acl"
            },
        })
        # Call the function.
        func_call = self.func.build().get_user_function()
        resp = await func_call(req)
        self.assertEqual(resp.status_code, 400)

    async def test_request_id_acl(self):
        # Construct a mock HTTP request.
        req = func.HttpRequest(**{
            **self.request_base,
            "params": {
                **self.request_base["params"],
                "acl": f"user:{MOCK_USER['id']}:rwx,group:{MOCK_USER['id']}:r-x,other::---",
            }
        })
        # Call the function.
        func_call = self.func.build().get_user_function()
        resp = await func_call(req)
        self.assertEqual(resp.status_code, 400)


class TestSetAclFunction(TestChangeAclFunctionBase):
    __test__ = True
    request_base = dict(
        method="GET",
        url="/api/set_acl",
        headers={
            "X-MS-CLIENT-PRINCIPAL-ID": MOCK_USER["id"],
        },
        params={"container": "sandbox", "path": TEST_PATH, "acl": 'user::rwx,group::r-x,other::---'},
        body=b"",
    )
    func = set_acl_request

    @patch.object(DataLakeFileClient, "get_access_control")
    @patch.object(AsyncClient, "send")
    async def test_set_acl_request(self, mock_send_user_query: Mock, mock_get_access_control: Mock):  # , mock_send_acl_set: Mock):
        mock_send_user_query.return_value = Response(
            status_code=200,
            json={
                "@odata.context": "https://graph.microsoft.com/v1.0/$metadata#users(id,mail,displayName)",
                "value": [MOCK_USER],
            },
        )
        mock_get_access_control.return_value = {
            'owner': MOCK_USER["id"],
        }
        req = func.HttpRequest(**self.request_base)
        # Call the function.
        func_call = self.func.build().get_user_function()
        resp = await func_call(req)
        resp_body = resp.get_body()
        self.assertEqual(resp.status_code, 200)


class TestSetRecursiveAclFunction(TestChangeAclFunctionBase):
    __test__ = True
    request_base = dict(
        method="GET",
        url="/api/set_acl",
        headers={
            "X-MS-CLIENT-PRINCIPAL-ID": MOCK_USER["id"]
        },
        params={"container": "sandbox", "path": TEST_PATH, "acl": 'user::rwx,group::r-x,other::---'},
        body=b"",
    )
    func = set_acl_recursive_request

    @patch.object(DataLakeFileClient, "get_access_control")
    @patch.object(AsyncClient, "send")
    async def test_set_recursive_acl_request(self, mock_send_user_query: Mock, mock_get_access_control: Mock):
        mock_send_user_query.return_value = Response(
            status_code=200,
            json={
                "@odata.context": "https://graph.microsoft.com/v1.0/$metadata#users(id,mail,displayName)",
                "value": [MOCK_USER],
            },
        )
        mock_get_access_control.return_value = {
            'owner': MOCK_USER["id"],
        }
        # Construct a mock HTTP request.
        req = func.HttpRequest(**self.request_base)
        # Call the function.
        func_call = self.func.build().get_user_function()
        resp = await func_call(req)
        resp_body = resp.get_body()
        self.assertEqual(resp.status_code, 200)


class TestUpdateRecursiveAclFunction(TestChangeAclFunctionBase):
    __test__ = True
    request_base = dict(
        method="GET",
        url="/api/set_acl",
        headers={
            "X-MS-CLIENT-PRINCIPAL-ID": MOCK_USER["id"]
        },
        params={"container": "sandbox", "path": TEST_PATH, "acl": 'user::rwx,group::r-x,other::---'},
        body=b"",
    )
    func = update_acl_recursive_request

    @patch.object(DataLakeFileClient, "get_access_control")
    @patch.object(AsyncClient, "send")
    async def test_update_recursive_acl_request(self, mock_send_user_query: Mock, mock_get_access_control: Mock):
        mock_send_user_query.return_value = Response(
            status_code=200,
            json={
                "@odata.context": "https://graph.microsoft.com/v1.0/$metadata#users(id,mail,displayName)",
                "value": [MOCK_USER],
            },
        )
        mock_get_access_control.return_value = {
            'owner': MOCK_USER["id"],
        }
        # Construct a mock HTTP request.
        req = func.HttpRequest(**self.request_base)
        # Call the function.
        func_call = self.func.build().get_user_function()
        resp = await func_call(req)
        resp_body = resp.get_body()
        self.assertEqual(resp.status_code, 200)
