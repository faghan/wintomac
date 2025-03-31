import uuid
import random


from unittest.mock import call

import pytest

from azsync.azcopy import (
    AZCopy,
    AZError,
    AZLoginError,
    AZUnknownError,
    AZFileNotFoundError,
)
from azsync.fileutils import PartialStats

from .common import (
    PopenMock,
    default_login_call,
    default_logout_call,
    EXECUTABLE,
    APP_ID,
    TENANT_ID,
    SECRET,
)


# Random values for MD5 hash, size, path
def _new_test_file():
    return PartialStats(
        hash=str(uuid.uuid4()).upper(), size=random.randint(0, 2 ** 32 - 1)
    )


def _fmt_test_file(stats):
    return "MD5: %s\t%i\t%s" % (_TEST_FILE.hash, _TEST_FILE.size, uuid.uuid4())


_TEST_FILE = _new_test_file()
_TEST_STDOUT = (
    "Random junk from client",
    _fmt_test_file(_TEST_FILE),
    "More junk from client",
)


@pytest.fixture
def client():
    return AZCopy(tenant_id=TENANT_ID, app_id=APP_ID, secret=SECRET)


def test_get_md5__not_logged_in(client):
    with PopenMock.patch() as mock:
        mock.side_effect = [PopenMock(), PopenMock(stdout=_TEST_STDOUT), PopenMock()]

        dst_url = str(uuid.uuid4())

        with client:
            assert client.get_md5(dst_url=dst_url) == _TEST_FILE

        assert mock.mock_calls == [
            default_login_call(),
            call([EXECUTABLE, "get_md5", dst_url]),
            default_logout_call(),
        ]


def test_get_md5__logged_in(client):
    with PopenMock.patch() as mock:
        mock.side_effect = [PopenMock(), PopenMock(stdout=_TEST_STDOUT), PopenMock()]

        dst_url = str(uuid.uuid4())

        with client:
            client.login()
            assert client.get_md5(dst_url=dst_url) == _TEST_FILE

        assert mock.mock_calls == [
            default_login_call(),
            call([EXECUTABLE, "get_md5", dst_url]),
            default_logout_call(),
        ]


def test_get_md5__login_failed(client):
    with PopenMock.patch() as mock:
        mock.side_effect = [PopenMock(returncode=1)]

        dst_url = str(uuid.uuid4())

        with client:
            with pytest.raises(AZLoginError):
                client.get_md5(dst_url=dst_url)

        assert mock.mock_calls == [
            default_login_call(),
        ]


def test_get_md5__raises_on_error(client):
    with PopenMock.patch() as mock:
        error = str(uuid.uuid4())
        mock.side_effect = [
            PopenMock(),
            OSError(error),
        ]

        client.login()
        assert client.is_logged_in()
        with pytest.raises(OSError, match=error):
            client.get_md5("destination")

        assert mock.mock_calls == [
            default_login_call(),
            call([EXECUTABLE, "get_md5", "destination"]),
        ]


def test_get_md5__failure(client):
    with PopenMock.patch() as mock:
        mock.side_effect = [
            PopenMock(),
            PopenMock(returncode=1, stdout=[""]),
            PopenMock(),
        ]

        dst_url = str(uuid.uuid4())

        with client:
            with pytest.raises(AZUnknownError):
                client.get_md5(dst_url=dst_url)

        assert mock.mock_calls == [
            default_login_call(),
            call([EXECUTABLE, "get_md5", dst_url]),
            default_logout_call(),
        ]


def test_get_md5__file_not_found(client):
    with PopenMock.patch() as mock:
        mock.side_effect = [
            PopenMock(),
            PopenMock(returncode=1, stdout=["X-Ms-Error-Code: [BlobNotFound]"]),
            PopenMock(),
        ]

        dst_url = str(uuid.uuid4())

        with client:
            with pytest.raises(AZFileNotFoundError):
                client.get_md5(dst_url=dst_url)

        assert mock.mock_calls == [
            default_login_call(),
            call([EXECUTABLE, "get_md5", dst_url]),
            default_logout_call(),
        ]


def test_get_md5__no_files(client):
    with PopenMock.patch() as mock:
        mock.side_effect = [PopenMock()] * 3
        dst_url = str(uuid.uuid4())

        with client:
            with pytest.raises(AZError, match="get_md5 returned {}"):
                client.get_md5(dst_url=dst_url)

        assert mock.mock_calls == [
            default_login_call(),
            call([EXECUTABLE, "get_md5", dst_url]),
            default_logout_call(),
        ]


def test_get_md5__too_many_files(client):
    with PopenMock.patch() as mock:
        mock.side_effect = [
            PopenMock(),
            PopenMock(
                stdout=[
                    _fmt_test_file(_new_test_file()),
                    _fmt_test_file(_new_test_file()),
                ],
            ),
            PopenMock(),
        ]

        dst_url = str(uuid.uuid4())

        with client:
            with pytest.raises(AZError, match="get_md5 returned"):
                client.get_md5(dst_url=dst_url)

        assert mock.mock_calls == [
            default_login_call(),
            call([EXECUTABLE, "get_md5", dst_url]),
            default_logout_call(),
        ]
