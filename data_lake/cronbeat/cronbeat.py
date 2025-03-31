#!/usr/bin/env python3
import collections
import configargparse
import datetime
import json
import logging
import os
import resource
import subprocess
import sys
import time
import uuid

from pathlib import Path

import coloredlogs
import humanfriendly
import pid
import requests

_LOGGER = "cronbeat"
_LOG_FORMAT = "%(asctime)s %(name)s %(levelname)s %(message)s"


class HeartBeatMessage:
    def __init__(self):
        self.failures = []
        self.groups = collections.defaultdict(
            lambda: {
                "skipped": 0,
                "completed": {
                    "#": 0,
                    "memory": [],
                    "runtime": [],
                },
                "failed": {
                    "#": 0,
                    "memory": [],
                    "runtime": [],
                },
            }
        )

    def add_task(self, task):
        group = self.groups[task["name"]]

        if task["outcome"] == "busy":
            group["skipped"] += 1
            return

        if task["outcome"] == 0:
            outcome = group["completed"]
        else:
            self.failures.append(task)
            outcome = group["failed"]

        outcome["#"] += 1
        outcome["memory"].append(task["memory"])
        outcome["runtime"].append(task["runtime"])

    def finalize(self):
        title = datetime.date.today().strftime("Task summary for %Y-%m-%d")
        data = {
            "@type": "MessageCard",
            "@context": "https://schema.org/extensions",
            "summary": title,
            "themeColor": "0078D7",
            "title": title,
            "sections": [],
        }

        if self.failures:
            data["sections"].append(self._build_failure_section())

        for name, stats in self.groups.items():
            human_name = name or "Untitled"
            section = {
                "text": f"**{human_name}**",
                "facts": [],
            }

            num_skipped = stats["skipped"]
            if num_skipped:
                section["facts"].append(
                    {
                        "name": "Skipped",
                        "value": f"{num_skipped} tasks due to already running tasks",
                    }
                )

            section["facts"].extend(self._build_task_facts(stats, "failed"))
            section["facts"].extend(self._build_task_facts(stats, "completed"))

            data["sections"].append(section)

        return data

    def _build_task_facts(self, stats, name):
        stats = stats[name]
        if not stats["#"]:
            return ()

        num = stats["#"]
        time = humanfriendly.format_timespan(max(stats["runtime"]), max_units=2)
        mem = humanfriendly.format_size(max(stats["memory"]))

        return (
            {
                "name": name.title(),
                "value": f"{num} tasks in at most {time}, using at most {mem} RAM",
            },
        )

    def _build_failure_section(self):
        data = {
            "text": "**Failures**",
            "facts": [],
        }

        for task in self.failures:
            name = task["name"] or "Untitled"
            timestamp = task["timestamp"].split()[1]

            if isinstance(task["outcome"], str):
                errormsg = f"failed with exception {task['outcome']}"
            else:
                errormsg = f"failed with returncode {task['outcome']}"

            data["facts"].extend(
                (
                    {"name": timestamp, "value": f"{name} {errormsg}, while running"},
                    {"name": " ", "value": "*%s*" % (" ".join(task["commands"][-1]),)},
                )
            )

        return data


class DummyPid:
    def __enter__(self, *args, **kwargs):
        pass

    def __exit__(self, *args, **kwargs):
        pass


class Task:
    def __init__(self, name, options):
        if not isinstance(name, str):
            raise ValueError(f"Expected str, got {name!r}")
        elif not isinstance(options, dict):
            raise ValueError(f"Expected dict, got {options!r}")

        commands = options.pop("commands", [])
        if not isinstance(commands, list):
            raise ValueError(f"'commands' is not a list: {commands!r}")
        elif not commands:
            raise ValueError(f"No commands found for {name!r}")

        for cmd in commands:
            if not isinstance(cmd, list):
                raise ValueError(f"sub-command is not a list: {cmd!r}")
            elif not all(isinstance(value, str) for value in cmd):
                raise ValueError(f"sub-command contains non-string values: {cmd!r}")
            elif not cmd:
                raise ValueError("Empty sub-command found")

        self.pid = options.pop("pid", None)
        if not isinstance(self.pid, str) and self.pid is not None:
            raise ValueError(f"'pid' must be string or null, not {self.pid!r}")

        self.name = name
        self.commands = commands

        log = logging.getLogger(_LOGGER)
        for key in options:
            log.warning("unexpected key %r in options for %r", key, name)

    def lock(self, root):
        if not self.pid:
            return DummyPid()

        return pid.PidFile(self.pid, root)

    @staticmethod
    def from_json_file(filepath):
        with open(filepath, "rb") as handle:
            data = json.load(handle)

        if not isinstance(data, dict):
            raise ValueError(f"Expected dict, found {data!r}")

        tasks = {}
        for key, value in data.items():
            if key.lower() in tasks:
                raise ValueError(f"Multiple tasks with (case-insensitive) name {key!r}")

            tasks[key.lower()] = Task(key, value)

        return tasks


