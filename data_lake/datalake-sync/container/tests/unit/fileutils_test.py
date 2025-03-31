import errno
import signal
import multiprocessing

from pathlib import Path
from unittest.mock import call, patch

import pytest

from azsync.fileutils import (
    PartialStats,
    calculate_md5_hashes,
    collect_files,
    collect_md5_hashes,
    iglob_folder,
    init_worker_process,
    md5_hash,
    try_makedirs,
)


def _write_file(root, rel_path, text=""):
    path = root / rel_path
    path.write_text(text)

    return path.stat().st_mtime


def test_file_stats__constructor__1():
    stats = PartialStats("11235", 7913)
    assert stats.hash == "11235"
    assert stats.size == 7913
    assert stats.mtime is None


def test_file_stats__constructor__2():
    stats = PartialStats("11235", 7913, 12345667)
    assert stats.hash == "11235"
    assert stats.size == 7913
    assert stats.mtime == 12345667


def test_file_stats__age():
    stats = PartialStats(mtime=987654)

    with patch("time.time", autospec=True) as mock:
        mock.return_value = 1000000

        assert stats.age() == 12346
        assert mock.mock_calls == [call()]


def test_file_stats__age__no_mtime():
    stats = PartialStats()

    with patch("time.time", autospec=True) as mock:
        assert stats.age() is None
        assert mock.mock_calls == []


def test_file_stats__to_json():
    stats = PartialStats()
    assert stats.to_json() == {"hash": None, "size": None, "mtime": None}
    stats = PartialStats("11235", 7913, 12345667)
    assert stats.to_json() == {"hash": "11235", "size": 7913, "mtime": 12345667}


def test_file_stats__from_json_1():
    stats = PartialStats.from_json({"hash": None, "size": None, "mtime": None})
    assert stats.hash is None
    assert stats.size is None
    assert stats.mtime is None


def test_file_stats__from_json_2():
    stats = PartialStats.from_json({"hash": "11235", "size": 7913, "mtime": 12345667})
    assert stats.hash == "11235"
    assert stats.size == 7913
    assert stats.mtime == 12345667


def test_file_stats__from_json__missing_keys():
    with pytest.raises(KeyError):
        assert PartialStats.from_json({"size": None, "mtime": None})
    with pytest.raises(KeyError):
        assert PartialStats.from_json({"hash": None, "mtime": None})
    with pytest.raises(KeyError):
        assert PartialStats.from_json({"hash": None, "size": None})


def test_file_stats__repr():
    assert repr(PartialStats()) == "PartialStats(*, *, *)"
    assert repr(PartialStats(hash="11235")) == "PartialStats('11235', *, *)"
    assert repr(PartialStats(size=7913)) == "PartialStats(*, 7913, *)"
    assert repr(PartialStats(mtime=12346)) == "PartialStats(*, *, 12346)"

    stats = PartialStats("11235", 7913, 12345)
    assert repr(stats) == "PartialStats('11235', 7913, 12345)"


def test_file_stats__equality():
    assert PartialStats(hash="12345") != 1

    assert PartialStats(hash="12345") == PartialStats(hash="12345")
    assert PartialStats(hash="12345") != PartialStats(hash="12346")
    assert PartialStats(size=12345) == PartialStats(size=12345)
    assert PartialStats(size=12345) != PartialStats(size=12346)
    assert PartialStats(mtime=12345) == PartialStats(mtime=12345)
    assert PartialStats(mtime=12345) != PartialStats(mtime=12346)

    full_stats = PartialStats(hash="12345", size=7913, mtime=123456)
    assert full_stats != PartialStats(hash="12345")
    assert full_stats.match(
        PartialStats(hash="12345"), optional_size=True, optional_mtime=True
    )
    assert full_stats != PartialStats(size=7913)
    assert full_stats.match(
        PartialStats(size=7913), optional_hash=True, optional_mtime=True
    )
    assert full_stats != PartialStats(mtime=123456)
    assert full_stats.match(
        PartialStats(mtime=123456), optional_hash=True, optional_size=True
    )
    assert full_stats != PartialStats(hash="12345", size=7913)
    assert full_stats.match(PartialStats(hash="12345", size=7913), optional_mtime=True)
    assert full_stats != PartialStats(hash="12345", mtime=123456)
    assert full_stats.match(
        PartialStats(hash="12345", mtime=123456), optional_size=True
    )
    assert full_stats != PartialStats(size=7913, mtime=123456)
    assert full_stats.match(PartialStats(size=7913, mtime=123456), optional_hash=True)
    assert full_stats == PartialStats(hash="12345", size=7913, mtime=123456)


