#!/usr/bin/env python3
# -*- coding: utf8 -*-
import logging
import logging.handlers

from collections import defaultdict
from pathlib import Path

import azsync.logging
import azsync.sync

from azsync.azcopy import AZCopy
from azsync.commands.common import new_subparser
from azsync.fileutils import PartialStats
from azsync.state import PersistentState
from azsync.utilities import urljoin, urlquote


_LOGGER = "metabolomics"

_FOLDER_PREFIX_RAWDATA = "RawData"
_FOLDER_PREFIX_METHODS = "DataProcessingMethod"


def add_argparser(subparsers):
    parser = new_subparser(subparsers, "metabolomics")
    parser.set_defaults(command_main=_main)

    parser.add_argument(
        "--main-folder",
        help="Main folder containing *.raw files",
        type=Path,
        required=True,
    )
    parser.add_argument(
        "--destination",
        help="Remote destination folder for sub-folders in --main-folder",
        default="/",
    )

    parser.add_argument(
        "--min-file-age",
        help="Wait at least this many seconds after a file has modified "
        "before transfering it to to Azure [%(default)s]",
        default=1 * 60 * 60,
        type=int,
    )


def _main(args):
    log = logging.getLogger(_LOGGER)
    root_url = urljoin(
        f"https://{args.storage_account}.blob.core.windows.net",
        urlquote(args.container_name),
        urlquote(args.destination),
    )

    client = AZCopy(tenant_id=args.tenant_id, app_id=args.app_id, secret=args.secret)
    client.set_log_level(args.azcopy_log_level)

    tries = azsync.sync.TRIES

    with client:
        log.info("finding metabolomics datasets in '%s'", args.main_folder)

        with PersistentState(args.state_file) as state:
            datasets = _collect_runs_and_methods(state=state, root=args.main_folder)

            log.info("uploading runs and methods")
            for name, dataset in sorted(datasets.items()):
                # Collect method files shared between runs
                method_filepaths, method_updated = _collect_method_files(
                    state=state, dirpath=dataset["methods"], min_age=args.min_file_age
                )

                for runpath in dataset["runs"]:
                    run_filepaths = _collect_run_files(
                        state=state, dirpath=runpath, min_age=args.min_file_age
                    )

                    if method_updated or run_filepaths:
                        log.info("uploading files for '%s/%s'", name, runpath.name)
                        run_filepaths.update(method_filepaths)

                        task = azsync.sync.CheckedMultiCopy(
                            file_map=run_filepaths,
                            dst_url=urljoin(
                                root_url, urlquote(name), urlquote(runpath.name)
                            ),
                        )

                        log.info("running task %r", task)
                        tries = task.execute(client, tries)
                        if tries <= 0:
                            log.error("failed to run task %r", task)
                            return

                        for key, value in task.filestats.items():
                            state.set_file_stats(key, value)


def _collect_runs_and_methods(state, root):
    log = logging.getLogger(_LOGGER)
    samples = defaultdict(lambda: {"methods": None, "runs": [], "state": None})

    for src_dir in root.iterdir():
        if not src_dir.is_dir():
            log.warning("non-dir found in main folder: %r", src_dir.name)
            continue
        elif "_" not in src_dir.name:
            log.warning("misnamed folder found in main folder: %r", src_dir.name)
            continue

        key, name = src_dir.name.split("_", 1)
        if key == _FOLDER_PREFIX_METHODS:
            log.info("found methods folder for sample %r", name)
            samples[name]["methods"] = src_dir
        elif key == _FOLDER_PREFIX_RAWDATA:
            log.info("found raw-data folder for sample %r", name)

            for path in src_dir.iterdir():
                if path.is_dir() and path.name.isdigit():
                    log.info("found run folder for %r: %r", name, path.name)
                    samples[name]["runs"].append(path)
                else:
                    log.warning("unexpected entity for %r: %r", name, path.name)
        else:
            log.warning("unexpected folder in main-folder: %r", src_dir.name)

        samples[name]["state"] = state.get_metabolomics_run(name)

    for key, value in list(samples.items()):
        if not (value["methods"] and value["runs"]):
            log.warning("incomplete dataset '%r'; skipping", key)
            samples.pop(key)

    return dict(samples)


def _collect_method_files(state, dirpath, min_age, root=Path()):
    log = logging.getLogger(_LOGGER)

    method_files = {}
    method_updated = False
    for filepath in dirpath.iterdir():
        if filepath.is_file():
            method_files[root / filepath.name] = filepath

            method_updated |= _is_file_updated(log, state, filepath, min_age)
        elif filepath.is_dir():
            _files, _updated = _collect_method_files(
                state, filepath, min_age, root / filepath.name
            )

            method_files.update(_files)
            method_updated |= _updated
        else:
            log.warning("unexpected non-file found: %r", filepath)
            continue

    return method_files, method_updated


def _collect_run_files(state, dirpath, min_age):
    log = logging.getLogger(_LOGGER)

    run_files = {}
    is_raw_data = False
    for filepath in dirpath.iterdir():
        if filepath.is_file():
            # Raw files have to be post-processed on the VM
            if filepath.suffix == ".raw":
                is_raw_data = True

            # Only updated files are returned, to avoid re-hashing every raw file
            if _is_file_updated(log, state, filepath, min_age):
                run_files[filepath.name] = filepath
        else:
            log.warning("unexpected non-file found: %r", filepath)

    root = Path("raw") if is_raw_data else Path("mzML")

    return {(root / name): filepath for name, filepath in run_files.items()}


def _is_file_updated(log, state, filepath, min_age):
    cached = state.get_file_stats(filepath)
    current = PartialStats.from_filepath(filepath)
    if cached is not None and cached.match(current, optional_hash=True):
        return False

    if current.age() < min_age:
        log.warning("skipping recently modified file '%s'", filepath)
        return False

    return True
