import os
import uuid

import pytest

from azsync.azcopy import AZCopy, AZLoginError

from .common import (
    APP_ID,
    TENANT_ID,
    SECRET,
    EXECUTABLE,
    default_login_call,
    PopenMock,
)


@pytest.fixture
def client():
    return AZCopy(tenant_id=TENANT_ID, app_id=APP_ID, secret=SECRET)


def test_login__return_true_on_success(client):
    # autospec enabled to test number of parameters
    with PopenMock.patch(autospec=True) as mock:
        mock.return_value = PopenMock()

        assert not client.is_logged_in()
        client.login()
        assert client.is_logged_in()

        args, kwargs = mock.call_args
        assert args == (
            [
                EXECUTABLE,
                "login",
                f"--tenant-id={TENANT_ID}",
                "--service-principal",
                f"--application-id={APP_ID}",
            ],
        )

        environ = dict(os.environ)
        environ["AZCOPY_SPA_CLIENT_SECRET"] = SECRET

        assert kwargs["env"] == environ
        assert mock.mock_calls == [default_login_call()]


def test_login__raises_on_failure(client):
    with PopenMock.patch() as mock:
        mock.return_value = PopenMock(returncode=1)

        assert not client.is_logged_in()
        with pytest.raises(AZLoginError):
            client.login()
        assert not client.is_logged_in()

        assert mock.mock_calls == [default_login_call()]


def test_login__raises_on_error(client):
    with PopenMock.patch() as mock:
        mock.side_effect = OSError(str(uuid.uuid4()))

        assert not client.is_logged_in()
        with pytest.raises(OSError, match=str(mock.side_effect)):
            client.login()
        assert not client.is_logged_in()

        assert mock.mock_calls == [default_login_call()]


def test_login__custom_exec(client):
    executable = str(uuid.uuid4())
    client.exec = executable

    with PopenMock.patch() as mock:
        mock.return_value = PopenMock()

        assert not client.is_logged_in()
        client.login()
        assert client.is_logged_in()

        args, _kwargs = mock.call_args
        assert args[0][0] == executable

        assert mock.mock_calls == [default_login_call(executable)]


def test_login__only_login_once(client):
    with PopenMock.patch() as mock:
        mock.return_value = PopenMock()

        assert not client.is_logged_in()
        client.login()
        client.login()
        assert client.is_logged_in()

        assert mock.mock_calls == [default_login_call()]
