import multiprocessing
import uuid

from copy import deepcopy
from unittest.mock import create_autospec, call, patch, Mock
from pathlib import Path

import pytest

from azsync.azcopy import AZCopy, AZError, AZFileNotFoundError
from azsync.fileutils import PartialStats
from azsync.sync import (
    execute,
    CheckedCopy,
    CheckedMultiCopy,
    RemoveLocal,
    RemoveRemote,
    CheckedSync,
    Write,
    TRIES,
)
from azsync.utilities import urljoin

from .test_azcopy.common import Untouchable


@pytest.fixture
def client():
    return create_autospec(AZCopy, instance=True)


@pytest.fixture
def source():
    return str(uuid.uuid4())


@pytest.fixture
def destination():
    return str(uuid.uuid4())


class ListMD5sWrapper:
    def __init__(self, out_values):
        self._out_iter = iter(out_values)

    def __call__(self, dst_url):
        return next(self._out_iter)


def mock_list_md5s(*args):
    out_values = []
    for values in args:
        if not isinstance(values, list):
            values = [values]

        for value in values:
            if isinstance(value, dict):
                for path, stats in value.items():
                    if not isinstance(path, Path):
                        raise ValueError(path)
                    elif not isinstance(stats, (PartialStats, Untouchable)):
                        raise ValueError(stats)

                out_values.append(deepcopy(value))
            else:
                raise ValueError(value)

    return Mock(wraps=ListMD5sWrapper(out_values))


def test_mock_list_md5s():
    with pytest.raises(ValueError, match="12345"):
        mock_list_md5s(12345)

    with pytest.raises(ValueError, match="12345"):
        mock_list_md5s([12345])

    with pytest.raises(ValueError, match=str(123556)):
        mock_list_md5s({123556: Untouchable()})

    with pytest.raises(ValueError, match=str(123556)):
        mock_list_md5s({Path("foo"): 123556})

    mock_list_md5s({Path("foo"): Untouchable()})
    mock_list_md5s({Path("foo"): PartialStats()})


def test_untouchable__str():
    obj = Untouchable()

    with pytest.raises(NotImplementedError, match="Untouchable.__str__"):
        str(obj)


def test_untouchable__repr():
    obj = Untouchable()

    with pytest.raises(NotImplementedError, match="Untouchable.__repr__"):
        repr(obj)


def test_untouchable__eq():
    obj = Untouchable()

    with pytest.raises(NotImplementedError, match="Untouchable.__eq__"):
        obj == obj

    with pytest.raises(NotImplementedError, match="Untouchable.__eq__"):
        obj == [None]


def test_untouchable__setattr():
    obj = Untouchable()

    with pytest.raises(NotImplementedError, match="Untouchable.__setattr__"):
        obj.foo = 1


#############################################################################
# CheckedSync


def test_checked_sync__repr_1(source, destination):
    sync = CheckedSync(source, destination)

    assert repr(sync) == f"CheckedSync({source!r}, {destination!r}, False, 600)"


def test_checked_sync__repr_2(source, destination):
    sync = CheckedSync(source, destination, rm_dst=True)

    assert repr(sync) == f"CheckedSync({source!r}, {destination!r}, True, 600)"


def test_checked_sync__repr_3(source, destination):
    sync = CheckedSync(source, destination, timeout=7913)

    assert repr(sync) == f"CheckedSync({source!r}, {destination!r}, False, 7913)"


def test_checked_sync__execute__no_tries_left(client, source, destination):
    sync = CheckedSync(source, destination, timeout=7913)

    assert sync.execute(client, tries=0) == 0
    assert client.mock_calls == []


def test_checked_sync__terminates_if_sync_fails(client, source, destination):
    client.sync.side_effect = AZError("xyz")

    sync = CheckedSync(source, destination)
    with pytest.raises(AZError, match="xyz"):
        sync.execute(client)

    assert client.mock_calls == [call.sync(source, destination, rm_dst=False)]


def test_checked_sync__terminates_if_collect_md5s_fails(client, source, destination):
    with patch("azsync.sync.collect_md5_hashes", autospec=True) as mock:
        # Attaching the mock ensures that it shows up in 'mock_calls'
        client.attach_mock(mock, "collect_md5_hashes__")
        mock.side_effect = multiprocessing.TimeoutError()

        sync = CheckedSync(source, destination)
        assert sync.execute(client) <= 0
        assert client.mock_calls == [
            call.sync(source, destination, rm_dst=False),
            call.collect_md5_hashes__(source, cache={}, timeout=10 * 60),
        ]


def test_checked_sync__no_files__terminates_if_collect_md5s_fails(
    client, source, destination
):
    with patch("azsync.sync.collect_md5_hashes", autospec=True) as mock:
        # Attaching the mock ensures that it shows up in 'mock_calls'
        client.attach_mock(mock, "collect_md5_hashes__")

        mock.return_value = {}
        client.list_md5s.side_effect = AZError("xyz")

        sync = CheckedSync(source, destination)
        with pytest.raises(AZError, match="xyz"):
            sync.execute(client)

        assert client.mock_calls == [
            call.sync(source, destination, rm_dst=False),
            call.collect_md5_hashes__(source, cache={}, timeout=10 * 60),
            call.list_md5s(dst_url=destination),
        ]


def test_checked_sync__no_files__all_ok(client, source, destination):
    with patch("azsync.sync.collect_md5_hashes", autospec=True) as mock:
        # Attaching the mock ensures that it shows up in 'mock_calls'
        client.attach_mock(mock, "collect_md5_hashes__")

        mock.return_value = {}
        client.list_md5s.return_value = {}

        sync = CheckedSync(source, destination)
        assert sync.execute(client) == TRIES
        assert client.mock_calls == [
            call.sync(source, destination, rm_dst=False),
            call.collect_md5_hashes__(source, cache={}, timeout=10 * 60),
            call.list_md5s(dst_url=destination),
        ]


