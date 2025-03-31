import logging
import multiprocessing
import shutil
import tempfile

from pathlib import Path

from .fileutils import collect_md5_hashes, calculate_md5_hashes
from .utilities import urljoin, urlquote

from .azcopy import AZFileNotFoundError

TRIES = 5


class CheckedSync:
    def __init__(self, src_dir, dst_url, rm_dst=False, timeout=10 * 60):
        _typecheck("src_dir", src_dir, (str, Path))
        _typecheck("dst_url", dst_url, str)
        _typecheck("rm_dst", rm_dst, int)
        _typecheck("timeout", timeout, int)

        self.src_dir = src_dir
        self.dst_url = dst_url
        self.rm_dst = rm_dst
        self.timeout = timeout

    def execute(self, client, tries=TRIES):
        log = logging.getLogger(__name__)

        local_hashes = {}
        all_hashes_validated = False
        while tries > 0 and not all_hashes_validated:
            # Synchronize folder using 'azcopy sync'
            client.sync(self.src_dir, self.dst_url, rm_dst=self.rm_dst)

            try:
                # Collect sizes/hashes from sequencing machine; a failure due to a
                # timeout is considered a fatal error since we cannot predict when
                # the drive will become available (typically within a few hours).
                local_hashes = collect_md5_hashes(
                    self.src_dir, cache=local_hashes, timeout=self.timeout
                )
            except multiprocessing.TimeoutError as error:
                log.error("timeout while hashing files at %r: %r", self.src_dir, error)
                return False

            # Collect sizes/hashes from Azure
            remote_hashes = client.list_md5s(dst_url=self.dst_url)

            all_hashes_validated = True
            # Compare hashes and remove mismatching files
            for filepath, local_hash in sorted(local_hashes.items()):
                filepath = filepath.relative_to(self.src_dir)
                remote_hash = remote_hashes.pop(filepath, None)

                if remote_hash is None:
                    all_hashes_validated = False
                    log.warning("md5 not found on Azure for '%s'", filepath)
                elif not local_hash.match(remote_hash, optional_mtime=True):
                    all_hashes_validated = False
                    log.warning("md5 mismatch for '%s'", filepath)
                    log.debug("local = md5s %s, remote = %s", local_hash, remote_hash)

                    client.remove(dst_url=urljoin(self.dst_url, urlquote(filepath)))

            if not all_hashes_validated:
                # Ensure that the sync-loop will not repeat infinitly in case of any
                # problem causing inconsistant results between local and remote
                log.warning("inconsistent local/remote; retrying sync if possible")
                tries -= 1
            elif remote_hashes and self.rm_dst:
                log.warning(
                    "%i extra remote files; re-syncing to remove",
                    len(remote_hashes),
                )
                all_hashes_validated = False
                tries -= 1

        return tries

    def __repr__(self):
        values = [self.src_dir, self.dst_url, self.rm_dst, self.timeout]
        values_str = ", ".join(repr(value) for value in values)

        return f"CheckedSync({values_str})"


class CheckedCopy:
    def __init__(self, src_file, dst_url, timeout=10 * 60):
        _typecheck("src_file", src_file, (str, Path))
        _typecheck("dst_url", dst_url, str)
        _typecheck("timeout", timeout, int)

        self.src_file = src_file
        self.dst_url = dst_url
        self.timeout = timeout
        self.filestats = None

    def execute(self, client, tries=TRIES):
        first_loop = True
        local_hashes = {}
        self.filestats = None
        log = logging.getLogger(__name__)

        while tries > 0:
            try:
                # Collect sizes/hashes from network drive
                local_hashes = collect_md5_hashes(
                    self.src_file, cache=local_hashes, timeout=self.timeout
                )
            except multiprocessing.TimeoutError as error:
                log.error("timeout while hashing files at %r: %r", self.src_file, error)
                return 0

            if len(local_hashes) != 1:
                log.error("expected 1 hash for %r, got %r", self.src_file, local_hashes)
                return 0

            (local_hash,) = local_hashes.values()

            try:
                # Collect sizes/hashes from Azure
                remote_hash = client.get_md5(dst_url=self.dst_url)
                if local_hash.match(remote_hash, optional_mtime=True):
                    break
            except AZFileNotFoundError:
                # First check is expected to fail with BlobNotFound, but not the next
                if not first_loop:
                    raise
            else:
                log.warning("md5 mismatch for %r", self.src_file)
                log.debug("local = md5s %s, remote = %s", local_hash, remote_hash)
                if not first_loop:
                    tries -= 1

            client.copy(self.src_file, self.dst_url)
            first_loop = False

        if local_hashes:
            (self.filestats,) = local_hashes.values()

        return tries

    def __repr__(self):
        values = [self.src_file, self.dst_url, self.timeout]
        values_str = ", ".join(repr(value) for value in values)

        return f"CheckedCopy({values_str})"


