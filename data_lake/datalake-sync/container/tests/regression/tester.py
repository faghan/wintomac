#!/usr/bin/env python3
# -*- coding: utf8 -*-
import argparse
import datetime
import getpass
import hashlib
import inspect
import json
import logging
import os
import random
import re
import shutil
import subprocess
import sys
import time
import traceback

from pathlib import Path

# Dummy azure identifiers
AZURE_TENANT_ID = "15fb0f5f-d60c-4f96-aeae-6fcf4777af5d"
AZURE_APPLICATION_ID = "e65bfd60-8b35-4ed6-bbd0-af3bbe027d66"


# Default minimum and maximum for randomly generated files
_RNG_SIZE_MIN = 512
_RNG_SIZE_MAX = 4 * _RNG_SIZE_MIN

# Default minimum age for randomly generated files (hours)
_RNG_AGE_MIN = 24
# How much older a file is allowed to be, relative to the min age
_RNG_AGE_RANGE = 12

_HOSTS = ("main", "alt", "azure")

_RE_PARAM = re.compile(r"^\${[A-Z]+}$")


class HelpFormatter(argparse.ArgumentDefaultsHelpFormatter):
    """Help formatter with default values and word-wrapping."""

    def __init__(self, *args, **kwargs):
        kwargs.setdefault("width", 79)

        super().__init__(*args, **kwargs)


class MemoryHandler(logging.Handler):
    """Implements logging using an in-memory stream."""

    _format_date = logging.Formatter("%(asctime)s").format
    _format_name = logging.Formatter("%(name)s").format
    _format_level = logging.Formatter("%(levelname)s").format
    _format_msg = logging.Formatter("%(message)s").format

    def __init__(self, destination):
        logging.Handler.__init__(self)
        self._records = destination

    def emit(self, record):
        self._records.append(
            {
                "date": self._format_date(record),
                "name": self._format_name(record),
                "level": self._format_level(record),
                "msg": self._format_msg(record),
            }
        )


def rand(rng=random.Random()):
    return rng.random()


def randint(min, max, rng=random.Random()):
    return rng.randint(min, max)


def random_bytes(size):
    return bytes(randint(0, 255) for _ in range(size))


def hash_bytes(data):
    hasher = hashlib.new("md5")
    hasher.update(data)

    return hasher.hexdigest()


def update_path(state, value):
    return (
        str(value)
        .replace("${MAIN}", state["root:main"])
        .replace("${ALT}", state["root:alt"])
    )


def get_self_action(obj, name, params):
    func = getattr(obj, f"_action_{name}", None)
    if func is None:
        raise TestError(f"unknown call {name!r} in action")

    signature = inspect.signature(func)
    for key in params:
        if key not in signature.parameters:
            raise TestError(f"unexpected '{name}' argument {key!r}")

    return func


########################################################################################


class FileBlob:
    def __init__(self, size=None, age=None):
        self.size = randint(_RNG_SIZE_MIN, _RNG_SIZE_MAX) if size is None else int(size)
        self.data = random_bytes(self.size)
        self.hash = hash_bytes(self.data)

        if age is None:
            age = _RNG_AGE_MIN * 60 * 60
            age += _RNG_AGE_RANGE * 60 * 60 * rand()
        else:
            age = float(age) * 60 * 60

        self.mtime = datetime.datetime.now().timestamp() - age

    def write_local(self, filepath):
        if filepath.exists():
            raise FileExistsError(f"local file already exists: {filepath!r}")

        filepath.parent.mkdir(parents=True, exist_ok=True)
        filepath.write_bytes(self.data)

        os.utime(filepath, (self.mtime, self.mtime))

    def write_remote(self, state, filepath):
        state[str(filepath)] = {"size": self.size, "hash": self.hash}


########################################################################################


class TestError(Exception):
    pass