def test_md5_hash__empty_file(tmp_path):
    tmpfile = tmp_path / "empty_file"
    tmpfile.touch()

    assert md5_hash(tmpfile) == "D41D8CD98F00B204E9800998ECF8427E"


def test_md5_hash__non_empty_file(tmp_path):
    tmpfile = tmp_path / "empty_file"
    tmpfile.write_bytes(b"foobar")

    assert md5_hash(tmpfile) == "3858F62230AC3C915F300C664312C63F"


def test_md5_hash__non_empty_file__str(tmp_path):
    tmpfile = tmp_path / "empty_file"
    tmpfile.write_bytes(b"foobar")

    assert md5_hash(str(tmpfile)) == "3858F62230AC3C915F300C664312C63F"


def test_iglob_folder__empty_folder(tmp_path):
    assert iglob_folder(tmp_path, "*") == []


def test_iglob_folder__non_empty_folder(tmp_path):
    filepath_a = tmp_path / "bar.txt"
    filepath_b = tmp_path / "foo.gz"

    filepath_a.touch()
    filepath_b.touch()

    assert iglob_folder(tmp_path, "*") == [filepath_a, filepath_b]


def test_iglob_folder__matching(tmp_path):
    (tmp_path / "bar.txt").touch()
    (tmp_path / "foo.gz").touch()
    (tmp_path / "zod.txt").touch()

    assert iglob_folder(tmp_path, "*.gz") == [tmp_path / "foo.gz"]


def test_iglob_folder__matching_case_insensitive(tmp_path):
    (tmp_path / "bar.gZ").touch()
    (tmp_path / "foo.gz").touch()
    (tmp_path / "zod.Gz").touch()

    assert iglob_folder(tmp_path, "*.gz") == [
        tmp_path / "bar.gZ",
        tmp_path / "foo.gz",
        tmp_path / "zod.Gz",
    ]


def test_iglob_folder__missing_dir(tmp_path):
    with pytest.raises(FileNotFoundError):
        iglob_folder(tmp_path / "foo", "*")


def test_collect_files__empty_folder(tmp_path):
    assert collect_files(tmp_path) == {}


def test_collect_files__empty_folder__str(tmp_path):
    assert collect_files(str(tmp_path)) == {}


def test_collect_files__path_is_file__str(tmp_path):
    file_1_mtime = _write_file(tmp_path, "foobar.txt", "test")
    tmp_filepath = tmp_path / "foobar.txt"

    assert collect_files(str(tmp_filepath)) == {
        tmp_filepath: PartialStats(size=4, mtime=file_1_mtime),
    }


def test_collect_files__folder_with_files(tmp_path):
    file_1_mtime = _write_file(tmp_path, "foobar.txt", "test")
    file_2_mtime = _write_file(tmp_path, "zod.zip", "")

    tmp_path_2 = tmp_path / "xyz"
    tmp_path_2.mkdir()

    file_3_mtime = _write_file(tmp_path_2, "file3.fastq", ">chr13")

    tmp_path_3 = tmp_path_2 / "subfolder"
    tmp_path_3.mkdir()

    file_4_mtime = _write_file(tmp_path_3, "file", "bar")

    assert collect_files(tmp_path) == {
        tmp_path / "foobar.txt": PartialStats(size=4, mtime=file_1_mtime),
        tmp_path / "zod.zip": PartialStats(size=0, mtime=file_2_mtime),
        tmp_path_2 / "file3.fastq": PartialStats(size=6, mtime=file_3_mtime),
        tmp_path_3 / "file": PartialStats(size=3, mtime=file_4_mtime),
    }


def test_collect_files__path_not_found(tmp_path):
    with pytest.raises(FileNotFoundError):
        collect_files(tmp_path / "this_path_does_not_exist")


def test_collect_md5_hashes__empty_folder(tmp_path):
    assert collect_md5_hashes(tmp_path, {}) == {}


def test_collect_md5_hashes__folder_with_files(tmp_path):
    file_1_mtime = _write_file(tmp_path, "foobar.txt", "foobar")
    tmp_path_2 = tmp_path / "foo"
    tmp_path_2.mkdir()
    file_2_mtime = _write_file(tmp_path_2, "zod.zip", "")

    assert collect_md5_hashes(tmp_path, {}) == {
        (tmp_path / "foobar.txt"): PartialStats(
            hash="3858F62230AC3C915F300C664312C63F",
            size=6,
            mtime=file_1_mtime,
        ),
        (tmp_path / "foo" / "zod.zip"): PartialStats(
            hash="D41D8CD98F00B204E9800998ECF8427E",
            size=0,
            mtime=file_2_mtime,
        ),
    }


