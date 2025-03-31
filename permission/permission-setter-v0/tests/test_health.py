import unittest

import azure.functions as func

from function_app import health_request


class TestHealthFunction(unittest.TestCase):
    def test_get_user_correct_request(self):
        # Construct a mock HTTP request.
        req = func.HttpRequest(
            method="GET",
            url="/api/health",
            body=b"",
        )
        # Call the function.
        func_call = health_request.build().get_user_function()
        resp = func_call(req)
        self.assertEqual(resp.status_code, 200)