def main_run(args):
    log = logging.getLogger(_LOGGER)
    if not args.library:
        log.error("No task library specified; cannot proceeed")
        return 1
    elif not args.task:
        log.error("No task specified for library %r; cannot proceeed", args.library)
        return 1

    log.info("Reading task %r from library %r", args.task, args.library)

    try:
        tasks = Task.from_json_file(args.library)
    except ValueError as error:
        log.error("Error while loading library: %r", error)
        return 1

    task = tasks.get(args.task.lower())
    if task is None:
        log.error("Task %r not found in library", args.task)
        return 1

    timestamp = datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    start_time = time.time()

    log_lines = []
    max_log_lines = 5

    try:
        with task.lock(args.cache / "pids"):
            commands = []
            for command in task.commands:
                commands.append(command)

                # Allow use of `~` to refer to $HOME
                command = [os.path.expanduser(value) for value in command]

                try:
                    log.info("Running command %r", command)

                    with subprocess.Popen(
                        command,
                        start_new_session=True,
                        stdin=subprocess.DEVNULL,
                        stdout=subprocess.PIPE,
                        stderr=subprocess.STDOUT,
                    ) as proc:
                        for line in proc.stdout:
                            print(line.decode(errors="replace"), end="")

                            log_lines.append(line)
                            if len(log_lines) > max_log_lines:
                                log_lines.pop(0)

                        outcome = proc.wait()
                        log.info("Command completed with return code %r", outcome)
                except (OSError, ValueError) as error:
                    log.error("Command failed with exception %r", error)
                    outcome = str(error)

                if outcome != 0:
                    break

        elapsed = time.time() - start_time
        usage = resource.getrusage(resource.RUSAGE_CHILDREN)
        memory = usage.ru_maxrss * 1024

        log.info(
            "Commands executed in %s, using %s RAM",
            humanfriendly.format_timespan(elapsed, max_units=2),
            humanfriendly.format_size(memory),
        )
    except pid.PidFileError:
        log.warning("task using pid %r is already running, skipping ..", task.pid)

        commands = None
        elapsed = None
        memory = None
        outcome = "busy"

    destination = args.cache / str(uuid.uuid4())
    while destination.exists():
        destination = args.cache / str(uuid.uuid4())

    destination.write_text(
        json.dumps(
            {
                "name": task.name,
                "timestamp": timestamp,
                "commands": commands,
                "runtime": elapsed,
                "memory": memory,
                "outcome": outcome,
                "log": [line.decode(errors="replace") for line in log_lines]
                if outcome != 0
                else None,
            }
        )
    )

    return 0


def main_emit(args):
    log = logging.getLogger(_LOGGER)
    log.info("Emitting completed tasks")

    session = []
    emitted_dir = args.cache / "emitted"
    emitted_dir.mkdir(exist_ok=True, parents=True)

    for filepath in args.cache.iterdir():
        try:
            if filepath.is_file():
                destination = emitted_dir / filepath.name
                filepath.rename(destination)
                session.append(destination)
        except OSError as error:
            log.error("Failed to move task file %r: %r", filepath, error)

    items = []
    for filepath in session:
        log.debug("processing %r", filepath)

        try:
            data = json.loads(filepath.read_text())
        except (OSError, json.JSONDecodeError) as error:
            log.error("Failed to read task file %r: %r", filepath, error)
            continue

        items.append(data)

    message = HeartBeatMessage()
    for task in sorted(items, key=lambda it: it.get("timestamp", "")):
        message.add_task(task)

    response = requests.post(args.webhook, json=message.finalize()).raise_for_status()
    if response.status_code != 200:
        log.error("POST to webhook returned %i", response.status_code)
        return 1

    for filepath in session:
        log.debug("deleting emitted file %r", filepath)
        filepath.unlink()

    return 0


def main_list(args):
    log = logging.getLogger(_LOGGER)
    log.info("Listing completed tasks")

    tasks = []
    for filepath in args.cache.iterdir():
        if filepath.is_file():
            log.debug("processing %r", filepath)

            try:
                tasks.append(json.loads(filepath.read_text()))
            except (OSError, json.JSONDecodeError) as error:
                log.error("Failed to read task file %r: %r", filepath, error)
                continue

    for task in sorted(tasks, key=lambda it: it["timestamp"]):
        outcome = task["outcome"]
        if isinstance(outcome, str):
            outcome = outcome.title()
        elif outcome != 0:
            outcome = f"Failed ({outcome})"
        else:
            outcome = "OK"

        runtime = "N/A"
        if task["runtime"] is not None:
            runtime = humanfriendly.format_timespan(task["runtime"], max_units=2)

        memory = "N/A"
        if task["memory"] is not None:
            memory = humanfriendly.format_size(task["memory"])

        print(
            "\t".join(
                (
                    task["timestamp"],
                    task["name"],
                    outcome,
                    runtime,
                    memory,
                )
            )
        )


def parse_args():
    parser = configargparse.ArgumentParser(
        prog="cronbeat",
        allow_abbrev=False,
        default_config_files=["/etc/cronbeat/*.ini", "~/.cronbeat.ini"],
    )

    parser.add_argument("command", choices=("run", "emit", "list"), type=str.lower)
    parser.add_argument("library", help="Json file describing tasks", nargs="?")
    parser.add_argument("task", help="Name of task to run", nargs="?")

    parser.add_argument("--config", is_config_file=True, help="Path to config file")

    parser.add_argument("--log-file", type=Path, help="Optional path to logfile")
    parser.add_argument(
        "--log-level",
        type=str.upper,
        default="INFO",
        choices=("DEBUG", "INFO", "WARNING", "ERROR", "CRITICAL"),
    )

    parser.add_argument(
        "--cache",
        type=Path,
        default=Path("~/.cronbeat").expanduser(),
        help="Folder in which task beats are saved",
    )

    parser.add_argument("--webhook", help="URL to Teams webhook")

    return parser


def main(argv):
    parser = parse_args()
    args = parser.parse_args(argv)

    coloredlogs.install(level=args.log_level, fmt=_LOG_FORMAT)
    if args.log_file is not None:
        handler = logging.FileHandler(args.log_file)
        handler.setFormatter(logging.Formatter(_LOG_FORMAT))
        logging.getLogger().addHandler(handler)

    args.cache.mkdir(exist_ok=True, parents=True)
    if args.command == "run":
        return main_run(args)
    elif args.command == "emit":
        return main_emit(args)
    elif args.command == "list":
        return main_list(args)

    parser.print_usage()
    return 1


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