class TestAction:
    def __init__(self, data):
        self.call = data.pop("call", None)
        if self.call is None:
            raise TestError("no call specified for action")
        elif not isinstance(self.call, str):
            raise TestError(f"call must be str in action, not {self.call!r}")

        self.params = data
        self.func = get_self_action(self, self.call, self.params)

    def serialize(self):
        data = dict(self.params)
        data["call"] = self.call

        return data

    def trigger(self, state):
        return self.func(state=state, **self.params)

    @staticmethod
    def _action_sync(state, source, destination):
        storage = state["storage"]
        source = Path(update_path(state, source))
        destination = Path(destination)

        for it in source.iterdir():
            if it.is_file():
                key = str(destination / it.name)
                data = it.read_bytes()

                storage[key] = {"hash": hash_bytes(data), "size": len(data)}
            elif it.is_dir():
                TestAction._action_sync(state, it, destination / it.name)

        return True

    @staticmethod
    def _action_copy(state, source, destination):
        storage = state["storage"]
        source = Path(update_path(state, source))
        data = Path(source).read_bytes()

        storage[destination] = {"hash": hash_bytes(data), "size": len(data)}

        return True

    @staticmethod
    def _action_list_md5s(state, source):
        # Source is expected to be a folder to match azcopy behavior
        source = source.rstrip("/") + "/"
        for key, value in state["storage"].items():

            if key.startswith(source):
                relative_path = key[len(source) :]

                print(
                    "MD5: {}\t{}\t{}".format(
                        value["hash"], value["size"], relative_path
                    )
                )

        return True

    @staticmethod
    def _action_get_md5(state, source):
        # Exact match expected for 'get_md5'
        value = state["storage"].get(source)
        if value is None:
            sys.stdout.write("X-Ms-Error-Code: [BlobNotFound]")

            return False

        print("MD5: {}\t{}\t{}".format(value["hash"], value["size"], source))

        return True

    @staticmethod
    def _action_scramble(state, destination):
        if isinstance(destination, str):
            destination = [destination]

        storage = state["storage"]
        for filename in destination:
            blob = FileBlob()
            blob.write_remote(storage, filename)

        return True

    @staticmethod
    def _action_remove(state, destination):
        storage = state["storage"]
        if destination not in storage:
            sys.stdout.write("X-Ms-Error-Code: [BlobNotFound]")

            return False

        storage.pop(destination)

        return True

    @staticmethod
    def _action_rmdir(state, destination):
        destination = Path(update_path(state, destination))
        if not destination.is_dir():
            raise TestError(f"{destination!r} is not a directory")

        destination.rmdir()
        return True

    @staticmethod
    def _action_touch(state, destination, age=0):
        destination = update_path(state, destination)
        mtime = time.time() - age * 60 * 60

        if not os.path.exists(destination):
            raise TestError("action 'touch' cannot create file files ({destination})")

        os.utime(destination, (mtime, mtime))

        return True


