import uuid


import pytest

from azsync.azcopy import AZCopy

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


def test_with__does_nothing_if_not_logged_in(client):
    with PopenMock.patch() as mock:
        with client:
            assert not client.is_logged_in()

        assert mock.mock_calls == []


def test_with__logs_out_if_logged_in(client):
    with PopenMock.patch() as mock:
        mock.side_effect = [PopenMock(), PopenMock()]

        with client:
            assert not client.is_logged_in()
            client.login()
            assert client.is_logged_in()

        assert not client.is_logged_in()
        assert mock.mock_calls == [default_login_call(), default_logout_call()]


def test_with__raises_on_error(client):
    with PopenMock.patch() as mock:
        error = str(uuid.uuid4())
        mock.side_effect = [PopenMock(), OSError(error)]

        with pytest.raises(OSError, match=error):
            with client:
                assert not client.is_logged_in()
                client.login()

        assert client.is_logged_in()
        assert mock.mock_calls == [default_login_call(), default_logout_call()]
