#!/usr/bin/env python3
# -*- coding: utf8 -*-
import fnmatch
import logging
import sys
import time
import html

from pathlib import Path

import coloredlogs
import configargparse
import humanfriendly
import requests

_REQUIRED_FILES = (
    "results.xlsx",
    "metadata.xlsx",
)


def trigger_webhook(webhook, text, nincomplete):
    """
    See reference at
      https://docs.microsoft.com/en-us/outlook/actionable-messages/message-card-reference

    Visualize output at
      https://messagecardplayground.azurewebsites.net/
    """
    title = f"Found {nincomplete} incomplete Benchling proteomics requests"

    data = {
        "@type": "MessageCard",
        "@context": "https://schema.org/extensions",
        "summary": title,
        "themeColor": "E81123",
        "sections": [
            {"startGroup": True, "activityTitle": title, "activityText": text}
        ],
    }

    requests.post(webhook, json=data).raise_for_status()


def iglob_folder(dirpath, pattern):
    """Simple non-recursive glob that does not ignore filesystem errors."""
    pattern = pattern.lower()

    filepaths = []
    for it in dirpath.iterdir():
        if fnmatch.fnmatch(it.name.lower(), pattern):
            filepaths.append(it)

    filepaths.sort()
    return filepaths


def get_newest_timestamp(dirpath):
    newest_timestamp = float("-inf")
    for it in dirpath.iterdir():
        newest_timestamp = max(newest_timestamp, it.stat().st_mtime)

        if it.is_dir():
            newest_timestamp = max(newest_timestamp, get_newest_timestamp(it))

    return newest_timestamp


def parse_args(argv):
    parser = configargparse.ArgumentParser(
        allow_abbrev=False,
        formatter_class=configargparse.ArgumentDefaultsHelpFormatter,
    )

    parser.add_argument(
        "--root",
        type=Path,
        required=True,
        help="Folder containing proteomics request folders",
    )

    parser.add_argument(
        "--project-glob",
        help="Glob used to select project sub-folders in the `root` folder",
        default="prot[0-9]*",
        type=str.lower,
    )

    parser.add_argument(
        "--config",
        help="Read command-line options from this file (see above)",
        type=Path,
        is_config_file=True,
    )
    parser.add_argument(
        "--webhook",
        required=True,
        help="URL to Microsoft Teams webhook",
    )
    parser.add_argument(
        "--log-level",
        type=str.upper,
        default="INFO",
        choices=("DEBUG", "INFO", "WARNING", "ERROR", "CRITICAL"),
    )
    parser.add_argument(
        "--log-file",
        type=Path,
        help="If set, log messages ar ewritten to this file",
    )

    return parser.parse_args(argv)


def main(argv):
    args = parse_args(argv)
    coloredlogs.install(
        level=args.log_level,
        fmt="%(asctime)s %(name)s %(levelname)s %(message)s",
    )

    folders = []
    ncomplete = 0
    log = logging.getLogger("monitor-proteomics")
    for it in iglob_folder(args.root, args.project_glob):
        if it.is_dir():
            if all((it / filename).exists() for filename in _REQUIRED_FILES):
                log.info("Found completed project %r", it.name)
                ncomplete += 1
                continue

            for fpath in it.iterdir():
                if fpath.suffix.lower() == ".raw" and fpath.is_file():
                    break
            else:
                log.info("Skipping project without any results %r", it.name)
                continue

            log.info("Found incomplete project %r", it.name)
            folders.append((get_newest_timestamp(it), it))

    if not folders:
        log.info("No incomplete projects found")
        return 0

    lines = ["<ul>"]
    for timestamp, it in sorted(folders):
        lines.append(
            "  <li><b>{}</b> last updated {} ago</li>".format(
                html.escape(it.name),
                html.escape(humanfriendly.format_timespan(time.time() - timestamp)),
            )
        )
    lines.append("</li>")

    log.info("Sending message to Teams")
    trigger_webhook(
        webhook=args.webhook, text="\n".join(lines), nincomplete=len(folders)
    )

    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
