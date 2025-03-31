#!/usr/bin/env python3
# -*- coding: utf8 -*-
import logging
import os
import re
import subprocess

from pathlib import Path

from .fileutils import PartialStats


EXECUTABLE = "azure-storage-azcopy"


BLOB_NOT_FOUND = "BlobNotFound"
UNKNOWN_ERROR = "__UnknownError__"
NOT_AUTHENTICATED = "__NotAuthenticated__"


AZCOPY_LOG_LEVELS = ("NONE", "DEBUG", "INFO", "WARNING", "ERROR", "PANIC", "FATAL")


def _require_login(func):
    def _inner(self, *args, **kwargs):
        self.login()

        return func(self, *args, **kwargs)

    return _inner


class AZError(RuntimeError):
    def __init__(self, error_code):
        super().__init__(error_code.strip("_"))
        self.error_code = error_code


class AZLoginError(AZError):
    pass


class AZNotAuthenticatedError(AZLoginError):
    def __init__(self, _error):
        message = (
            "{}. Try running 'keyctl session' before sync_to_azure, if the client "
            "succesfully authenticated prior to this failure (see also README.md)."
        ).format(_NOT_AUTHENTICATED.decode("utf-8"))

        super().__init__(message)


class AZFileNotFoundError(AZError):
    pass


class AZUnknownError(AZError):
    def __init__(self):
        super().__init__(UNKNOWN_ERROR)


_AZCOPY_ERRORS = {
    NOT_AUTHENTICATED: AZNotAuthenticatedError,
    BLOB_NOT_FOUND: AZFileNotFoundError,
}


#######################################################################################


