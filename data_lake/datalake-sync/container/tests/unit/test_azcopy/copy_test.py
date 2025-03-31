import uuid

from unittest.mock import call

import pytest

from azsync.azcopy import AZCopy, AZLoginError, AZUnknownError

from .common import (
    PopenMock,
    default_login_call,
    default_logout_call,
    EXECUTABLE,
    APP_ID,
    TENANT_ID,
    SECRET,
)


@pytest.fixture
def client():
    return AZCopy(tenant_id=TENANT_ID, app_id=APP_ID, secret=SECRET)


def test_copy__logged_in(client):
    with PopenMock.patch() as mock:
        mock.side_effect = [PopenMock()] * 3

        src_file = str(uuid.uuid4())
        dst_url = str(uuid.uuid4())

        with client:
            client.login()
            client.copy(src_file=src_file, dst_url=dst_url)

        assert mock.mock_calls == [
            default_login_call(),
            call([EXECUTABLE, "copy", "--put-md5", src_file, dst_url]),
            default_logout_call(),
        ]


def test_copy__not_logged_in(client):
    with PopenMock.patch() as mock:
        mock.side_effect = [PopenMock()] * 3

        src_file = str(uuid.uuid4())
        dst_url = str(uuid.uuid4())

        with client:
            client.copy(src_file=src_file, dst_url=dst_url)

        assert mock.mock_calls == [
            default_login_call(),
            call([EXECUTABLE, "copy", "--put-md5", src_file, dst_url]),
            default_logout_call(),
        ]


def test_copy__login_failed(client):
    with PopenMock.patch() as mock:
        mock.side_effect = [PopenMock(returncode=1)]

        src_file = str(uuid.uuid4())
        dst_url = str(uuid.uuid4())

        with client:
            with pytest.raises(AZLoginError):
                client.copy(src_file=src_file, dst_url=dst_url)

        assert mock.mock_calls == [
            default_login_call(),
        ]


def test_copy__raises_on_error(client):
    with PopenMock.patch() as mock:
        error = str(uuid.uuid4())
        mock.side_effect = [
            PopenMock(),
            OSError(error),
        ]

        client.login()
        assert client.is_logged_in()
        with pytest.raises(OSError, match=error):
            client.copy("source", "destination")

        assert mock.mock_calls == [
            default_login_call(),
            call([EXECUTABLE, "copy", "--put-md5", "source", "destination"]),
        ]


def test_copy__failure(client):
    with PopenMock.patch() as mock:
        mock.side_effect = [
            PopenMock(),
            PopenMock(returncode=1),
            PopenMock(),
        ]

        src_file = str(uuid.uuid4())
        dst_url = str(uuid.uuid4())

        with client:
            with pytest.raises(AZUnknownError):
                client.copy(src_file=src_file, dst_url=dst_url)

        assert mock.mock_calls == [
            default_login_call(),
            call([EXECUTABLE, "copy", "--put-md5", src_file, dst_url]),
            default_logout_call(),
        ]
