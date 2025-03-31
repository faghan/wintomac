#!/usr/bin/env python3
# -*- coding: utf8 -*-
import datetime
import fnmatch
import logging
import logging.handlers

from pathlib import Path

import azsync.logging
import azsync.sync

from azsync.azcopy import AZCopy
from azsync.commands.common import new_subparser
from azsync.fileutils import PartialStats, iglob_folder
from azsync.state import PersistentState
from azsync.utilities import urljoin, urlquote

import os
import re

_XLSX_RESULTS = "results.xlsx"
_XLSX_METADATA = "metadata.xlsx"


def add_argparser(subparsers):
    parser = new_subparser(subparsers, "proteomics")
    parser.set_defaults(command_main=_main)

    parser.add_argument(
        "--main-folder",
        help="Main folder containing *.raw files",
        type=Path,
        required=True,
    )
    parser.add_argument(
        "--project-glob",
        help="Glob used to select project sub-folders in --main-folder",
        default="prot[0-9]*",
        type=str.lower,
    )
    parser.add_argument(
        "--blank-glob",
        help="Glob used to exclude blank samples in project sub-folders",
        default="blank*.raw",
        type=str.lower,
    )

    parser.add_argument(
        "--destination",
        help="Remote destination folder for sub-folders in --main-folder",
        default="/",
    )

    parser.add_argument(
        "--min-file-age",
        help="Wait at least this many seconds after a file has modified "
        "before transfering it to to Azure",
        default=24 * 60 * 60,
        type=int,
    )


def _main(args):
    log = logging.getLogger(__name__)
    client = AZCopy(tenant_id=args.tenant_id, app_id=args.app_id, secret=args.secret)
    client.set_log_level(args.azcopy_log_level)

    with client:
        log.info("synchronizing *.raw files in '%s' to azure", args.main_folder)

        with PersistentState(args.state_file) as state:
            for src_dir in iglob_folder(args.main_folder, args.project_glob):
                if not src_dir.is_dir():
                    log.info("skipping non-project folder %r", src_dir)
                    continue

                _synchronize_folder(
                    args=args,
                    client=client,
                    state=state,
                    src_dir=src_dir,
                )


def _synchronize_folder(args, client, state, src_dir):
    log = logging.getLogger(__name__)
    root_url = urljoin(
        f"https://{args.storage_account}.blob.core.windows.net",
        urlquote(args.container_name),
        urlquote(args.destination),
        urlquote(src_dir.name.upper()),
    )

    log.info("Synchronizing '%s' to %r", src_dir, root_url)

    # 1. Collect and stat local raw, result, and misc files
    files = _collect_local_files(
        src_dir, blank_glob=args.blank_glob, min_age=args.min_file_age
    )

    requestId = str(src_dir).split(os.linesep)[-1]

    # 2. Compare with previous runs using file-stat cache
    updated_files = _get_updated_files(state, files, log)
    if not updated_files:
        log.info("No updated files in '%s'; skipping", src_dir)
        return

    # 3. upload new/modified files
    log.info("Found %i new/updated files out of %i:", len(updated_files), len(files))
    for idx, filename in enumerate(sorted(updated_files), start=1):
        log.info("  %i. %s", idx, filename)

    task = azsync.sync.CheckedMultiCopy(updated_files, root_url)
    tries = task.execute(client, azsync.sync.TRIES)
    if tries <= 0:
        log.error("failed to run task %r", task)
        return

    for filepath, filestats in task.filestats.items():
        state.set_file_stats(filepath, filestats)

    RESULT_FILE_EXITS_IN_UPDATED_FILES = False
    # 4. Record if files needed for further processing were uploaded
    runstate = state.get_proteomics_run(src_dir.name.upper())
    for file in updated_files:
        if is_it_valid_result(file):
            runstate.set_results_synced()
            RESULT_FILE_EXITS_IN_UPDATED_FILES = True