def test_checked_sync__matching_files(client, source, destination):
    local_files = {
        (Path(source) / "foo/bar"): PartialStats(hash="1234", size=1234),
        (Path(source) / "zod"): PartialStats(hash="4321", size=17),
    }

    remote_files = [
        {
            Path("foo/bar"): PartialStats(hash="1234", size=1234),
            Path("zod"): PartialStats(hash="4321", size=17),
        }
    ]

    with patch("azsync.sync.collect_md5_hashes", autospec=True) as mock:
        # Attaching the mock ensures that it shows up in 'mock_calls'
        client.attach_mock(mock, "collect_md5_hashes__")

        mock.return_value = dict(local_files)
        client.list_md5s = mock_list_md5s(remote_files)

        sync = CheckedSync(source, destination)
        assert sync.execute(client) == TRIES
        assert client.mock_calls == [
            call.sync(source, destination, rm_dst=False),
            call.collect_md5_hashes__(source, cache={}, timeout=10 * 60),
            call.list_md5s(dst_url=destination),
        ]


def test_checked_sync__local_has_extra_files(client, source, destination):
    local_files = {
        (Path(source) / "foo/bar"): PartialStats(hash="1234", size=1234),
        (Path(source) / "zod"): PartialStats(hash="4321", size=17),
    }

    remote_files = [
        {
            Path("zod"): PartialStats(hash="4321", size=17),
        },
        {
            Path("foo/bar"): PartialStats(hash="1234", size=1234),
            Path("zod"): PartialStats(hash="4321", size=17),
        },
    ]

    with patch("azsync.sync.collect_md5_hashes", autospec=True) as mock:
        # Attaching the mock ensures that it shows up in 'mock_calls'
        client.attach_mock(mock, "collect_md5_hashes__")

        mock.return_value = dict(local_files)
        client.list_md5s = mock_list_md5s(remote_files)

        sync = CheckedSync(source, destination)
        assert sync.execute(client) == TRIES - 1
        assert client.mock_calls == [
            call.sync(source, destination, rm_dst=False),
            call.collect_md5_hashes__(source, cache={}, timeout=10 * 60),
            call.list_md5s(dst_url=destination),
            call.sync(source, destination, rm_dst=False),
            call.collect_md5_hashes__(source, cache=dict(local_files), timeout=10 * 60),
            call.list_md5s(dst_url=destination),
        ]


def test_checked_sync__remote_has_extra_files__rm_dst(client, source, destination):
    local_files = {
        (Path(source) / "zod"): PartialStats(hash="4321", size=17),
    }

    remote_files = [
        {
            Path("foo/bar"): PartialStats(hash="1234", size=1234),
            Path("zod"): PartialStats(hash="4321", size=17),
        },
        {
            Path("zod"): PartialStats(hash="4321", size=17),
        },
    ]

    with patch("azsync.sync.collect_md5_hashes", autospec=True) as mock:
        # Attaching the mock ensures that it shows up in 'mock_calls'
        client.attach_mock(mock, "collect_md5_hashes__")

        mock.return_value = dict(local_files)
        client.list_md5s = mock_list_md5s(remote_files)

        sync = CheckedSync(source, destination, rm_dst=True)
        assert sync.execute(client) == TRIES - 1
        assert client.mock_calls == [
            call.sync(source, destination, rm_dst=True),
            call.collect_md5_hashes__(source, cache={}, timeout=10 * 60),
            call.list_md5s(dst_url=destination),
            call.sync(source, destination, rm_dst=True),
            call.collect_md5_hashes__(source, cache=dict(local_files), timeout=10 * 60),
            call.list_md5s(dst_url=destination),
        ]


def test_checked_sync__remote_has_extra_files__no_rm_dst(client, source, destination):
    local_files = {
        (Path(source) / "zod"): PartialStats(hash="4321", size=17),
    }

    remote_files = {
        Path("foo/bar"): PartialStats(hash="1234", size=1234),
        Path("zod"): PartialStats(hash="4321", size=17),
    }

    with patch("azsync.sync.collect_md5_hashes", autospec=True) as mock:
        # Attaching the mock ensures that it shows up in 'mock_calls'
        client.attach_mock(mock, "collect_md5_hashes__")

        mock.return_value = dict(local_files)
        client.list_md5s = mock_list_md5s(remote_files, remote_files)

        sync = CheckedSync(source, destination, rm_dst=False)
        assert sync.execute(client) == TRIES
        assert client.mock_calls == [
            call.sync(source, destination, rm_dst=False),
            call.collect_md5_hashes__(source, cache={}, timeout=10 * 60),
            call.list_md5s(dst_url=destination),
        ]


def test_checked_sync__mismatching_file_size_on_remote(client, source, destination):
    local_files = {
        (Path(source) / "foo/bar"): PartialStats(hash="1234", size=1234),
        (Path(source) / "zod"): PartialStats(hash="4321", size=18),
    }

    remote_files = [
        {
            Path("foo/bar"): PartialStats(hash="1234", size=1234),
            Path("zod"): PartialStats(hash="4321", size=17),
        },
        {
            Path("foo/bar"): PartialStats(hash="1234", size=1234),
            Path("zod"): PartialStats(hash="4321", size=18),
        },
    ]

    with patch("azsync.sync.collect_md5_hashes", autospec=True) as mock:
        # Attaching the mock ensures that it shows up in 'mock_calls'
        client.attach_mock(mock, "collect_md5_hashes__")

        mock.return_value = dict(local_files)
        client.list_md5s = mock_list_md5s(remote_files)

        sync = CheckedSync(source, destination, rm_dst=False)
        assert sync.execute(client) == TRIES - 1
        assert client.mock_calls == [
            call.sync(source, destination, rm_dst=False),
            call.collect_md5_hashes__(source, cache={}, timeout=10 * 60),
            call.list_md5s(dst_url=destination),
            call.remove(dst_url=urljoin(destination, "zod")),
            call.sync(source, destination, rm_dst=False),
            call.collect_md5_hashes__(source, cache=dict(local_files), timeout=10 * 60),
            call.list_md5s(dst_url=destination),
        ]


def test_checked_sync__mismatching_file_hash_on_remote(client, source, destination):
    local_files = {
        (Path(source) / "foo/bar"): PartialStats(hash="123x", size=1234),
        (Path(source) / "zod"): PartialStats(hash="4321", size=17),
    }

    remote_files = [
        {
            Path("foo/bar"): PartialStats(hash="1234", size=1234),
            Path("zod"): PartialStats(hash="4321", size=17),
        },
        {
            Path("foo/bar"): PartialStats(hash="123x", size=1234),
            Path("zod"): PartialStats(hash="4321", size=17),
        },
    ]

    with patch("azsync.sync.collect_md5_hashes", autospec=True) as mock:
        # Attaching the mock ensures that it shows up in 'mock_calls'
        client.attach_mock(mock, "collect_md5_hashes__")

        mock.return_value = dict(local_files)
        client.list_md5s = mock_list_md5s(remote_files)

        sync = CheckedSync(source, destination, rm_dst=False)
        assert sync.execute(client) == TRIES - 1
        assert client.mock_calls == [
            call.sync(source, destination, rm_dst=False),
            call.collect_md5_hashes__(source, cache={}, timeout=10 * 60),
            call.list_md5s(dst_url=destination),
            call.remove(dst_url=urljoin(destination, "foo/bar")),
            call.sync(source, destination, rm_dst=False),
            call.collect_md5_hashes__(source, cache=dict(local_files), timeout=10 * 60),
            call.list_md5s(dst_url=destination),
        ]