def test_collect_md5_hashes__root_is_file(tmp_path):
    file_1_mtime = _write_file(tmp_path, "foobar.txt", "foobar")

    assert collect_md5_hashes(tmp_path / "foobar.txt", {}) == {
        (tmp_path / "foobar.txt"): PartialStats(
            hash="3858F62230AC3C915F300C664312C63F",
            size=6,
            mtime=file_1_mtime,
        ),
    }


def test_collect_md5_hashes__with_outdated_cache(tmp_path):
    file_1_mtime = _write_file(tmp_path, "foobar.txt", "foobar")
    _write_file(tmp_path, "zod.zip", "")
    cache = collect_md5_hashes(tmp_path)
    file_2_mtime = _write_file(tmp_path, "zod.zip", "bar")

    with patch("azsync.fileutils.md5_hash", autospec=True) as mock:
        mock.return_value = "dummy md5 hash"

        assert collect_md5_hashes(tmp_path, cache) == {
            (tmp_path / "foobar.txt"): PartialStats(
                size=6,
                mtime=file_1_mtime,
                hash="3858F62230AC3C915F300C664312C63F",
            ),
            (tmp_path / "zod.zip"): PartialStats(
                size=3,
                mtime=file_2_mtime,
                hash="dummy md5 hash",
            ),
        }


def test_collect_md5_hashes__with_partial_cache(tmp_path):
    file_1_mtime = _write_file(tmp_path, "foobar.txt", "foobar")
    cache = collect_md5_hashes(tmp_path)
    file_2_mtime = _write_file(tmp_path, "zod.zip", "bar")

    with patch("azsync.fileutils.md5_hash", autospec=True) as mock:
        mock.return_value = "dummy md5 hash"

        assert collect_md5_hashes(tmp_path, cache) == {
            (tmp_path / "foobar.txt"): PartialStats(
                size=6,
                mtime=file_1_mtime,
                hash="3858F62230AC3C915F300C664312C63F",
            ),
            (tmp_path / "zod.zip"): PartialStats(
                size=3,
                mtime=file_2_mtime,
                hash="dummy md5 hash",
            ),
        }


def test_collect_md5_hashes__with_cache_missing_hash(tmp_path):
    file_1_mtime = _write_file(tmp_path, "foobar.txt", "foobar")
    cache = collect_md5_hashes(tmp_path)

    cache[Path(tmp_path / "foobar.txt")].hash = None

    assert collect_md5_hashes(tmp_path, cache) == {
        (tmp_path / "foobar.txt"): PartialStats(
            size=6,
            mtime=file_1_mtime,
            hash="3858F62230AC3C915F300C664312C63F",
        )
    }


def test_collect_md5_hashes__timeout(tmp_path):
    with patch("azsync.fileutils.collect_files", autospec=True) as mock:
        mock.side_effect = multiprocessing.TimeoutError()

        with pytest.raises(
            multiprocessing.TimeoutError, match="timeout while collecting files"
        ):
            collect_md5_hashes(tmp_path)


def test_collect_md5_hashes__timeout_in_hash_md5(tmp_path):
    file_path = tmp_path / "foobar.txt"
    file_mtime = _write_file(tmp_path, "foobar.txt", "foobar")

    with patch("azsync.fileutils.collect_files", autospec=True) as cmock:
        cmock.return_value = {
            file_path: PartialStats(size=4, mtime=file_mtime),
        }

        with patch("azsync.fileutils.md5_hash", autospec=True) as hmock:
            hmock.side_effect = multiprocessing.TimeoutError(file_path)

            with pytest.raises(multiprocessing.TimeoutError, match=str(file_path)):
                collect_md5_hashes(tmp_path)


def test_calculate_md5_hashes__path_not_found(tmp_path):
    with pytest.raises(FileNotFoundError):
        calculate_md5_hashes([tmp_path / "this_path_does_not_exist"])


def test_calculate_md5_hashes__path_is_directory(tmp_path):
    with pytest.raises(IsADirectoryError):
        calculate_md5_hashes([tmp_path])


def test_calculate_md5_hashes__empty_list(tmp_path):
    assert calculate_md5_hashes(()) == {}


