import unittest

import azure.functions as func

from function_app import me_request

USER_PRINCIPAL = "00000000-0000-0000-0000-000000000000"


class TestMeFunction(unittest.TestCase):
    request_base = dict(
        method="GET",
        headers={
            "x-ms-client-principal-id": USER_PRINCIPAL
        },
        url="/api/me",
        body=b"",
    )
    func = me_request

    def test_get_user_correct_request(self):
        # Construct a mock HTTP request.
        req = func.HttpRequest(**self.request_base)
        # Call the function.
        func_call = self.func.build().get_user_function()
        resp = func_call(req)
        resp_body = resp.get_body()
        self.assertEqual(resp_body, USER_PRINCIPAL.encode())

    def test_get_user_no_header(self):
        # Construct a mock HTTP request.
        req = func.HttpRequest(**{
            **self.request_base,
            'headers': {},
        })
        # Call the function.
        func_call = self.func.build().get_user_function()
        resp = func_call(req)
        self.assertEqual(resp.status_code, 500)