class AZCopy:
    def __init__(self, tenant_id, app_id, secret):
        self._log = logging.getLogger(__name__)

        if not (tenant_id and tenant_id.strip()):
            raise ValueError("no tenant ID specified for AZCopy session")
        if not (app_id and app_id.strip()):
            raise ValueError("no app ID specified for AZCopy session")
        if not (secret and secret.strip()):
            raise ValueError("no client secret specified for AZCopy session")

        self._logged_in = False
        self._tenant_id = tenant_id.strip()
        self._app_id = app_id.strip()
        self._secret = secret.strip()
        self._log_level = None

        self.exec = EXECUTABLE

    def set_log_level(self, log_level):
        if log_level not in AZCOPY_LOG_LEVELS:
            raise ValueError(log_level)

        self._log_level = log_level

    def is_logged_in(self):
        """Returns true if login() was successfully called."""
        return self._logged_in

    def login(self):
        """Attempts to login with the provided credentials; returns true on success,
        false otherwise. This operation will be run regardless of the number of the
        number of remaining tries.
        """
        log = logging.getLogger("azcopy.login")
        if self._logged_in:
            log.debug("skipping login; already logged in")
            return True

        log.info("logging in as tenant %r, app %r", self._tenant_id, self._app_id)

        environ = dict(os.environ)
        environ["AZCOPY_SPA_CLIENT_SECRET"] = self._secret

        try:
            self._run_command(
                command=[
                    self.exec,
                    "login",
                    f"--tenant-id={self._tenant_id}",
                    "--service-principal",
                    f"--application-id={self._app_id}",
                ],
                log=log,
                env=environ,
            )
        except AZError as error:
            raise AZLoginError(error.error_code) from error

        self._logged_in = True

        return True

    def logout(self):
        """Attempts to logout from the current session; returns true on success, or if
        the client was already logged out, false otherwise.
        """
        log = logging.getLogger("azcopy.logout")
        if not self._logged_in:
            log.debug("skipping logout; already logged out")
            return True

        log.info("logging out of azure client")
        self._run_command(command=[self.exec, "logout"], log=log)
        self._logged_in = False

    @_require_login
    def copy(self, src_file, dst_url):
        """Attempts to copy local 'src_file' to 'dst_url'; returns true on success and
        false otherwise.
        """
        log = logging.getLogger("azcopy.copy")
        log.info("copying '%s' to %r", src_file, dst_url)

        self._run_command(
            command=self._command("copy", "--put-md5", str(src_file), dst_url),
            log=log,
        )

    @_require_login
    def remove(self, dst_url):
        """Attempts to remove remote file at 'dst_url'; returns true on success and
        false otherwise.
        """
        log = logging.getLogger("azcopy.remove")
        log.info("removing %r", dst_url)

        self._run_command(
            command=self._command("remove", dst_url),
            log=log,
        )

    @_require_login
    def sync(self, src_dir, dst_url, rm_dst=False):
        """Attempts to synchronize local folder 'src_dir' to 'dst_url'; returns true
        on success and false otherwise. If 'rm_dst' is true, files found only at the
        destination will be removed.
        """
        log = logging.getLogger("azcopy.sync")
        log.info("syncing %r to %r", src_dir, dst_url)

        self._run_command(
            command=self._command(
                "sync",
                "--put-md5",
                "--delete-destination",
                "true" if rm_dst else "false",
                src_dir,
                dst_url,
            ),
            log=log,
        )

    @_require_login
    def list_md5s(self, dst_url):
        log = logging.getLogger("azcopy.sync")
        log.info("listing MD5 hashes for %r", dst_url)

        return self._md5s(log, [self.exec, "list_md5s", dst_url])

    @_require_login
    def get_md5(self, dst_url):
        log = logging.getLogger("azcopy.sync")
        log.info("getting MD5 hash for %r", dst_url)

        md5_hashes = self._md5s(log, [self.exec, "get_md5", dst_url])
        if len(md5_hashes) != 1:
            raise AZError(f"get_md5 returned {md5_hashes!r}")

        (value,) = md5_hashes.values()

        return value

    def _md5s(self, log, command):
        """Retrieves a list of filenames, sizes, and MD5 hashes at 'dst_url', and
        returns a dict of {filename: (size, hash)}.
        """
        result = {}
        for line in self._run_command(command, log=log, response_prefix="MD5: "):
            line = line[5:]
            # Note that MD5 may be an empty string here, which is treated differently
            # from None (i.e. not a wildcard). See PartialStats.__eq__.
            md5, size, filename = (value.strip() for value in line.split("\t", 2))

            # Path normalizes server (posix) and client (posix or Windows) paths
            result[Path(filename)] = PartialStats(size=int(size), hash=md5.upper())

        return result

    @classmethod
    def _run_command(cls, command, log, response_prefix=None, **kwargs):
        log.debug("running command %r", command)
        proc = _popen(command, **kwargs)

        lines = []
        log_lines = []
        error = None

        for line in proc.stdout:
            # Progress updates stars with a carriage return; these are excluded to
            # avoid bloating the file/memory log with a large amount of noise
            if line.startswith(b"\r"):
                continue

            error_code = _ERROR_CODE_RE.search(line)
            if error_code:
                (error,) = error_code.groups()
                error = error.decode("utf-8")
            elif _NOT_AUTHENTICATED in line:
                error = NOT_AUTHENTICATED

            line = line.decode("utf-8").strip()
            if response_prefix and line.startswith(response_prefix):
                lines.append(line)
            else:
                log_lines.append(line)

        proc.wait()

        loglevel = logging.DEBUG
        if proc.returncode:
            loglevel = logging.WARNING if error is None else logging.DEBUG

        log.log(loglevel, "finished running command %r", command)
        log.log(loglevel, "command returned %i", proc.wait())

        shelllog = logging.getLogger(log.name + ".shell")
        for line in log_lines:
            line = line.rstrip()
            if line:
                shelllog.log(loglevel, "%s", line)

        if proc.returncode:
            if error is None:
                raise AZUnknownError()

            raise _AZCOPY_ERRORS.get(error, AZError)(error)

        return lines

    def _command(self, subcommand, *args):
        call = [self.exec, subcommand]
        if self._log_level is not None:
            call.append("--log-level")
            call.append(self._log_level)

        call.extend(args)

        return call

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc_value, traceback):
        if not isinstance(exc_value, AZLoginError):
            self.logout()


def _popen(command, env=None):
    return subprocess.Popen(
        command,
        stdin=subprocess.DEVNULL,
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
        env=env,
    )


_ERROR_CODE_RE = re.compile(rb"X-Ms-Error-Code: \[(\w+)\]")
_NOT_AUTHENTICATED = (
    b"no SAS token or OAuth token is present and the resource is not public"
)
