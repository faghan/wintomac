from unittest.mock import patch, call

import pytest
import subprocess

import azsync.azcopy

from azsync.azcopy import AZCopy

from .common import (
    APP_ID,
    TENANT_ID,
    SECRET,
)


def test_client__invalid_values():
    AZCopy(tenant_id=TENANT_ID, app_id=APP_ID, secret=SECRET)

    with pytest.raises(ValueError):
        AZCopy(tenant_id="", app_id=APP_ID, secret=SECRET)
    with pytest.raises(ValueError):
        AZCopy(tenant_id=None, app_id=APP_ID, secret=SECRET)

    with pytest.raises(ValueError):
        AZCopy(tenant_id=TENANT_ID, app_id="", secret=SECRET)
    with pytest.raises(ValueError):
        AZCopy(tenant_id=TENANT_ID, app_id=None, secret=SECRET)

    with pytest.raises(ValueError):
        AZCopy(tenant_id=TENANT_ID, app_id=APP_ID, secret="")
    with pytest.raises(ValueError):
        AZCopy(tenant_id=TENANT_ID, app_id=APP_ID, secret=None)


@pytest.mark.parametrize("env", [None, object()])
def test_popen__with_without_env(env):
    with patch("subprocess.Popen", autospec=True) as mock:
        mock.return_value = object()

        result = azsync.azcopy._popen(["a", "b", "c"], env=env)

        assert result is mock.return_value
        assert mock.mock_calls == [
            call(
                ["a", "b", "c"],
                stdin=subprocess.DEVNULL,
                stdout=subprocess.PIPE,
                stderr=subprocess.STDOUT,
                env=env,
            )
        ]