def test_checked_sync__mismatching_file_hash_on_remote__remove_fails(
    client, source, destination
):
    local_files = {(Path(source) / "zod"): PartialStats(hash="432x", size=17)}
    remote_files = {Path("zod"): PartialStats(hash="4321", size=17)}

    with patch("azsync.sync.collect_md5_hashes", autospec=True) as mock:
        # Attaching the mock ensures that it shows up in 'mock_calls'
        client.attach_mock(mock, "collect_md5_hashes__")

        client.remove.side_effect = AZError("xyz")
        mock.return_value = dict(local_files)
        client.list_md5s = mock_list_md5s(remote_files)

        sync = CheckedSync(source, destination, rm_dst=False)
        with pytest.raises(AZError, match="xyz"):
            sync.execute(client)

        assert client.mock_calls == [
            call.sync(source, destination, rm_dst=False),
            call.collect_md5_hashes__(source, cache={}, timeout=10 * 60),
            call.list_md5s(dst_url=destination),
            call.remove(dst_url=urljoin(destination, "zod")),
        ]


def test_checked_sync__remove_escapes_filenames(client, source, destination):
    local_files = {(Path(source) / "foo/bar?"): PartialStats(hash="1234", size=1234)}

    remote_files = [
        {Path("foo/bar?"): PartialStats(hash="1234", size=4321)},
        {Path("foo/bar?"): PartialStats(hash="1234", size=1234)},
    ]

    with patch("azsync.sync.collect_md5_hashes", autospec=True) as mock:
        # Attaching the mock ensures that it shows up in 'mock_calls'
        client.attach_mock(mock, "collect_md5_hashes__")

        mock.return_value = dict(local_files)
        client.list_md5s = mock_list_md5s(remote_files)

        sync = CheckedSync(source, destination, rm_dst=False)
        assert sync.execute(client) == TRIES - 1
        assert client.mock_calls == [
            call.sync(source, destination, rm_dst=False),
            call.collect_md5_hashes__(source, cache={}, timeout=10 * 60),
            call.list_md5s(dst_url=destination),
            call.remove(dst_url=urljoin(destination, "foo/bar%3F")),
            call.sync(source, destination, rm_dst=False),
            call.collect_md5_hashes__(source, cache=dict(local_files), timeout=10 * 60),
            call.list_md5s(dst_url=destination),
        ]


#############################################################################
# CheckedCopy


def test_checked_copy__repr_1(source, destination):
    copy = CheckedCopy(source, destination)

    assert repr(copy) == f"CheckedCopy({source!r}, {destination!r}, 600)"


def test_checked_copy__repr_2(source, destination):
    copy = CheckedCopy(source, destination, timeout=7913)

    assert repr(copy) == f"CheckedCopy({source!r}, {destination!r}, 7913)"


def test_checked_copy__execute__no_tries_left(client, source, destination):
    copy = CheckedCopy(source, destination)

    with patch("azsync.sync.collect_md5_hashes", autospec=True) as mock:
        # Attaching the mock ensures that it shows up in 'mock_calls'
        client.attach_mock(mock, "collect_md5_hashes__")

        assert copy.execute(client, tries=0) == 0
        assert client.mock_calls == []


def test_checked_copy__terminates_if_collect_md5s_fails_1(client, source, destination):
    with patch("azsync.sync.collect_md5_hashes", autospec=True) as mock:
        # Attaching the mock ensures that it shows up in 'mock_calls'
        client.attach_mock(mock, "collect_md5_hashes__")
        mock.side_effect = multiprocessing.TimeoutError()

        copy = CheckedCopy(source, destination)
        assert copy.execute(client) <= 0
        assert client.mock_calls == [
            call.collect_md5_hashes__(source, cache={}, timeout=10 * 60),
        ]


def test_checked_copy__terminates_if_collect_md5s_fails_2(client, source, destination):
    with patch("azsync.sync.collect_md5_hashes", autospec=True) as mock:
        # Attaching the mock ensures that it shows up in 'mock_calls'
        client.attach_mock(mock, "collect_md5_hashes__")

        mock.return_value = {}

        copy = CheckedCopy(source, destination)
        assert copy.execute(client) == 0
        assert client.mock_calls == [
            call.collect_md5_hashes__(source, cache={}, timeout=10 * 60),
        ]


def test_checked_copy__terminates_if_get_md5_fails__1st(client, source, destination):
    with patch("azsync.sync.collect_md5_hashes", autospec=True) as mock:
        mock.return_value = {".": None}

        client.get_md5.side_effect = AZError("xyz")

        copy = CheckedCopy(source, destination)
        with pytest.raises(AZError, match="xyz"):
            copy.execute(client)

        assert client.mock_calls == [call.get_md5(dst_url=destination)]


def test_checked_copy__terminates_if_get_md5_fails__loop(client, source, destination):
    with patch("azsync.sync.collect_md5_hashes", autospec=True) as mock:
        # Attaching the mock ensures that it shows up in 'mock_calls'
        client.attach_mock(mock, "collect_md5_hashes__")
        mock.return_value = {"foo": Untouchable()}

        client.get_md5.side_effect = [
            AZFileNotFoundError("BlobNotFound"),
            AZError("xyz"),
        ]

        copy = CheckedCopy(source, destination)
        with pytest.raises(AZError, match="xyz"):
            copy.execute(client)

        assert client.mock_calls == [
            call.collect_md5_hashes__(source, cache={}, timeout=10 * 60),
            call.get_md5(dst_url=destination),
            call.copy(source, destination),
            call.collect_md5_hashes__(source, cache=mock.return_value, timeout=10 * 60),
            call.get_md5(dst_url=destination),
        ]


