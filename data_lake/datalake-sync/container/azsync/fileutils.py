import errno
import fnmatch
import hashlib
import multiprocessing
import os
import signal
import time

from pathlib import Path


class PartialStats:
    def __init__(self, hash=None, size=None, mtime=None):
        self.hash = hash
        self.size = size
        self.mtime = mtime

        if not (isinstance(hash, str) or hash is None):
            raise ValueError(f"hash must be str or None, not {hash!r}")
        elif not (isinstance(size, int) or size is None):
            raise ValueError(f"size must be int or None, not {size!r}")
        elif not (isinstance(mtime, (int, float)) or mtime is None):
            raise ValueError(f"mtime must be int, float or None, not {mtime!r}")

    def age(self):
        if self.mtime is None:
            return None

        return time.time() - self.mtime

    def to_json(self):
        return {
            "hash": self.hash,
            "size": self.size,
            "mtime": self.mtime,
        }

    @classmethod
    def from_json(cls, data):
        return PartialStats(hash=data["hash"], size=data["size"], mtime=data["mtime"])

    @classmethod
    def from_filepath(cls, filepath):
        filestat = filepath.stat()

        return PartialStats(size=filestat.st_size, mtime=filestat.st_mtime)

    def match(
        self, other, optional_hash=False, optional_size=False, optional_mtime=False
    ):
        if not isinstance(other, PartialStats):
            raise TypeError(other)

        return (
            (
                self.hash == other.hash
                or (optional_hash and (self.hash is None or other.hash is None))
            )
            and (
                self.size == other.size
                or (optional_size and (self.size is None or other.size is None))
            )
            and (
                self.mtime == other.mtime
                or (optional_mtime and (self.mtime is None or other.mtime is None))
            )
        )

    def __eq__(self, other):
        if not isinstance(other, PartialStats):
            return NotImplemented

        return self.match(other)

    def __repr__(self):
        values = []
        for value in (self.hash, self.size, self.mtime):
            values.append("*" if value is None else repr(value))

        values_str = ", ".join(values)

        return f"PartialStats({values_str})"


def iglob_folder(dirpath, pattern):
    """Simple non-recursive glob that does not ignore filesystem errors."""
    pattern = pattern.lower()

    filepaths = []
    for it in dirpath.iterdir():
        if fnmatch.fnmatch(it.name.lower(), pattern):
            filepaths.append(it)

    filepaths.sort()
    return filepaths


def collect_files(root):
    """Recursively returns PartialStats (mtime and size) for all files in a folder."""

    result = {}
    root = Path(root)
    for (dirpath, _dirnames, filenames) in os.walk(root):
        dirpath = Path(dirpath)

        for filename in filenames:
            filepath = dirpath / filename

            result[filepath] = PartialStats.from_filepath(filepath)

    if not result:
        if os.path.isfile(root):
            return {Path(root): PartialStats.from_filepath(root)}
        elif not os.path.exists(root):
            raise FileNotFoundError(root)

    return result


def md5_hash(filename, block_size=256 * 1024):
    """Returns base16 encoded MD5 hash for file"""
    with open(filename, "rb") as handle:
        size = 0
        hasher = hashlib.new("md5")
        block = handle.read(block_size)
        while block:
            hasher.update(block)
            size += len(block)
            block = handle.read(block_size)

        return hasher.hexdigest().upper()


def try_makedirs(path):
    """makedirs wrapper; returns true if a new folder was created, false otherwise"""
    try:
        os.makedirs(path)

        return True
    except OSError as error:
        if error.errno == errno.EEXIST:
            return False

        raise


def collect_md5_hashes(root, cache=None, timeout=10 * 60):
    pool = multiprocessing.Pool(1, init_worker_process)
    cache = cache or {}

    try:
        async_result = pool.apply_async(collect_files, (root,))

        try:
            filestats = async_result.get(timeout)
        except multiprocessing.TimeoutError:
            raise multiprocessing.TimeoutError("timeout while collecting files")

        result = {}
        for filepath, stats in filestats.items():
            stats.hash = _calcualate_md5_hash(
                pool=pool,
                filepath=filepath,
                stats=stats,
                cache=cache,
                timeout=timeout,
            )

            result[filepath] = stats

        return result
    finally:
        pool.terminate()


def calculate_md5_hashes(filepaths, cache=None, timeout=10 * 60):
    pool = multiprocessing.Pool(1, init_worker_process)
    cache = cache or {}

    try:
        result = {}
        for filepath in filepaths:
            async_result = pool.apply_async(PartialStats.from_filepath, (filepath,))

            try:
                stats = async_result.get(timeout)
            except multiprocessing.TimeoutError:
                raise multiprocessing.TimeoutError(f"stats timed out for {filepath}")

            stats.hash = _calcualate_md5_hash(
                pool=pool,
                filepath=filepath,
                stats=stats,
                cache=cache,
                timeout=timeout,
            )

            result[filepath] = stats

        return result
    finally:
        pool.terminate()


def _calcualate_md5_hash(pool, filepath, stats, cache, timeout):
    cached_stats = cache.get(filepath)
    # Compares based on size and mtime, since hash is not set for 'stats'
    if cached_stats is not None and cached_stats.match(stats, optional_hash=True):
        if cached_stats.hash:
            return cached_stats.hash

    async_result = pool.apply_async(md5_hash, (filepath,))

    try:
        return async_result.get(timeout)
    except multiprocessing.TimeoutError:
        raise multiprocessing.TimeoutError(f"timeout while hashing '{filepath}'")


def init_worker_process():
    """Init function for subprocesses created by multiprocessing.Pool: Ensures that
    KeyboardInterrupts only occur in the main process, allowing for proper cleanup.
    """
    signal.signal(signal.SIGINT, signal.SIG_IGN)