class TestEventTemplates:
    CONTAINER = "container"
    DESTINATION = "destination"
    ROOT_URL = f"https://storage.blob.core.windows.net/{CONTAINER}/{DESTINATION}"

    @classmethod
    def event_from_template(cls, data):
        name = data.pop("template")
        pre_actions = data.pop("pre_actions", ())
        post_actions = data.pop("post_actions", ())
        return_code = data.pop("return_code", None)

        func = get_self_action(cls, name, data)

        event = func(**data)

        actions = []
        actions.extend(pre_actions)
        actions.extend(event.pop("actions", []))
        actions.extend(post_actions)

        event["actions"] = actions
        if return_code is not None:
            event["return_code"] = return_code

        return event

    @classmethod
    def _action_copy(cls, source, destination):
        return {
            "call": [
                "azure-storage-azcopy",
                "copy",
                "--log-level",
                "WARNING",
                "--put-md5",
                f"{source}",
                f"{cls.ROOT_URL}/{destination}",
            ],
            "actions": [
                {
                    "call": "copy",
                    "source": f"{source}",
                    "destination": f"{cls.DESTINATION}/{destination}",
                }
            ],
        }

    @classmethod
    def _action_get_md5(cls, filename):
        return {
            "call": [
                "azure-storage-azcopy",
                "get_md5",
                f"{cls.ROOT_URL}/{filename}",
            ],
            "actions": [
                {
                    "call": "get_md5",
                    "source": f"{cls.DESTINATION}/{filename}",
                }
            ],
        }

    @classmethod
    def _action_login(cls):
        return {
            "call": [
                "azure-storage-azcopy",
                "login",
                f"--tenant-id={AZURE_TENANT_ID}",
                "--service-principal",
                f"--application-id={AZURE_APPLICATION_ID}",
            ]
        }

    @classmethod
    def _action_list_md5s(cls, destination):
        return {
            "call": [
                "azure-storage-azcopy",
                "list_md5s",
                f"{cls.ROOT_URL}/{destination}",
            ],
            "actions": [
                {
                    "call": "list_md5s",
                    "source": f"{cls.DESTINATION}/{destination}",
                }
            ],
        }

    @classmethod
    def _action_logout(cls):
        return {"call": ["azure-storage-azcopy", "logout"]}

    @classmethod
    def _action_remove(cls, destination):
        return {
            "call": [
                "azure-storage-azcopy",
                "remove",
                "--log-level",
                "WARNING",
                f"{cls.ROOT_URL}/{destination}",
            ],
            "actions": [
                {
                    "call": "remove",
                    "destination": f"{cls.DESTINATION}/{destination}",
                }
            ],
        }

    @classmethod
    def _action_sync(cls, source, destination):
        return {
            "call": [
                "azure-storage-azcopy",
                "sync",
                "--log-level",
                "WARNING",
                "--put-md5",
                "--delete-destination",
                "false",
                source,
                f"{cls.ROOT_URL}/{destination}",
            ],
            "actions": [
                {
                    "call": "sync",
                    "source": source,
                    "destination": f"{cls.DESTINATION}/{destination}",
                }
            ],
        }


class TestEvent:
    def __init__(self, data):
        if "template" in data:
            data = TestEventTemplates.event_from_template(data)

        self.call = data.pop("call", None)
        if self.call is None:
            raise TestError("no call specified for event")
        elif not isinstance(self.call, list):
            raise TestError(f"call must be list in event, not {self.call!r}")
        elif not all(isinstance(value, str) for value in self.call):
            raise TestError("call must be list of strs, not {self.call!r}")

        self.actions = data.pop("actions", [])
        if not isinstance(self.actions, list):
            raise TestError(f"actions must be list, not {self.actions!r}")

        self.actions = [TestAction(action) for action in self.actions]

        self.return_code = data.pop("return_code", 0)
        if not isinstance(self.return_code, int):
            raise TestError(f"return_code must be int, not {self.return_code!r}")

        if data:
            raise TestError(f"unexpected values in test events: {data!r}")

    def serialize(self):
        return {
            "call": self.call,
            "actions": [action.serialize() for action in self.actions],
            "return_code": self.return_code,
        }


