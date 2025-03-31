import uuid
import random


from pathlib import Path
from unittest.mock import call

import pytest

from azsync.azcopy import AZCopy, AZLoginError, AZUnknownError
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


_TEST_FILES = (
    # Random values for MD5 hash, size, path
    (uuid.uuid4(), random.randint(0, 2 ** 32 - 1), uuid.uuid4()),
    ("", random.randint(0, 2 ** 32 - 1), uuid.uuid4()),
    (uuid.uuid4(), random.randint(0, 2 ** 32 - 1), uuid.uuid4()),
)

_TEST_STDOUT = (
    "Random junk from client",
    "MD5: %s\t%i\t%s" % _TEST_FILES[0],
    "MD5: %s\t%i\t%s" % _TEST_FILES[1],
    "MD5: %s\t%i\t%s" % _TEST_FILES[2],
    "More junk from client",
)

_TEST_FILES_ALT = ((uuid.uuid4(), random.randint(0, 2 ** 32 - 1), uuid.uuid4()),)

_TEST_STDOUT_ALT = ("MD5: %s\t%i\t%s" % _TEST_FILES_ALT[0],)

_TEST_OUT = {
    Path(str(path)): PartialStats(size=size, hash=str(md5).upper())
    for (md5, size, path) in _TEST_FILES
}


@pytest.fixture
def client():
    return AZCopy(tenant_id=TENANT_ID, app_id=APP_ID, secret=SECRET)


def test_list_md5s__logged_in(client):
    with PopenMock.patch() as mock:
        mock.side_effect = [PopenMock()] * 3

        dst_url = str(uuid.uuid4())

        with client:
            client.login()
            assert client.list_md5s(dst_url=dst_url) == {}

        assert mock.mock_calls == [
            default_login_call(),
            call([EXECUTABLE, "list_md5s", dst_url]),
            default_logout_call(),
        ]


def test_list_md5s__logged_in__with_files(client):
    with PopenMock.patch() as mock:
        mock.side_effect = [PopenMock(), PopenMock(stdout=_TEST_STDOUT), PopenMock()]

        dst_url = str(uuid.uuid4())

        with client:
            client.login()
            assert client.list_md5s(dst_url=dst_url) == _TEST_OUT

        assert mock.mock_calls == [
            default_login_call(),
            call([EXECUTABLE, "list_md5s", dst_url]),
            default_logout_call(),
        ]


def test_list_md5s__not_logged_in(client):
    with PopenMock.patch() as mock:
        mock.side_effect = [PopenMock()] * 3

        dst_url = str(uuid.uuid4())

        with client:
            assert client.list_md5s(dst_url=dst_url) == {}

        assert mock.mock_calls == [
            default_login_call(),
            call([EXECUTABLE, "list_md5s", dst_url]),
            default_logout_call(),
        ]


def test_list_md5s__login_failed(client):
    with PopenMock.patch() as mock:
        mock.side_effect = [PopenMock(returncode=1)]

        dst_url = str(uuid.uuid4())

        with client:
            with pytest.raises(AZLoginError):
                client.list_md5s(dst_url=dst_url)

        assert mock.mock_calls == [
            default_login_call(),
        ]


def test_list_md5s__raises_on_error(client):
    with PopenMock.patch() as mock:
        error = str(uuid.uuid4())
        mock.side_effect = [
            PopenMock(),
            OSError(error),
        ]

        client.login()
        assert client.is_logged_in()
        with pytest.raises(OSError, match=error):
            client.list_md5s("destination")

        assert mock.mock_calls == [
            default_login_call(),
            call([EXECUTABLE, "list_md5s", "destination"]),
        ]


def test_list_md5s__failure(client):
    with PopenMock.patch() as mock:
        mock.side_effect = [
            PopenMock(),
            PopenMock(returncode=1, stdout=_TEST_STDOUT_ALT),
            PopenMock(),
        ]

        dst_url = str(uuid.uuid4())

        with client:
            with pytest.raises(AZUnknownError):
                client.list_md5s(dst_url=dst_url)

        assert mock.mock_calls == [
            default_login_call(),
            call([EXECUTABLE, "list_md5s", dst_url]),
            default_logout_call(),
        ]
