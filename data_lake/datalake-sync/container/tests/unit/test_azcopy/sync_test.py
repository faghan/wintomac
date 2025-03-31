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


def _default_sync_cmd(src_dir, dst_url, rm_dst=False, executable=EXECUTABLE):
    return call(
        [
            executable,
            "sync",
            "--put-md5",
            "--delete-destination",
            "true" if rm_dst else "false",
            src_dir,
            dst_url,
        ]
    )


def test_sync__logged_in(client):
    with PopenMock.patch() as mock:
        mock.side_effect = [PopenMock()] * 3

        src_dir = str(uuid.uuid4())
        dst_url = str(uuid.uuid4())

        with client:
            client.login()
            client.sync(src_dir=src_dir, dst_url=dst_url)

        assert mock.mock_calls == [
            default_login_call(),
            _default_sync_cmd(src_dir, dst_url),
            default_logout_call(),
        ]


def test_sync__not_logged_in(client):
    with PopenMock.patch() as mock:
        mock.side_effect = [PopenMock()] * 3

        src_dir = str(uuid.uuid4())
        dst_url = str(uuid.uuid4())

        with client:
            client.sync(src_dir=src_dir, dst_url=dst_url)

        assert mock.mock_calls == [
            default_login_call(),
            _default_sync_cmd(src_dir, dst_url),
            default_logout_call(),
        ]


def test_sync__without_remove_destination(client):
    with PopenMock.patch() as mock:
        mock.side_effect = [PopenMock()] * 3

        src_dir = str(uuid.uuid4())
        dst_url = str(uuid.uuid4())

        with client:
            client.login()
            client.sync(src_dir=src_dir, dst_url=dst_url, rm_dst=False)

        assert mock.mock_calls == [
            default_login_call(),
            _default_sync_cmd(src_dir, dst_url, rm_dst=False),
            default_logout_call(),
        ]


def test_sync__login_failed(client):
    with PopenMock.patch() as mock:
        mock.side_effect = [PopenMock(returncode=1)]

        src_dir = str(uuid.uuid4())
        dst_url = str(uuid.uuid4())

        with client:
            with pytest.raises(AZLoginError):
                client.sync(src_dir=src_dir, dst_url=dst_url)

        assert mock.mock_calls == [
            default_login_call(),
        ]


def test_sync__raises_on_error(client):
    with PopenMock.patch() as mock:
        error = str(uuid.uuid4())
        mock.side_effect = [
            PopenMock(),
            OSError(error),
        ]

        client.login()
        assert client.is_logged_in()
        with pytest.raises(OSError, match=error):
            client.sync("source", "destination")

        assert mock.mock_calls == [
            default_login_call(),
            _default_sync_cmd("source", "destination"),
        ]


def test_sync__failure(client):
    with PopenMock.patch() as mock:
        mock.side_effect = [
            PopenMock(),
            PopenMock(returncode=1),
            PopenMock(),
        ]

        src_dir = str(uuid.uuid4())
        dst_url = str(uuid.uuid4())

        with client:
            with pytest.raises(AZUnknownError):
                client.sync(src_dir=src_dir, dst_url=dst_url)

        assert mock.mock_calls == [
            default_login_call(),
            _default_sync_cmd(src_dir, dst_url),
            default_logout_call(),
        ]
