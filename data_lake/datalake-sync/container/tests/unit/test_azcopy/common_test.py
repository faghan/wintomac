import logging
import uuid

from unittest.mock import call

import pytest

from azsync.azcopy import (
    AZCopy,
    AZError,
    AZLoginError,
    AZNotAuthenticatedError,
    AZFileNotFoundError,
    AZUnknownError,
    _NOT_AUTHENTICATED,
)

from .common import (
    PopenMock,
    default_login_call,
    default_logout_call,
    EXECUTABLE,
    APP_ID,
    TENANT_ID,
    SECRET,
)


_TEST_STDOUT_NOT_LOGGED_IN = [
    "no SAS token or OAuth token is present and the resource is not public\n",
]

_TEST_STDOUT_FILE_NOT_FOUND = [
    "   X-Ms-Error-Code: [BlobNotFound]\n",
]

_TEST_STDOUT_OTHER_ERROR = [
    "   X-Ms-Error-Code: [ThisIsAnError]\n",
]


@pytest.fixture
def client():
    return AZCopy(tenant_id=TENANT_ID, app_id=APP_ID, secret=SECRET)


_ERROR_RESPONSE_TESTS = [
    (AZLoginError, _TEST_STDOUT_NOT_LOGGED_IN),
    (AZFileNotFoundError, _TEST_STDOUT_FILE_NOT_FOUND),
    (AZError, _TEST_STDOUT_OTHER_ERROR),
    (AZUnknownError, []),
]


@pytest.mark.parametrize("exception, stdout", _ERROR_RESPONSE_TESTS)
def test_azcopy__error_responses(client, exception, stdout):
    with PopenMock.patch() as mock:
        mock.side_effect = [
            PopenMock(),
            PopenMock(returncode=1, stdout=stdout),
            PopenMock(),
        ]

        dst_url = str(uuid.uuid4())

        with client:
            client.login()

            with pytest.raises(exception):
                client.list_md5s(dst_url=dst_url)

        assert mock.mock_calls == [
            default_login_call(),
            call([EXECUTABLE, "list_md5s", dst_url]),
            default_logout_call(),
        ]


def _find_in_logs(text, logrecords):
    for record in logrecords:
        if text in record.message:
            return record


_EXPECTED_LOG_LEVELS = (
    (0, "DEBUG"),
    (1, "WARNING"),
)


@pytest.mark.parametrize("returncode, loglevel", _EXPECTED_LOG_LEVELS)
def test_azcopy__logging__unknown_failure(caplog, client, returncode, loglevel):
    value1 = str(uuid.uuid4())
    value2 = str(uuid.uuid4())
    value3 = str(uuid.uuid4())

    with PopenMock.patch() as mock:
        mock.side_effect = [
            PopenMock(),
            PopenMock(stdout=[value1, "\r" + value2, value3], returncode=returncode),
        ]

        client.login()

        with caplog.at_level(logging.DEBUG):
            try:
                client.copy("source", "destination")
            except AZError:
                pass

            assert _find_in_logs(value1, caplog.records).levelname == loglevel
            assert _find_in_logs(value2, caplog.records) is None
            assert _find_in_logs(value3, caplog.records).levelname == loglevel

        assert mock.mock_calls == [
            default_login_call(),
            call([EXECUTABLE, "copy", "--put-md5", "source", "destination"]),
        ]


_ERROR_MSG = [
    "    X-Ms-Error-Code: [BlobNotFound]",
    _NOT_AUTHENTICATED.decode("utf-8"),
]


@pytest.mark.parametrize("errormsg", _ERROR_MSG)
def test_azcopy__logging__known_errors(caplog, client, errormsg):
    value1 = str(uuid.uuid4())
    value2 = str(uuid.uuid4())
    value3 = str(uuid.uuid4())

    with PopenMock.patch() as mock:
        mock.side_effect = [
            PopenMock(),
            PopenMock(stdout=[value1, "\r" + value2, errormsg, value3], returncode=1),
        ]

        client.login()

        with caplog.at_level(logging.DEBUG):
            try:
                client.copy("source", "destination")
            except (AZFileNotFoundError, AZLoginError):
                pass

            assert _find_in_logs(value1, caplog.records).levelname == "DEBUG"
            assert _find_in_logs(value2, caplog.records) is None
            assert _find_in_logs(value3, caplog.records).levelname == "DEBUG"

        assert mock.mock_calls == [
            default_login_call(),
            call([EXECUTABLE, "copy", "--put-md5", "source", "destination"]),
        ]


def test_azcopy__dont_logout_if_not_authenticated(client):
    with PopenMock.patch() as mock:
        mock.side_effect = [
            PopenMock(),
            PopenMock(stdout=[_NOT_AUTHENTICATED.decode("utf-8")], returncode=1,),
            PopenMock(),
        ]

        with pytest.raises(AZNotAuthenticatedError, match="no SAS token or OAuth"):
            with client:
                client.copy("source", "destination")

        assert mock.mock_calls == [
            default_login_call(),
            call([EXECUTABLE, "copy", "--put-md5", "source", "destination"]),
        ]


def test_azcopy__raise_error_during_logout(client):
    with PopenMock.patch() as mock:
        mock.side_effect = [
            PopenMock(),
            PopenMock(),
            PopenMock(returncode=1),
        ]

        with pytest.raises(AZUnknownError):
            with client:
                client.copy("source", "destination")

        assert mock.mock_calls == [
            default_login_call(),
            call([EXECUTABLE, "copy", "--put-md5", "source", "destination"]),
            default_logout_call(),
        ]


def test_azcopy__logout_takes_priority_if_not_loginerror(client):
    with PopenMock.patch() as mock:
        mock.side_effect = [
            PopenMock(),
            PopenMock(stdout=["    X-Ms-Error-Code: [BlobNotFound]"], returncode=1),
            PopenMock(returncode=1),
        ]

        with pytest.raises(AZUnknownError):
            with client:
                client.copy("source", "destination")

        assert mock.mock_calls == [
            default_login_call(),
            call([EXECUTABLE, "copy", "--put-md5", "source", "destination"]),
            default_logout_call(),
        ]