def test_checked_copy__terminates_if_copy_fails(client, source, destination):
    with patch("azsync.sync.collect_md5_hashes", autospec=True) as mock:
        # Attaching the mock ensures that it shows up in 'mock_calls'
        client.attach_mock(mock, "collect_md5_hashes__")
        mock.return_value = {"foo": None}

        client.get_md5.side_effect = AZFileNotFoundError("BlobNotFound")
        client.copy.side_effect = AZError("xyz")

        copy = CheckedCopy(source, destination)
        with pytest.raises(AZError, match="xyz"):
            copy.execute(client)

        assert client.mock_calls == [
            call.collect_md5_hashes__(source, cache={}, timeout=10 * 60),
            call.get_md5(dst_url=destination),
            call.copy(source, destination),
        ]


def test_checked_copy__matching_files__files_on_server(client, source, destination):
    with patch("azsync.sync.collect_md5_hashes", autospec=True) as mock:
        # Attaching the mock ensures that it shows up in 'mock_calls'
        client.attach_mock(mock, "collect_md5_hashes__")

        mock.return_value = {Path("zod"): PartialStats(hash="4321", size=17, mtime=123)}
        client.get_md5.side_effect = [PartialStats(hash="4321", size=17)]

        copy = CheckedCopy(source, destination)
        assert copy.execute(client) == TRIES
        assert client.mock_calls == [
            call.collect_md5_hashes__(source, cache={}, timeout=10 * 60),
            call.get_md5(dst_url=destination),
        ]


def test_checked_copy__matching_files__no_files_on_server(client, source, destination):
    hashes = {Path("zod"): PartialStats(hash="4321", size=17)}

    with patch("azsync.sync.collect_md5_hashes", autospec=True) as mock:
        # Attaching the mock ensures that it shows up in 'mock_calls'
        client.attach_mock(mock, "collect_md5_hashes__")

        mock.return_value = dict(hashes)
        client.get_md5.side_effect = [
            AZFileNotFoundError("BlobNotFound"),
            PartialStats(hash="4321", size=17),
        ]

        copy = CheckedCopy(source, destination)
        assert copy.execute(client) == TRIES
        assert client.mock_calls == [
            call.collect_md5_hashes__(source, cache={}, timeout=10 * 60),
            call.get_md5(dst_url=destination),
            call.copy(source, destination),
            call.collect_md5_hashes__(source, cache=hashes, timeout=10 * 60),
            call.get_md5(dst_url=destination),
        ]


def test_checked_copy__matching_files__diff_filenames(client, source, destination):
    with patch("azsync.sync.collect_md5_hashes", autospec=True) as mock:
        # Attaching the mock ensures that it shows up in 'mock_calls'
        client.attach_mock(mock, "collect_md5_hashes__")

        mock.return_value = {Path("."): PartialStats(hash="4321", size=17)}
        client.get_md5.side_effect = [PartialStats(hash="4321", size=17)]

        copy = CheckedCopy(source, destination)
        assert copy.execute(client) == TRIES
        assert client.mock_calls == [
            call.collect_md5_hashes__(source, cache={}, timeout=10 * 60),
            call.get_md5(dst_url=destination),
        ]


def test_checked_copy__mismatching_file_size_on_remote(client, source, destination):
    with patch("azsync.sync.collect_md5_hashes", autospec=True) as mock:
        # Attaching the mock ensures that it shows up in 'mock_calls'
        client.attach_mock(mock, "collect_md5_hashes__")

        mock.return_value = {Path("zod"): PartialStats(hash="4321", size=18)}
        client.get_md5.side_effect = [
            PartialStats(hash="4321", size=17),
            PartialStats(hash="4321", size=18),
        ]

        copy = CheckedCopy(source, destination)
        assert copy.execute(client) == TRIES
        assert client.mock_calls == [
            call.collect_md5_hashes__(source, cache={}, timeout=10 * 60),
            call.get_md5(dst_url=destination),
            call.copy(source, destination),
            call.collect_md5_hashes__(source, cache=mock.return_value, timeout=10 * 60),
            call.get_md5(dst_url=destination),
        ]


def test_checked_copy__mismatching_file_size_on_remote__after_copy(
    client, source, destination
):
    with patch("azsync.sync.collect_md5_hashes", autospec=True) as mock:
        # Attaching the mock ensures that it shows up in 'mock_calls'
        client.attach_mock(mock, "collect_md5_hashes__")

        mock.return_value = {Path("zod"): PartialStats(hash="4321", size=18)}
        client.get_md5.side_effect = [
            AZFileNotFoundError("BlobNotFound"),
            PartialStats(hash="4321", size=17),
            PartialStats(hash="4321", size=18),
        ]

        copy = CheckedCopy(source, destination)
        assert copy.execute(client) == TRIES - 1
        assert client.mock_calls == [
            call.collect_md5_hashes__(source, cache={}, timeout=10 * 60),
            call.get_md5(dst_url=destination),
            call.copy(source, destination),
            call.collect_md5_hashes__(source, cache=mock.return_value, timeout=10 * 60),
            call.get_md5(dst_url=destination),
            call.copy(source, destination),
            call.collect_md5_hashes__(source, cache=mock.return_value, timeout=10 * 60),
            call.get_md5(dst_url=destination),
        ]


def test_checked_copy__mismatching_file_hash_on_remote(client, source, destination):
    with patch("azsync.sync.collect_md5_hashes", autospec=True) as mock:
        # Attaching the mock ensures that it shows up in 'mock_calls'
        client.attach_mock(mock, "collect_md5_hashes__")

        mock.return_value = {Path("foo/bar"): PartialStats(hash="123x", size=1234)}
        client.get_md5.side_effect = [
            PartialStats(hash="1234", size=1234),
            PartialStats(hash="123x", size=1234),
        ]

        copy = CheckedCopy(source, destination)
        assert copy.execute(client) == TRIES
        assert client.mock_calls == [
            call.collect_md5_hashes__(source, cache={}, timeout=10 * 60),
            call.get_md5(dst_url=destination),
            call.copy(source, destination),
            call.collect_md5_hashes__(source, cache=mock.return_value, timeout=10 * 60),
            call.get_md5(dst_url=destination),
        ]


