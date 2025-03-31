import uuid

import pytest

from azsync.azcopy import AZCopy, AZLoginError

from .common import (
    APP_ID,
    TENANT_ID,
    SECRET,
    default_login_call,
    default_logout_call,
    PopenMock,
)


@pytest.fixture
def client():
    return AZCopy(tenant_id=TENANT_ID, app_id=APP_ID, secret=SECRET)


def test_logout__only_if_logged_in(client):
    with PopenMock.patch() as mock:
        assert not client.is_logged_in()
        client.logout()
        assert not client.is_logged_in()

        mock.assert_not_called()


def test_logout__when_logged_in(client):
    with PopenMock.patch() as mock:
        mock.side_effect = [PopenMock(), PopenMock()]

        assert not client.is_logged_in()
        client.login()
        assert client.is_logged_in()
        client.logout()
        assert not client.is_logged_in()

        assert mock.mock_calls == [default_login_call(), default_logout_call()]


def test_logout__not_when_login_failed(client):
    with PopenMock.patch() as mock:
        mock.side_effect = [PopenMock(returncode=1)]

        assert not client.is_logged_in()
        with pytest.raises(AZLoginError):
            client.login()
        assert not client.is_logged_in()
        client.logout()
        assert not client.is_logged_in()

        assert mock.mock_calls == [default_login_call()]


def test_logout__raises_on_error(client):
    with PopenMock.patch() as mock:
        error = str(uuid.uuid4())
        mock.side_effect = [PopenMock(), OSError(error)]

        assert not client.is_logged_in()
        client.login()
        assert client.is_logged_in()
        with pytest.raises(OSError, match=error):
            client.logout()
        assert client.is_logged_in()

        assert mock.mock_calls == [default_login_call(), default_logout_call()]
