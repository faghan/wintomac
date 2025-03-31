import io
import uuid

from unittest.mock import call, patch, ANY


from azsync.azcopy import EXECUTABLE


TENANT_ID = str(uuid.uuid4())
APP_ID = str(uuid.uuid4())
SECRET = str(uuid.uuid4())


def default_login_call(executable=EXECUTABLE):
    return call(
        [
            executable,
            "login",
            f"--tenant-id={TENANT_ID}",
            "--service-principal",
            f"--application-id={APP_ID}",
        ],
        env=ANY,
    )


def default_logout_call(executable=EXECUTABLE):
    return call([executable, "logout"])


class PopenMock:
    def __init__(self, returncode=0, stdout=()):
        self._returncode = returncode
        self.returncode = None
        self.stdout = io.BytesIO("\n".join(stdout).encode("utf-8"))

    def wait(self):
        self.returncode = self._returncode
        return self.returncode

    @staticmethod
    def patch(autospec=False):
        return patch(
            "azsync.azcopy._popen", autospec=autospec, spec=not autospec, spec_set=True
        )


class Untouchable:
    """Class used for dummy values that are not expected to be touched."""

    def __str__(self):
        raise NotImplementedError("Untouchable.__str__")

    def __repr__(self):
        raise NotImplementedError("Untouchable.__repr__")

    def __eq__(self, other):
        raise NotImplementedError("Untouchable.__eq__")

    def __setattr__(self, *args, **kwargs):
        raise NotImplementedError("Untouchable.__setattr__")