def test_checked_copy__mismatching_file_hash_on_remote__after_copy(
    client, source, destination
):
    with patch("azsync.sync.collect_md5_hashes", autospec=True) as mock:
        # Attaching the mock ensures that it shows up in 'mock_calls'
        client.attach_mock(mock, "collect_md5_hashes__")

        mock.return_value = {Path("foo/bar"): PartialStats(hash="123x", size=1234)}
        client.get_md5.side_effect = [
            AZFileNotFoundError("BlobNotFound"),
            PartialStats(hash="1234", size=1234),
            PartialStats(hash="123x", size=1234),
        ]

        copy = CheckedCopy(source, destination)
        assert copy.execute(client) == TRIES - 1
        assert client.mock_calls == [
            call.collect_md5_hashes__(source, cache={}, timeout=10 * 60),
            call.get_md5(dst_url=destination),
            call.copy(source, destination),
            call.collect_md5_hashes__(source, cache=mock.return_value, timeout=10 * 60),
            call.get_md5(dst_url=destination),
            call.copy(source, destination),
            call.collect_md5_hashes__(source, cache=mock.return_value, timeout=10 * 60),
            call.get_md5(dst_url=destination),
        ]


def test_checked_copy__local_file_changed_after_copy(client, source, destination):
    local_files_1 = {Path("foo/bar"): PartialStats(hash="123x", size=1234)}
    local_files_2 = {Path("foo/bar"): PartialStats(hash="12xx", size=1234)}

    with patch("azsync.sync.collect_md5_hashes", autospec=True) as mock:
        # Attaching the mock ensures that it shows up in 'mock_calls'
        client.attach_mock(mock, "collect_md5_hashes__")

        mock.side_effect = [local_files_1, local_files_2, local_files_2]
        client.get_md5.side_effect = [
            AZFileNotFoundError("BlobNotFound"),
            PartialStats(hash="123x", size=1234),
            PartialStats(hash="12xx", size=1234),
        ]

        copy = CheckedCopy(source, destination)
        assert copy.execute(client) == TRIES - 1
        assert client.mock_calls == [
            call.collect_md5_hashes__(source, cache={}, timeout=10 * 60),
            call.get_md5(dst_url=destination),
            call.copy(source, destination),
            call.collect_md5_hashes__(source, cache=local_files_1, timeout=10 * 60),
            call.get_md5(dst_url=destination),
            call.copy(source, destination),
            call.collect_md5_hashes__(source, cache=local_files_2, timeout=10 * 60),
            call.get_md5(dst_url=destination),
        ]


#############################################################################
# CheckedMultiCopy


def test_checked_multi_copy__repr_1(source, destination):
    file_map = {Path("foo"): source}
    copy = CheckedMultiCopy(file_map, destination)
    file_map = {Path("foo"): Path(source)}

    assert repr(copy) == f"CheckedMultiCopy({file_map!r}, {destination!r}, 600)"


def test_checked_multi_copy__repr_2(source, destination):
    file_map = {"foo": source}
    copy = CheckedMultiCopy(file_map, destination, timeout=7913)
    file_map = {Path("foo"): Path(source)}

    assert repr(copy) == f"CheckedMultiCopy({file_map!r}, {destination!r}, 7913)"


def test_checked_multi_copy__execute__no_tries_left(client, source, destination):
    copy = CheckedMultiCopy({"file": source}, destination)

    with patch("azsync.sync.calculate_md5_hashes", autospec=True) as mock:
        # Attaching the mock ensures that it shows up in 'mock_calls'
        client.attach_mock(mock, "calculate_md5_hashes__")

        assert copy.execute(client, tries=0) == 0
        assert client.mock_calls == []


def test_checked_multi_copy__terminates_if_collect_md5s_fails_1(
    client, source, destination
):
    with patch("azsync.sync.calculate_md5_hashes", autospec=True) as mock:
        # Attaching the mock ensures that it shows up in 'mock_calls'
        client.attach_mock(mock, "calculate_md5_hashes__")
        mock.side_effect = multiprocessing.TimeoutError()

        copy = CheckedMultiCopy({"foo": source}, destination)
        assert copy.execute(client) <= 0
        assert client.mock_calls == [
            call.calculate_md5_hashes__(
                filepaths=[Path(source)],
                timeout=10 * 60,
                cache=None,
            ),
        ]


def test_checked_multi_copy__terminates_if_collect_md5s_fails_2(
    client, source, destination
):
    with patch("azsync.sync.calculate_md5_hashes", autospec=True) as mock:
        # Attaching the mock ensures that it shows up in 'mock_calls'
        client.attach_mock(mock, "calculate_md5_hashes__")

        mock.return_value = {}

        copy = CheckedMultiCopy({"foo": source}, destination)
        with pytest.raises(KeyError, match=source):
            copy.execute(client)

        assert client.mock_calls == [
            call.calculate_md5_hashes__(
                filepaths=[Path(source)],
                timeout=10 * 60,
                cache=None,
            ),
            call.list_md5s(destination),
        ]


def test_checked_multi_copy__terminates_if_list_md5s_fails(client, source, destination):
    with patch("azsync.sync.calculate_md5_hashes", autospec=True) as mock:
        # Attaching the mock ensures that it shows up in 'mock_calls'
        client.attach_mock(mock, "calculate_md5_hashes__")
        client.list_md5s.side_effect = AZError("xyz")

        mock.return_value = {Path("."): Untouchable()}

        copy = CheckedMultiCopy({"foo": source}, destination)
        with pytest.raises(AZError, match="xyz"):
            copy.execute(client)

        assert client.mock_calls == [
            call.calculate_md5_hashes__(
                filepaths=[Path(source)],
                timeout=10 * 60,
                cache=None,
            ),
            call.list_md5s(destination),
        ]


def test_checked_multi_copy__terminates_if_copy_fails(client, source, destination):
    with patch("azsync.sync.calculate_md5_hashes", autospec=True) as mock:
        # Attaching the mock ensures that it shows up in 'mock_calls'
        client.attach_mock(mock, "calculate_md5_hashes__")
        client.list_md5s.return_value = {}
        client.copy.side_effect = AZError("xyz")

        mock.return_value = {Path(source): Untouchable()}

        copy = CheckedMultiCopy({"foo": Path(source)}, destination)
        with pytest.raises(AZError, match="xyz"):
            copy.execute(client)

        assert client.mock_calls == [
            call.calculate_md5_hashes__(
                filepaths=[Path(source)],
                timeout=10 * 60,
                cache=None,
            ),
            call.list_md5s(destination),
            call.copy(Path(source), urljoin(destination, "foo")),
        ]


