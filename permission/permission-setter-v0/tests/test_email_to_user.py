import unittest
from unittest.mock import patch, Mock

import azure.functions as func
from httpx import Response, AsyncClient, Request
from marshmallow import ValidationError

from function_app import user_id_request


class TestGetUserFunction(unittest.IsolatedAsyncioTestCase):
    @patch.object(AsyncClient, "send")
    async def test_get_user_correct_request(self, mock_send: Mock):
        mock_user = dict(
            id="00000000-0000-0000-0000-000000000000",
            mail="test@test.test",
            displayName="Test User",
        )
        mock_send.return_value = Response(
            status_code=200,
            json={
                "@odata.context": "https://graph.microsoft.com/v1.0/$metadata#users(id,mail,displayName)",
                "value": [mock_user],
            },
        )
        # Construct a mock HTTP request.
        req = func.HttpRequest(
            method="GET",
            url="/api/get_user_id",
            params={"email": "test@test.test"},
            body=b"",
        )
        # Call the function.
        func_call = user_id_request.build().get_user_function()
        resp = await func_call(req)
        resp_body = resp.get_body()
        # Check the output.
        mock_send.assert_called_once()
        mock_send.call_args[0][
            0
        ].url = "https://graph.microsoft.com/v1.0/$metadata#users(id,mail,displayName)"
        self.assertEqual(resp_body, mock_user["id"].encode())

    async def test_get_user_incorrect_request_no_email(self):
        # Construct a mock HTTP request.
        req = func.HttpRequest(
            method="GET",
            url="/api/get_user_id",
            params={},
            body=b"",
        )
        # Call the function.
        func_call = user_id_request.build().get_user_function()
        resp = await func_call(req)
        self.assertEqual(resp.status_code, 400)

    async def test_get_user_incorrect_request_too_many_params(self):
        # Construct a mock HTTP request.
        req = func.HttpRequest(
            method="GET",
            url="/api/get_user_id",
            params={"email": "test@test.test", "extra": "extra"},
            body=b"",
        )
        # Call the function.
        func_call = user_id_request.build().get_user_function()
        resp = await func_call(req)
        self.assertEqual(resp.status_code, 400)

    async def test_get_user_incorrect_request_invalid_email(self):
        # Construct a mock HTTP request.
        req = func.HttpRequest(
            method="GET",
            url="/api/get_user_id",
            params={"email": "test@test"},
            body=b"",
        )
        # Call the function.
        func_call = user_id_request.build().get_user_function()
        resp = await func_call(req)
        self.assertEqual(resp.status_code, 400)