class CheckedMultiCopy:
    def __init__(self, file_map, dst_url, timeout=10 * 60):
        _typecheck("file_map", file_map, dict)
        _typecheck("dst_url", dst_url, str)
        _typecheck("timeout", timeout, int)

        self.file_map = {}
        self.dst_url = dst_url
        self.timeout = timeout
        self.filestats = None

        for key, value in file_map.items():
            _typecheck("file_map key", key, (Path, str))
            _typecheck("file_map value", value, (Path, str))

            self.file_map[Path(key)] = Path(value)

    def execute(self, client, tries=TRIES):
        log = logging.getLogger(__name__)
        self.filestats = None
        first_loop = True

        while tries > 0:
            try:
                # Collect sizes/hashes from network drive
                self.filestats = calculate_md5_hashes(
                    # sorted() used to allow comparions of mocked calls
                    filepaths=sorted(self.file_map.values()),
                    timeout=self.timeout,
                    cache=self.filestats,
                )
            except multiprocessing.TimeoutError as error:
                log.error("timeout while hashing files: %r", error)
                return 0

            # Collect sizes/hashes from Azure; first check is expected to fail
            remote_hashes = client.list_md5s(self.dst_url)

            upload_queue = {}
            for key, filepath in self.file_map.items():
                local_stats = self.filestats[filepath]
                remote_stats = remote_hashes.get(key)

                if remote_stats is None or not local_stats.match(
                    remote_stats, optional_mtime=True
                ):
                    upload_queue[key] = filepath

            if not upload_queue:
                break
            elif not first_loop:
                tries -= 1

            if tries > 0:
                for key, filepath in sorted(upload_queue.items()):
                    client.copy(filepath, urljoin(self.dst_url, urlquote(key)))

            first_loop = False

        return tries

    def __repr__(self):
        values = [self.file_map, self.dst_url, self.timeout]
        values_str = ", ".join(repr(value) for value in values)

        return f"CheckedMultiCopy({values_str})"


class RemoveLocal:
    def __init__(self, dst):
        _typecheck("dst", dst, (str, Path))

        self.dst = dst

    def execute(self, client, tries=TRIES):
        if tries > 0:
            shutil.rmtree(self.dst)

        return tries

    def __repr__(self):
        return f"RemoveLocal({self.dst!r})"


class RemoveRemote:
    def __init__(self, dst):
        _typecheck("dst", dst, str)

        self.dst = dst

    def execute(self, client, tries=TRIES):
        if tries > 0:
            client.remove(self.dst)
        return tries

    def __repr__(self):
        return f"RemoveRemote({self.dst!r})"


class Write:
    def __init__(self, dst, data):
        _typecheck("dst", dst, str)
        _typecheck("data", data, (bytes, str))

        self.dst = dst
        self.data = data

        if isinstance(self.data, str):
            self.data = self.data.encode("utf-8")

    def execute(self, client, tries=TRIES):
        if tries <= 0:
            return tries

        with tempfile.NamedTemporaryFile() as handle:
            handle.write(self.data)
            handle.flush()

            return CheckedCopy(handle.name, self.dst).execute(client)

    def __repr__(self):
        return f"Write({self.dst!r}, ...)"


def execute(client, tasks, tries=TRIES):
    log = logging.getLogger(__name__)

    for task in tasks:
        log.info("running task %r", task)

        tries = task.execute(client, tries)
        if tries <= 0:
            log.error("Failed to run task %r", task)
            return False

    return True


def _typecheck(name, value, types):
    if not isinstance(value, types):
        raise ValueError(f"invalid task {name} param: {value!r}")