def test_checked_multi_copy__empty_file_lists(client, source, destination):
    with patch("azsync.sync.calculate_md5_hashes", autospec=True) as mock:
        # Attaching the mock ensures that it shows up in 'mock_calls'
        client.attach_mock(mock, "calculate_md5_hashes__")
        client.list_md5s = mock_list_md5s({})

        mock.return_value = {}

        copy = CheckedMultiCopy({}, destination)
        assert copy.execute(client) == TRIES
        assert client.mock_calls == [
            call.calculate_md5_hashes__(
                filepaths=[],
                timeout=10 * 60,
                cache=None,
            ),
            call.list_md5s(destination),
        ]


def test_checked_multi_copy__matching_files_on_server(client, source, destination):
    with patch("azsync.sync.calculate_md5_hashes", autospec=True) as mock:
        # Attaching the mock ensures that it shows up in 'mock_calls'
        client.attach_mock(mock, "calculate_md5_hashes__")
        client.list_md5s = mock_list_md5s(
            {Path("zod"): PartialStats(hash="4321", size=17)}
        )

        mock.return_value = {Path(source): PartialStats(hash="4321", size=17, mtime=12)}

        copy = CheckedMultiCopy({Path("zod"): source}, destination)
        assert copy.execute(client) == TRIES
        assert client.mock_calls == [
            call.calculate_md5_hashes__(
                filepaths=[Path(source)],
                timeout=10 * 60,
                cache=None,
            ),
            call.list_md5s(destination),
        ]


def test_checked_multi_copy__no_files_on_server(client, destination):
    local_files = {
        Path("/foo/bar"): PartialStats(hash="4321", size=17, mtime=1234),
        Path("/test/other"): PartialStats(hash="sdfa", size=145, mtime=23456),
    }

    with patch("azsync.sync.calculate_md5_hashes", autospec=True) as mock:
        # Attaching the mock ensures that it shows up in 'mock_calls'
        client.attach_mock(mock, "calculate_md5_hashes__")
        client.list_md5s = mock_list_md5s(
            {},
            {
                Path("file_1"): PartialStats(hash="4321", size=17),
                Path("dir/file_2"): PartialStats(hash="sdfa", size=145),
            },
        )

        mock.return_value = deepcopy(local_files)

        copy = CheckedMultiCopy(
            {"file_1": "/foo/bar", "dir/file_2": "/test/other"}, destination
        )

        assert copy.execute(client) == TRIES
        assert client.mock_calls == [
            call.calculate_md5_hashes__(
                filepaths=[Path("/foo/bar"), Path("/test/other")],
                timeout=10 * 60,
                cache=None,
            ),
            call.list_md5s(destination),
            call.copy(Path("/test/other"), urljoin(destination, "dir/file_2")),
            call.copy(Path("/foo/bar"), urljoin(destination, "file_1")),
            call.calculate_md5_hashes__(
                filepaths=[Path("/foo/bar"), Path("/test/other")],
                timeout=10 * 60,
                cache=local_files,
            ),
            call.list_md5s(destination),
        ]


def test_checked_multi_copy__other_files_on_server(client, destination):
    local_files = {
        Path("/foo/bar"): PartialStats(hash="4321", size=17, mtime=1234),
        Path("/test/other"): PartialStats(hash="sdfa", size=145, mtime=23456),
    }

    with patch("azsync.sync.calculate_md5_hashes", autospec=True) as mock:
        # Attaching the mock ensures that it shows up in 'mock_calls'
        client.attach_mock(mock, "calculate_md5_hashes__")
        client.list_md5s = mock_list_md5s(
            {
                Path("file_3"): PartialStats(hash="asdfas", size=127),
                Path("folder/file_4"): PartialStats(hash="sdfax", size=140),
            },
            {
                Path("dir/file_2"): PartialStats(hash="sdfa", size=145),
                Path("file_1"): PartialStats(hash="4321", size=17),
                Path("file_3"): PartialStats(hash="asdfas", size=127),
                Path("folder/file_4"): PartialStats(hash="sdfax", size=140),
            },
        )

        mock.return_value = deepcopy(local_files)

        copy = CheckedMultiCopy(
            {"file_1": "/foo/bar", "dir/file_2": "/test/other"}, destination
        )

        assert copy.execute(client) == TRIES
        assert client.mock_calls == [
            call.calculate_md5_hashes__(
                filepaths=[Path("/foo/bar"), Path("/test/other")],
                timeout=10 * 60,
                cache=None,
            ),
            call.list_md5s(destination),
            call.copy(Path("/test/other"), urljoin(destination, "dir/file_2")),
            call.copy(Path("/foo/bar"), urljoin(destination, "file_1")),
            call.calculate_md5_hashes__(
                filepaths=[Path("/foo/bar"), Path("/test/other")],
                timeout=10 * 60,
                cache=local_files,
            ),
            call.list_md5s(destination),
        ]


def test_checked_multi_copy__mismatching_file_on_server(client, destination):
    local_files = {
        Path("/foo/bar"): PartialStats(hash="4321", size=17, mtime=1234),
        Path("/test/other"): PartialStats(hash="sdfa", size=145, mtime=23456),
    }

    with patch("azsync.sync.calculate_md5_hashes", autospec=True) as mock:
        # Attaching the mock ensures that it shows up in 'mock_calls'
        client.attach_mock(mock, "calculate_md5_hashes__")
        client.list_md5s = mock_list_md5s(
            {
                Path("file_1"): PartialStats(hash="4321", size=17),
                Path("dir/file_2"): PartialStats(hash="sdfa", size=3245),
            },
            {
                Path("file_1"): PartialStats(hash="4321", size=17),
                Path("dir/file_2"): PartialStats(hash="sdfa", size=145),
            },
        )

        mock.return_value = deepcopy(local_files)

        copy = CheckedMultiCopy(
            {"file_1": "/foo/bar", "dir/file_2": "/test/other"}, destination
        )

        assert copy.execute(client) == TRIES
        assert client.mock_calls == [
            call.calculate_md5_hashes__(
                filepaths=[Path("/foo/bar"), Path("/test/other")],
                timeout=10 * 60,
                cache=None,
            ),
            call.list_md5s(destination),
            call.copy(Path("/test/other"), urljoin(destination, "dir/file_2")),
            call.calculate_md5_hashes__(
                filepaths=[Path("/foo/bar"), Path("/test/other")],
                timeout=10 * 60,
                cache=local_files,
            ),
            call.list_md5s(destination),
        ]