class TestRun:
    def __init__(self, data):
        self.sync = data.pop("sync", None)
        if self.sync is None:
            raise TestError("no value specified for 'sync'")
        elif self.sync not in ("miseq", "nextseq", "proteomics", "metabolomics"):
            raise TestError(f"invalid sync category: {self.sync!r}")

        self.setup = data.pop("setup", None)
        if self.setup is None:
            raise TestError("no value specified for 'setup'")
        elif not isinstance(self.setup, list):
            raise TestError(f"setup must be list, not {self.setup!r}")

        for setup in self.setup:
            if isinstance(setup, list):
                if not all(isinstance(value, str) for value in setup):
                    raise TestError("setup must be strs/lists of strs, not {setup!r}")
            elif not isinstance(setup, str):
                raise TestError("setup must be strs/lists of strs, not {setup!r}")

        self.setup_actions = data.pop("setup_actions", [])
        if not isinstance(self.setup_actions, list):
            raise TestError(f"setup_actions must be list, not {self.setup_actions!r}")

        self.setup_actions = [TestAction(action) for action in self.setup_actions]

        self.events = data.pop("events", None)
        if self.events is None:
            raise TestError("no value specified for 'events'")
        elif not isinstance(self.events, list):
            raise TestError(f"events must be list, not {self.events!r}")

        self.events = [TestEvent(event) for event in self.events]

        self.return_code = data.pop("return_code", 0)
        if not isinstance(self.return_code, int):
            raise TestError(f"return_code must be int, not {self.return_code!r}")

        if data:
            raise TestError(f"unexpected values in test case: {data!r}")

    def setup_test(self, root, test_num, remote_state):
        log = logging.getLogger("setup")
        log.info("setting up local and remote storage")

        root = root.absolute()
        storage_main = root / "storage" / "main"
        storage_alt = root / "storage" / "alt"

        log.info("setting up main storage at '%s'", storage_main)
        storage_main.mkdir(parents=True, exist_ok=True)
        log.info("setting up alt storage at '%s'", storage_alt)
        storage_alt.mkdir(parents=True, exist_ok=True)

        for filenames in self.setup:
            if not isinstance(filenames, list):
                filenames = [filenames]

            blob = FileBlob()
            for filename_with_host in filenames:
                host, filename = filename_with_host.split(":", 1)
                if host == "main":
                    log.info("creating local main file %r", filename)
                    blob.write_local(storage_main / filename)
                elif host == "alt":
                    log.info("creating local alt file %r", filename)
                    blob.write_local(storage_alt / filename)
                elif host == "remote":
                    log.info("creating remote file %r", filename)
                    blob.write_remote(remote_state, filename)
                else:
                    raise ValueError(filename_with_host)

        self._update_directory_mtimes(storage_main)
        self._update_directory_mtimes(storage_alt)

        state = {
            "log": [],
            "call_log": [],
            "failed": False,
            "pending_commands": [event.serialize() for event in self.events],
            "storage": remote_state,
            "root:main": str(storage_main),
            "root:alt": str(storage_alt),
        }

        for action in self.setup_actions:
            log.info("triggering setup action %r", action.call)
            if not action.trigger(state):
                return False

        with (root / f"{test_num:02g}_state.json").open("wt") as handle:
            json.dump(state, handle, indent=2)

        return True

    def run_test(self, args, test_num):
        log = logging.getLogger("run")
        if self.sync in ("miseq", "nextseq"):
            command = "ngs"
        elif self.sync in ("proteomics", "metabolomics"):
            command = self.sync
        else:
            raise ValueError(self.sync)

        log.info("running %s sync using %r command", self.sync, command)
        command = [
            args.executable,
            command,
            "--config",
            args.config,
            "--credentials",
            args.root / "credentials.txt",
            "--pid-file",
            args.root / "test.pid",
            "--state-file",
            args.root / "state.db",
            "--main-folder",
            args.root / "storage" / "main",
        ]

        if self.sync == "nextseq":
            command.extend(("--samplesheet-folder", args.root / "storage" / "alt"))

        env = dict(os.environ)
        env["PATH"] = "{}:{}".format(args.root / "bin", env["PATH"])
        env["FAKE_AZSYNC_STATE"] = args.root / f"{test_num:02g}_state.json"

        log.info("running commmand %r", command)
        proc = subprocess.Popen(
            command,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            env=env,
        )

        stdout, stderr = proc.communicate()
        log.info("commmand returned %i", proc.returncode)

        filepath_out = args.root / f"{test_num:02g}_stdout.txt"
        filepath_err = args.root / f"{test_num:02g}_stderr.txt"

        filepath_out.write_bytes(stdout)
        filepath_err.write_bytes(stderr)

        if proc.returncode != self.return_code:
            log.error("command did not return code %i:", self.return_code)
            self._log_lines(log=log.error, tmpl="%s", filepath=filepath_err)

            return False

        return True

    def teardown_test(self, args, test_num, remote_state):
        log = logging.getLogger("teardown")

        state_filepath = args.root / f"{test_num:02g}_state.json"
        log.info("checking call history in %r", state_filepath)
        with state_filepath.open("rt") as handle:
            state = json.load(handle)

        match_count = 1
        for idx, call in enumerate(state["call_log"], start=1):
            if match_call(call["expected"], call["received"]) is not None:
                log.info("  %03i. Command OK: %r", idx, call["expected"])
                match_count += 1
            elif call["received"] is not None:
                if call["expected"] is not None:
                    log.error(" %03i. Wrong command received:", idx)
                    log.error("      Expected = %r", call["expected"])
                    log.error("      Received = %r", call["received"])
                else:
                    log.error(" ???. Unexpected command received: %r", call["received"])
            elif call["received"]:
                log.error(
                    " %03i. Unexpected command received: %r", idx, call["received"]
                )

        if state["pending_commands"]:
            log.error("Not all commands received:")
            for idx, call in enumerate(state["pending_commands"], start=match_count):
                log.error(" %03i. %r", idx, call["call"])

        if state["failed"]:
            log.info("Mock command log messages:")
            for idx, record in enumerate(state["log"], start=1):
                log.info("  %03i. %s %s", idx, record["level"], record["msg"])

            return False
        elif state["pending_commands"]:
            return False

        # Update remote file system for next test
        remote_state.clear()
        remote_state.update(state["storage"])

        return True

    @classmethod
    def _update_directory_mtimes(cls, root):
        mtime = 0
        for it in root.iterdir():
            if it.is_file():
                mtime = max(mtime, it.stat().st_mtime)
            else:
                mtime = max(mtime, cls._update_directory_mtimes(it))

        if mtime:
            os.utime(root, (mtime, mtime))

        return mtime

    @staticmethod
    def _log_lines(log, tmpl, filepath, nlines=10):
        with filepath.open("rt") as handle:
            lines = handle.readlines()

        for line in lines[-nlines:]:
            log(tmpl, line.rstrip())