def test_calculate_md5_hashes__non_empty_list(tmp_path):
    file_1_mtime = _write_file(tmp_path, "foobar.txt", "foobar")
    tmp_path_2 = tmp_path / "foo"
    tmp_path_2.mkdir()
    file_2_mtime = _write_file(tmp_path_2, "zod.zip", "")

    assert calculate_md5_hashes(
        [tmp_path / "foobar.txt", tmp_path / "foo" / "zod.zip"]
    ) == {
        (tmp_path / "foobar.txt"): PartialStats(
            hash="3858F62230AC3C915F300C664312C63F",
            size=6,
            mtime=file_1_mtime,
        ),
        (tmp_path / "foo" / "zod.zip"): PartialStats(
            hash="D41D8CD98F00B204E9800998ECF8427E",
            size=0,
            mtime=file_2_mtime,
        ),
    }


def test_calculate_md5_hashes__with_outdated_cache(tmp_path):
    filepaths = [tmp_path / "foobar.txt", tmp_path / "zod.zip"]

    file_1_mtime = _write_file(tmp_path, "foobar.txt", "foobar")
    _write_file(tmp_path, "zod.zip", "")
    cache = calculate_md5_hashes(filepaths)
    file_2_mtime = _write_file(tmp_path, "zod.zip", "bar")

    with patch("azsync.fileutils.md5_hash", autospec=True) as mock:
        mock.return_value = "dummy md5 hash"

        assert calculate_md5_hashes(filepaths, cache) == {
            (tmp_path / "foobar.txt"): PartialStats(
                size=6,
                mtime=file_1_mtime,
                hash="3858F62230AC3C915F300C664312C63F",
            ),
            (tmp_path / "zod.zip"): PartialStats(
                size=3,
                mtime=file_2_mtime,
                hash="dummy md5 hash",
            ),
        }


def test_calculate_md5_hashes__with_partial_cache(tmp_path):
    file_1_mtime = _write_file(tmp_path, "foobar.txt", "foobar")
    cache = calculate_md5_hashes([tmp_path / "foobar.txt"])
    file_2_mtime = _write_file(tmp_path, "zod.zip", "bar")

    filepaths = [tmp_path / "foobar.txt", tmp_path / "zod.zip"]

    with patch("azsync.fileutils.md5_hash", autospec=True) as mock:
        mock.return_value = "dummy md5 hash"

        assert calculate_md5_hashes(filepaths, cache) == {
            (tmp_path / "foobar.txt"): PartialStats(
                size=6,
                mtime=file_1_mtime,
                hash="3858F62230AC3C915F300C664312C63F",
            ),
            (tmp_path / "zod.zip"): PartialStats(
                size=3,
                mtime=file_2_mtime,
                hash="dummy md5 hash",
            ),
        }


def test_calculate_md5_hashes__with_cache_missing_hash(tmp_path):
    filepaths = [tmp_path / "foobar.txt"]
    file_1_mtime = _write_file(tmp_path, "foobar.txt", "foobar")
    cache = calculate_md5_hashes(filepaths)

    cache[Path(tmp_path / "foobar.txt")].hash = None

    assert calculate_md5_hashes(filepaths, cache) == {
        (tmp_path / "foobar.txt"): PartialStats(
            size=6,
            mtime=file_1_mtime,
            hash="3858F62230AC3C915F300C664312C63F",
        )
    }


def test_calculate_md5_hashes__timeout_in_hash_md5(tmp_path):
    file_path = tmp_path / "foobar.txt"
    file_path.touch()

    with patch("azsync.fileutils.md5_hash", autospec=True) as hmock:
        hmock.side_effect = multiprocessing.TimeoutError(file_path)

        with pytest.raises(multiprocessing.TimeoutError, match=str(file_path)):
            calculate_md5_hashes([file_path])


def test_mkdir__dir_exists(tmp_path):
    assert not try_makedirs(tmp_path)
    assert not try_makedirs(str(tmp_path))


def test_mkdir__dir_does_not_exist(tmp_path):
    assert try_makedirs(tmp_path / "folder1")
    assert try_makedirs(str(tmp_path / "folder2"))


def test_mkdir__raises_oserror_other_than_eexist(tmp_path):
    with patch("os.makedirs", autospec=True) as mock:
        mock.side_effect = OSError(errno.EACCES)

        with pytest.raises(OSError):
            try_makedirs(tmp_path)


def test_mkdir__raises_non_oserror(tmp_path):
    with patch("os.makedirs", autospec=True) as mock:
        mock.side_effect = ValueError()

        with pytest.raises(ValueError):
            try_makedirs(tmp_path)


def test_init_worker_process():
    original_handler = signal.getsignal(signal.SIGINT)

    try:
        init_worker_process()

        assert signal.getsignal(signal.SIGINT) == signal.SIG_IGN
    finally:
        signal.signal(signal.SIGINT, original_handler)