def test_checked_multi_copy__mismatching_remote_file_after_copy(client, destination):
    local_files = {
        Path("/foo/bar"): PartialStats(hash="4321", size=17, mtime=1234),
        Path("/test/other"): PartialStats(hash="sdfa", size=145, mtime=23456),
    }

    with patch("azsync.sync.calculate_md5_hashes", autospec=True) as mock:
        # Attaching the mock ensures that it shows up in 'mock_calls'
        client.attach_mock(mock, "calculate_md5_hashes__")
        client.list_md5s = mock_list_md5s(
            {},
            {
                Path("file_1"): PartialStats(hash="abcd", size=17),
                Path("dir/file_2"): PartialStats(hash="sdfa", size=145),
            },
            {
                Path("file_1"): PartialStats(hash="4321", size=17),
                Path("dir/file_2"): PartialStats(hash="sdfa", size=145),
            },
        )

        mock.return_value = deepcopy(local_files)

        copy = CheckedMultiCopy(
            {"file_1": "/foo/bar", "dir/file_2": "/test/other"}, destination
        )

        assert copy.execute(client) == TRIES - 1
        assert client.mock_calls == [
            call.calculate_md5_hashes__(
                filepaths=[Path("/foo/bar"), Path("/test/other")],
                timeout=10 * 60,
                cache=None,
            ),
            call.list_md5s(destination),
            call.copy(Path("/test/other"), urljoin(destination, "dir/file_2")),
            call.copy(Path("/foo/bar"), urljoin(destination, "file_1")),
            call.calculate_md5_hashes__(
                filepaths=[Path("/foo/bar"), Path("/test/other")],
                timeout=10 * 60,
                cache=local_files,
            ),
            call.list_md5s(destination),
            call.copy(Path("/foo/bar"), urljoin(destination, "file_1")),
            call.calculate_md5_hashes__(
                filepaths=[Path("/foo/bar"), Path("/test/other")],
                timeout=10 * 60,
                cache=local_files,
            ),
            call.list_md5s(destination),
        ]


def test_checked_multi_copy__mismatching_local_file_after_copy(client, destination):
    local_files_1 = {
        Path("/foo/bar"): PartialStats(hash="4321", size=17, mtime=1234),
        Path("/test/other"): PartialStats(hash="sdfa", size=145, mtime=23456),
    }

    local_files_2 = {
        Path("/foo/bar"): PartialStats(hash="4321", size=1744, mtime=1234),
        Path("/test/other"): PartialStats(hash="sdfa", size=145, mtime=23456),
    }

    with patch("azsync.sync.calculate_md5_hashes", autospec=True) as mock:
        # Attaching the mock ensures that it shows up in 'mock_calls'
        client.attach_mock(mock, "calculate_md5_hashes__")
        client.list_md5s = mock_list_md5s(
            {},
            {
                Path("file_1"): PartialStats(hash="4321", size=17),
                Path("dir/file_2"): PartialStats(hash="sdfa", size=145),
            },
            {
                Path("file_1"): PartialStats(hash="4321", size=1744),
                Path("dir/file_2"): PartialStats(hash="sdfa", size=145),
            },
        )

        mock.side_effect = deepcopy([local_files_1, local_files_2, local_files_2])

        copy = CheckedMultiCopy(
            {"file_1": "/foo/bar", "dir/file_2": "/test/other"}, destination
        )

        assert copy.execute(client) == TRIES - 1
        assert client.mock_calls == [
            call.calculate_md5_hashes__(
                filepaths=[Path("/foo/bar"), Path("/test/other")],
                timeout=10 * 60,
                cache=None,
            ),
            call.list_md5s(destination),
            call.copy(Path("/test/other"), urljoin(destination, "dir/file_2")),
            call.copy(Path("/foo/bar"), urljoin(destination, "file_1")),
            call.calculate_md5_hashes__(
                filepaths=[Path("/foo/bar"), Path("/test/other")],
                timeout=10 * 60,
                cache=local_files_1,
            ),
            call.list_md5s(destination),
            call.copy(Path("/foo/bar"), urljoin(destination, "file_1")),
            call.calculate_md5_hashes__(
                filepaths=[Path("/foo/bar"), Path("/test/other")],
                timeout=10 * 60,
                cache=local_files_2,
            ),
            call.list_md5s(destination),
        ]


def test_checked_multi_copy__abort_if_out_of_tries_after_copy(client, destination):
    local_files = {
        Path("/foo/bar"): PartialStats(hash="4321", size=17, mtime=1234),
        Path("/test/other"): PartialStats(hash="sdfa", size=145, mtime=23456),
    }

    with patch("azsync.sync.calculate_md5_hashes", autospec=True) as mock:
        # Attaching the mock ensures that it shows up in 'mock_calls'
        client.attach_mock(mock, "calculate_md5_hashes__")
        client.list_md5s = mock_list_md5s(
            {},
            {
                Path("file_1"): PartialStats(hash="abcd", size=17),
                Path("dir/file_2"): PartialStats(hash="sdfa", size=145),
            },
        )

        mock.return_value = deepcopy(local_files)

        copy = CheckedMultiCopy(
            {"file_1": "/foo/bar", "dir/file_2": "/test/other"}, destination
        )

        assert copy.execute(client, tries=1) == 0
        assert client.mock_calls == [
            call.calculate_md5_hashes__(
                filepaths=[Path("/foo/bar"), Path("/test/other")],
                timeout=10 * 60,
                cache=None,
            ),
            call.list_md5s(destination),
            call.copy(Path("/test/other"), urljoin(destination, "dir/file_2")),
            call.copy(Path("/foo/bar"), urljoin(destination, "file_1")),
            call.calculate_md5_hashes__(
                filepaths=[Path("/foo/bar"), Path("/test/other")],
                timeout=10 * 60,
                cache=local_files,
            ),
            call.list_md5s(destination),
        ]