class TestRunner:
    def __init__(self, tests):
        if not isinstance(tests, list):
            raise TestError(f"expected list of tests, got {type(tests).__name__}")

        self.tests = [TestRun(test) for test in tests]

    def run(self, args):
        errors = False
        remote_state = {}
        error_template = "%s failed for test %s of {}; aborting".format(len(self.tests))

        log = logging.getLogger("runner")
        for test_num, test in enumerate(self.tests, start=1):
            if not test.setup_test(args.root, test_num, remote_state):
                log.error(error_template, "setup", test_num)
                errors = True
                break

            if not test.run_test(args, test_num):
                log.error(error_template, "azsync", test_num)
                errors = True

            if not test.teardown_test(args, test_num, remote_state):
                log.error(error_template, "validation", test_num)
                errors = True
                break

            log.info("Test %s of %s completed successfully!", test_num, len(self.tests))

        return not errors


########################################################################################


def match_call(expected, received):
    params = {}
    if expected is None or received is None or len(expected) != len(received):
        return None

    for expected, received in zip(expected, received):
        if expected != received:
            if _RE_PARAM.match(expected) and expected not in ("${MAIN}", "${ALT}"):
                params[expected] = received
            else:
                return None

    return params


def mock_call(state, argv):
    log = logging.getLogger("mock")

    if state["failed"]:
        log.error("post-failure command %r", argv)
        state["call_log"].append({"received": argv, "expected": None})

        return 1
    elif not state["pending_commands"]:
        log.error("received unexpected command %r", argv)

        state["call_log"].append({"received": argv, "expected": None})
        state["failed"] = True

        return 1

    command = state["pending_commands"][0]
    expected = [update_path(state, value) for value in command["call"]]

    argv = [update_path(state, value) for value in argv]
    match = match_call(expected, argv)
    if match is None:
        log.error("received wrong command %r; expected %r", argv, expected)

        state["call_log"].append({"received": argv, "expected": expected})
        state["failed"] = True

        return 1

    log.info("received command %r", argv)
    state["call_log"].append({"received": argv, "expected": expected})

    return_code = None
    command = state["pending_commands"].pop(0)
    for action in command.get("actions", ()):
        action = TestAction(dict(action))

        for key, value in action.params.items():
            if isinstance(value, str):
                value = match.get(value, value)

            action.params[key] = value

        if not action.trigger(state):
            return_code = 255

    if return_code is None:
        return_code = command.get("return_code", return_code)

    log.info("exiting with return code %i", return_code)
    return return_code