#    if _XLSX_RESULTS in updated_files:
#        runstate.set_results_synced()
    META_FILE_EXITS_IN_UPDATED_FILES = False
    for file in updated_files:
        if is_it_valid_metadata(requestId, file):
            runstate.set_metadata_synced()
            META_FILE_EXITS_IN_UPDATED_FILES = True
    
    #if _XLSX_METADATA in updated_files:
    #    runstate.set_metadata_synced()
    RESULT_FILE_EXITS_IN_FILES = False
    META_FILE_EXITS_IN_FILES = False
    for file in files:
        if is_it_valid_result(file):
            RESULT_FILE_EXITS_IN_FILES = True
        if is_it_valid_metadata(requestId, file):
            META_FILE_EXITS_IN_FILES = True

    # 5. If result (xlsx) files were added/modified, add remote .sync file
    if (
        RESULT_FILE_EXITS_IN_FILES
        and META_FILE_EXITS_IN_FILES
        and (RESULT_FILE_EXITS_IN_UPDATED_FILES or META_FILE_EXITS_IN_UPDATED_FILES)
    ):
        task = azsync.sync.Write(
            dst=urljoin(root_url, "results.ready"),
            data=datetime.datetime.now().isoformat(),
        )

        if task.execute(client, tries) <= 0:
            log.error("failed to run task %r", task)
            return

        runstate.set_flag_synced()

    log.info("synchronization of '%s' completed", src_dir)


def is_it_valid_result(filename):
    log = logging.getLogger(__name__)
    regExp = "Prot(.)*.xlsx"
    if re.search(regExp, filename):
        log.info("%s is a valid result file", filename)
        return True
    log.info("%s is not a valid result file", filename)
    return False

def is_it_valid_metadata(requestId, filename):
    validPatterns = ["{}_metadata.xlsx".format(requestId)]
    if "{}_{}".format(requestId, filename) in validPatterns:
        return True
    return False


def _collect_local_files(src_dir, blank_glob, min_age):
    log = logging.getLogger(__name__)
    result = {}
    requestId = str(src_dir).split(os.linesep)[-1]

    for filepath in sorted(src_dir.iterdir()):
        log.info("collecting %s", filepath)
        if not filepath.is_file():
            log.info("skipping folder '%s'", filepath)
            continue

        stats = PartialStats.from_filepath(filepath)
        if stats.age() < min_age:
            log.info("skipping recently modified file '%s'", filepath)
            continue

        dst_folder = None
        dst_filename = filepath.name
        suffix = filepath.suffix.lower()

        if suffix == ".raw":
            dst_folder = "samples"
            if fnmatch.fnmatch(dst_filename.lower(), blank_glob):
                dst_folder = "blanks"
        elif suffix in (".meth", ".sld"):
            dst_folder = "other"
        elif is_it_valid_result(dst_filename):
            dst_filename = dst_filename.lower()
            dst_folder = "/results/"
        elif is_it_valid_metadata(requestId, dst_filename.lower()):
            dst_filename = dst_filename.lower()
            dst_folder = "/"
        else:
            log.info("else is called")
            log.info("skipping file '%s'", filepath)
            continue
        #elif dst_filename.lower() == _XLSX_RESULTS:
        #    dst_folder = "/"
        #    dst_filename = _XLSX_RESULTS
        #elif dst_filename.lower() == _XLSX_METADATA:
        #    dst_folder = "/"
        #    dst_filename = _XLSX_METADATA


        destination = urljoin(dst_folder, dst_filename)
        if destination in result:
            log.error(
                "multiple files map to '%s' for '%s': '%s' and '%s'",
                destination,
                src_dir,
                result[destination],
                filepath,
            )

            return None

        result[destination] = {"filepath": filepath, "filestat": stats}

    return result


def _get_updated_files(state, files, log):
    updated_files = {}
    for key, value in files.items():
        filepath = value["filepath"]
        current_stats = value["filestat"]
        cached_stats = state.get_file_stats(filepath)
        #log.info("%s: %s", filepath, cached_stats)

        if cached_stats is None or not current_stats.match(
            cached_stats, optional_hash=True
        ):
            updated_files[key] = filepath

    return updated_files