def test_checked_multi_copy__escape_characters_in_filenames(client, destination):
    local_files = {
        Path("/foo/bar"): PartialStats(hash="4321", size=17, mtime=1234),
        Path("/test/other"): PartialStats(hash="sdfa", size=145, mtime=23456),
    }

    with patch("azsync.sync.calculate_md5_hashes", autospec=True) as mock:
        # Attaching the mock ensures that it shows up in 'mock_calls'
        client.attach_mock(mock, "calculate_md5_hashes__")
        client.list_md5s = mock_list_md5s(
            {},
            {
                Path("file_1?"): PartialStats(hash="4321", size=17),
                Path("dir/file:2"): PartialStats(hash="sdfa", size=145),
            },
        )

        mock.return_value = deepcopy(local_files)

        copy = CheckedMultiCopy(
            {"file_1?": "/foo/bar", "dir/file:2": "/test/other"}, destination
        )

        assert copy.execute(client) == TRIES
        assert client.mock_calls == [
            call.calculate_md5_hashes__(
                filepaths=[Path("/foo/bar"), Path("/test/other")],
                timeout=10 * 60,
                cache=None,
            ),
            call.list_md5s(destination),
            call.copy(Path("/test/other"), urljoin(destination, "dir/file%3A2")),
            call.copy(Path("/foo/bar"), urljoin(destination, "file_1%3F")),
            call.calculate_md5_hashes__(
                filepaths=[Path("/foo/bar"), Path("/test/other")],
                timeout=10 * 60,
                cache=local_files,
            ),
            call.list_md5s(destination),
        ]


#############################################################################
# RemoveLocal


def test_remove_local__repr(destination):
    rm = RemoveLocal(destination)

    assert repr(rm) == f"RemoveLocal({destination!r})"


def test_remove_local__execute__tries_left(client, destination):
    rm = RemoveLocal(destination)

    with patch("shutil.rmtree", autospec=True) as mock:
        assert rm.execute(client, tries=1) == 1
        assert client.mock_calls == []
        assert mock.mock_calls == [call(destination)]


def test_remove_local__execute__no_tries_left(client, destination):
    rm = RemoveLocal(destination)

    with patch("shutil.rmtree", autospec=True) as mock:
        assert rm.execute(client, tries=0) == 0
        assert client.mock_calls == []
        assert mock.mock_calls == []


#############################################################################
# RemoveRemote


def test_remove_remote__repr(destination):
    rm = RemoveRemote(destination)

    assert repr(rm) == f"RemoveRemote({destination!r})"


def test_remove_remote__execute(client, destination):
    rm = RemoveRemote(destination)

    assert rm.execute(client) == TRIES
    assert client.mock_calls == [call.remove(destination)]


def test_remove_remote__execute__no_tries_left(client, source, destination):
    rm = RemoveRemote(destination)

    assert rm.execute(client, tries=0) == 0
    assert client.mock_calls == []


#############################################################################
# Write


def test_write__repr(destination):
    write = Write(destination, "big chunk o' data here")

    assert repr(write) == f"Write({destination!r}, ...)"


def test_write__execute(tmp_path, client, destination):
    data = str(uuid.uuid4())

    tmp_file = tmp_path / "random_file.dat"
    with tmp_file.open("wb") as tmp_handle:
        with patch("tempfile.NamedTemporaryFile", autospec=True) as mock:
            mock.return_value = tmp_handle
            mock.name = str(tmp_file)

            with patch("azsync.sync.CheckedCopy", autospec=True) as copy_mock:
                copy_mock.return_value.execute.return_value = 50

                write = Write(destination, data)
                assert write.execute(client) == 50
                assert copy_mock.mock_calls == [
                    call(str(tmp_file), destination),
                    call().execute(client),
                ]
                assert tmp_file.read_bytes() == data.encode("utf-8")


def test_write__execute__binary_data(tmp_path, client, destination):
    data = str(uuid.uuid4())

    tmp_file = tmp_path / "random_file.dat"
    with tmp_file.open("wb") as tmp_handle:
        with patch("tempfile.NamedTemporaryFile", autospec=True) as mock:
            mock.return_value = tmp_handle
            mock.name = str(tmp_file)

            with patch("azsync.sync.CheckedCopy", autospec=True) as copy_mock:
                copy_mock.return_value.execute.return_value = 50

                write = Write(destination, data.encode("utf-8"))
                assert write.execute(client) == 50
                assert copy_mock.mock_calls == [
                    call(str(tmp_file), destination),
                    call().execute(client),
                ]
                assert tmp_file.read_bytes() == data.encode("utf-8")


def test_write__execute__no_tries_left(client, source, destination):
    write = Write(destination, str(uuid.uuid4()))

    with patch("tempfile.NamedTemporaryFile", autospec=True) as mock:
        client.attach_mock(mock, "NamedTemporaryFile__")

        assert write.execute(client, tries=0) == 0
        assert client.mock_calls == []


#############################################################################
# execute


def test_execute__empty_list(client):
    assert execute(client, [])
    assert client.mock_calls == []


def test_execute__execute_all_1(client):
    mock = Mock()
    mock.task1.execute.return_value = 5
    mock.task2.execute.return_value = 4
    mock.task3.execute.return_value = 3

    assert execute(client, [mock.task1, mock.task2, mock.task3])
    assert client.mock_calls == []
    assert mock.mock_calls == [
        call.task1.execute(client, 5),
        call.task2.execute(client, 5),
        call.task3.execute(client, 4),
    ]


def test_execute__execute_all_2(client):
    mock = Mock()
    mock.task1.execute.return_value = 0
    mock.task2.execute.return_value = 5
    mock.task3.execute.return_value = 5

    assert not execute(client, [mock.task1, mock.task2, mock.task3])
    assert client.mock_calls == []
    assert mock.mock_calls == [
        call.task1.execute(client, 5),
    ]


def test_execute__execute_all_3(client):
    mock = Mock()
    mock.task1.execute.return_value = 2
    mock.task2.execute.return_value = 0
    mock.task3.execute.return_value = 5

    assert not execute(client, [mock.task1, mock.task2, mock.task3])
    assert client.mock_calls == []
    assert mock.mock_calls == [
        call.task1.execute(client, 5),
        call.task2.execute(client, 2),
    ]


def test_execute__execute_all_4(client):
    mock = Mock()
    mock.task1.execute.return_value = 4
    mock.task2.execute.return_value = 1
    mock.task3.execute.return_value = 0

    assert not execute(client, [mock.task1, mock.task2, mock.task3])
    assert client.mock_calls == []
    assert mock.mock_calls == [
        call.task1.execute(client, 5),
        call.task2.execute(client, 4),
        call.task3.execute(client, 1),
    ]