def mock_main(argv):
    state_filename = os.environ.get("FAKE_AZSYNC_STATE")
    if state_filename is None:
        sys.stderr.write("FAKE_AZSYNC_STATE not set; aborting ..\n")
        return 1

    with open(state_filename, "rt") as handle:
        state = json.load(handle)

    # Log messages to state file, keeping mock output to a minimum
    handler = MemoryHandler(state["log"])
    root = logging.getLogger()
    root.setLevel(logging.DEBUG)
    root.addHandler(handler)

    try:
        return_code = mock_call(state, argv)
    except Exception as error:
        root.error("%s", traceback.format_exc())
        sys.stderr.write(f"unhandled {error!r}; aborting ..\n")
        state["failed"] = True
        return_code = 255

    with open(state_filename, "wt") as handle:
        json.dump(state, handle, indent=2)

    return return_code


########################################################################################


def cli_parse_args():
    parser = argparse.ArgumentParser(formatter_class=HelpFormatter)
    parser.add_argument(
        "--config",
        type=Path,
        metavar="INI",
        required=True,
        help="Path to sync_to_azure config.ini file",
    )
    parser.add_argument(
        "--test",
        type=Path,
        metavar="JSON",
        required=True,
        help="Path to JSON file describing sync_to_azure test",
    )

    parser.add_argument(
        "--root",
        type=Path,
        default=Path("/tmp/") / getpass.getuser() / "azsync",
        metavar="PATH",
        help="Root output folder for session",
    )

    parser.add_argument(
        "--executable",
        default="sync_to_azure",
        metavar="EXE",
        help="Path to 'sync_to_azure' executable",
    )

    return parser


def cli_main(argv):
    parser = cli_parse_args()
    args = parser.parse_args(argv)

    try:
        import coloredlogs

        coloredlogs.install(
            level=logging.INFO,
            fmt="%(asctime)s %(name)s %(levelname)s %(message)s",
            datefmt="%H:%M:%S",
        )
    except ModuleNotFoundError:
        logging.basicConfig(
            level=logging.INFO,
            format="%(asctime)s %(name)s %(levelname)s %(message)s",
            datefmt="%H:%M:%S",
        )

    log = logging.getLogger("main")
    if not shutil.which(args.executable):
        log.error("executable %r not found", args.executable)
        return 1
    elif not args.config.exists():
        log.error("config ini-file not found at %r", args.config)
        return 1
    elif not args.test.exists():
        log.error("test template not found at %r", args.test)
        return 1

    log.info("loading test template from %r", args.test)
    with args.test.open("rt") as handle:
        tests = json.load(handle)

    runner = TestRunner(tests)

    if args.root.exists():
        log.info("Removing old temp dir at %r", args.root)
        shutil.rmtree(args.root)

    # Create fake credentials file
    args.root.mkdir(parents=True, exist_ok=True)
    (args.root / "credentials.txt").write_text("fake-credentials-for-azsync")

    # Create bin folder with mock executables
    bin_dir = args.root / "bin"
    bin_dir.mkdir(parents=True, exist_ok=True)
    log.info("creating mock executable at %r", bin_dir / "azure-storage-azcopy")
    (bin_dir / "azure-storage-azcopy").symlink_to(Path(__file__).absolute())

    if not runner.run(args):
        return 1

    return 0


########################################################################################


def main(argv):
    executable = Path(__file__)
    if executable.is_symlink():
        return mock_main([executable.name] + argv)

    return cli_main(argv)


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
