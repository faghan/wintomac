#!/usr/bin/env python3
# -*- coding: utf8 -*-
import hashlib
import logging
import os
import re
import shutil
import subprocess
import sys

from datetime import datetime
from pathlib import Path

import coloredlogs
import configargparse
import requests


# curl is used for simple FTP support
CURL_EXEC = "curl"
# Basic curl command: --fail is used to trigger faiure on 404, --silent and show-error
# hides the progress bar and such, but still shows errors. The --no-progress-meter
# option is not available in older versions of curl
CURL_COMMAND = (CURL_EXEC, "--fail", "--silent", "--show-error")

DEFAULT_MAPPING_URL = (
    "ftp://ftp.ncbi.nlm.nih.gov/refseq/uniprotkb/gene_refseq_uniprotkb_collab.gz"
)

RE_TIMESTAMP_GZ = re.compile(r"\d{8}_\d{6}.tsv.gz")


def trigger_webhook(webhook, timestamp, url, size, md5_hash):
    """
    See reference at
      https://docs.microsoft.com/en-us/outlook/actionable-messages/message-card-reference

    Visualize output at
      https://messagecardplayground.azurewebsites.net/
    """
    title = f"New RefSeq to Uniprot mapping available ({timestamp})"
    message = f"Size = {size}, MD5 = {md5_hash}<br><br><a href={url}>{url}</a>"

    data = {
        "@type": "MessageCard",
        "@context": "https://schema.org/extensions",
        "summary": title,
        "themeColor": "E81123",
        "sections": [
            {"startGroup": True, "activityTitle": title, "activityText": message}
        ],
    }

    requests.post(webhook, json=data).raise_for_status()


def get_latest_local_file(dirpath):
    newest = None
    for it in dirpath.iterdir():
        if it.is_file() and RE_TIMESTAMP_GZ.match(it.name):
            if newest is None or newest < it:
                newest = it

    size = None
    if newest is not None:
        size = newest.stat().st_size

    return newest, size


def get_remote_file_size(url):
    log = logging.getLogger("get_remote_file_size")
    proc = subprocess.Popen(
        CURL_COMMAND + ("--head", url),
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        stdin=subprocess.DEVNULL,
    )

    stdout, stderr = proc.communicate()
    level = logging.ERROR if proc.returncode else logging.DEBUG

    stderr = stderr.decode("utf-8", errors="replace")
    for line in stderr.split("\n"):
        log.log(level, "ERR: %s", line.rstrip())

    stdout = stdout.decode("utf-8", errors="replace")
    if proc.returncode:
        log.error("failed to get archive size from %r", url)
        return None

    for line in stdout.split("\n"):
        log.debug("OUT: %s", line.rstrip())
        if line.startswith("Content-Length:"):
            key, value = line.split(":", 1)
            return int(value)

    log.error("archive size not found in head of %r", url)
    return None


def download_file(url, destination):
    log = logging.getLogger("download_file")
    proc = subprocess.Popen(
        CURL_COMMAND + ("--output", destination, url),
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
        stdin=subprocess.DEVNULL,
    )

    stdout, _ = proc.communicate()
    level = logging.ERROR if proc.returncode else logging.DEBUG

    stdout = stdout.decode("utf-8", errors="replace").rstrip()
    for line in stdout.split("\n"):
        log.log(level, "ERR: %s", line.rstrip())

    return proc.returncode == 0


def calculate_md5(filepath, block_size=64 * 1024):
    with filepath.open("rb") as handle:
        md5 = hashlib.new("md5")
        block = handle.read(block_size)
        while block:
            md5.update(block)
            block = handle.read(block_size)

        return md5.hexdigest()


def parse_args(argv):
    parser = configargparse.ArgumentParser(
        allow_abbrev=False,
        formatter_class=configargparse.ArgumentDefaultsHelpFormatter
    )

    parser.add_argument(
        "--config",
        help="Read command-line options from this file (see above)",
        type=Path,
        is_config_file=True,
    )
    parser.add_argument(
        "--output",
        type=Path,
        default=Path(os.getcwd()) / "output",
        help="Folder containing downloaded mapping files",
    )
    parser.add_argument(
        "--mapping-url", default=DEFAULT_MAPPING_URL, help="URL to NCBI>Uniprot mapping"
    )
    parser.add_argument(
        "--webhook",
        required=True,
        help="URL to Microsoft Teams webhook. If provided, the script will send a "
        "message when a new mapping is availble",
    )
    parser.add_argument(
        "--log-level",
        type=str.upper,
        default="INFO",
        choices=("DEBUG", "INFO", "WARNING", "ERROR", "CRITICAL"),
    )

    return parser.parse_args(argv)


def main(argv):
    args = parse_args(argv)
    coloredlogs.install(
        level=args.log_level, fmt="%(asctime)s %(name)s %(levelname)s %(message)s",
    )

    log = logging.getLogger("main")
    if not shutil.which(CURL_EXEC):
        log.error("%r not found in PATH; cannot proceed", CURL_EXEC)
        return 1

    log.info("saving files to '%s'", args.output)
    args.output.mkdir(parents=True, exist_ok=True)

    last_path, last_size = get_latest_local_file(args.output)
    if last_path is not None:
        log.info("starting from '%s' (%ib)", last_path, last_size)

    if last_size is not None:
        log.info("checking size of current mapping file at %r", args.mapping_url)
        remote_size = get_remote_file_size(args.mapping_url)
        if remote_size is None:
            return 1
        elif last_size == remote_size:
            log.info("remote and local file have same size; assumed to be identical")
            return 0

    now = datetime.now()
    temp_file = args.output / now.strftime("%Y%m%d_%H%M%S.tmp")
    log.info("downloading current mapping file to '%s'", temp_file)
    if not download_file(args.mapping_url, temp_file):
        if temp_file.exists():
            log.info("removing temporary file at '%s'", temp_file)
            temp_file.unlink()

        return 1

    current_file = temp_file.with_suffix(".tsv.gz")
    log.info("moving downloaded file '%s' -> '%s'", temp_file, current_file)
    temp_file.rename(current_file)

    log.info("triggering webhook")
    trigger_webhook(
        webhook=args.webhook,
        timestamp=now.strftime("%Y-%m-%d %H:%M:%S"),
        url=args.mapping_url,
        size=current_file.stat().st_size,
        md5_hash=calculate_md5(current_file),
    )

    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
