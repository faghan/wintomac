#!/usr/bin/env python3
# -*- coding: utf8 -*-
import logging
import logging.handlers
import time

from datetime import datetime, timedelta
from pathlib import Path

import azsync.logging
import azsync.sync

from azsync.azcopy import AZCopy
from azsync.commands.common import new_subparser
from azsync.state import PersistentState
from azsync.utilities import urljoin, urlquote


def add_argparser(subparsers, command="ngs"):
    parser = new_subparser(subparsers, command=command, cfgname="ngs")
    parser.set_defaults(command_main=_main)

    parser.add_argument(
        "--main-folder",
        help="Main folder; sub-folders in this folder are synchronized individually. "
        "If a filename is specified with --completion-flag, folders are only "
        "synchronized if that file is found in a given sub-folder.",
        type=Path,
        required=True,
    )
    parser.add_argument(
        "--samplesheet-folder",
        help="SampleSheet folder; is assumed to contain X.csv files, "
        "where X corresponds to the name of a folder in --main-folder.",
        type=Path,
    )
    parser.add_argument(
        "--destination",
        help="Remote destination folder for sub-folders in --main-folder",
        default="/",
    )

    parser.add_argument(
        "--completion-flag",
        help="--main-folder sub-folders are only synchronized if a file "
        "with this name is present in a given sub-folder",
        type=Path,
        required=True,
    )
    parser.add_argument(
        "--completion-delay",
        help="Wait at least this many seconds after a --completion-flag file has "
        "been created before transferring the corresponding folder",
        default=60 * 60,
        type=int,
    )

    parser.add_argument(
        "--remove-source",
        help="Remove main folder sub-directories when successfully sync'd",
        default=False,
        action="store_true",
    )

    return parser


def _main(args):
    log = logging.getLogger(__name__)
    log.info("synchronizing folders in '%s' to azure", args.main_folder)

    if args.samplesheet_folder is not None:
        args.samplesheet_folder = args.samplesheet_folder.absolute()

    client = AZCopy(tenant_id=args.tenant_id, app_id=args.app_id, secret=args.secret)
    client.set_log_level(args.azcopy_log_level)

    with PersistentState(args.state_file) as state:
        with client:
            for name in _collect_runs(args):
                runstate = state.get_ngs_run(name)
                if runstate.is_synced:
                    log.info("skipping already synced run %r", name)
                    continue

                log.info("processing run %r", name)

                dst_url = urljoin(
                    f"https://{args.storage_account}.blob.core.windows.net",
                    urlquote(args.container_name),
                    urlquote(args.destination),
                    urlquote(name),
                )

                _sync_folder(
                    args=args,
                    client=client,
                    src_dir=args.main_folder / name,
                    dst_url=dst_url,
                    runstate=runstate,
                )

        unsynced_runs = []
        for name, runstate in state.get_ngs_runs():
            if not runstate.is_synced:
                unsynced_runs.append((name, runstate))

        if unsynced_runs:
            currenttime = datetime.utcnow()
            log.info("Checking %i incomplete runs for stale runs", len(unsynced_runs))

            for name, runstate in sorted(unsynced_runs):
                warned = runstate.warned or runstate.observed
                if warned is not None and (currenttime - warned <= timedelta(hours=48)):
                    log.debug("Warning for %r skipped due to recent warning", name)
                    continue

                if not runstate.is_data_synced:
                    log.error("Data was never synced for old NGS run %r", name)
                if not runstate.is_sheet_synced:
                    log.error("Samplesheet was never synced for old NGS run %r", name)

                if (
                    runstate.is_data_synced and runstate.is_sheet_synced
                ) and not runstate.is_flag_synced:
                    log.error("NGS run %r has not been flagged as complete", name)

                runstate.set_warned()


def _collect_runs(args):
    """Collects all runs, as determined by the presence of either run folders or
    samplesheet files; this is done to ensure that no runs are overlooked.
    """
    runs = set()
    log = logging.getLogger(__name__)
    for run_dir in sorted(args.main_folder.iterdir()):
        if not run_dir.is_dir():
            log.warning("unexpected file in source-folder: '%s'", run_dir)
            continue

        runs.add(run_dir.name)

    if args.samplesheet_folder is not None:
        for samplesheet in sorted(args.samplesheet_folder.iterdir()):
            if not (samplesheet.is_file() and samplesheet.suffix == ".csv"):
                log.warning(
                    "unexpected file or folder in sample sheet folder: '%s'",
                    samplesheet,
                )
                continue

            runs.add(samplesheet.stem)

    return sorted(runs)


def _sync_folder(args, client, src_dir, dst_url, runstate):
    tasks = []
    has_data = runstate.is_data_synced
    #has_samplesheet = runstate.is_sheet_synced

    #if not has_samplesheet:
    #    has_samplesheet = _schedule_samplesheet_sync(
    #        args=args, src_dir=src_dir, dst_url=dst_url, tasks=tasks, has_data=has_data
    #    )

    if not has_data:
        has_data = _schedule_data_sync(args, src_dir, dst_url, tasks)

    # Create *.sync file on Azure to indicate that sync was completed
    if has_data:
        tasks.append(
            azsync.sync.Write(dst=f"{dst_url}.sync", data=datetime.now().isoformat())
        )

    if has_data and args.remove_source:
        tasks.append(azsync.sync.RemoveLocal(src_dir))

    if azsync.sync.execute(client=client, tasks=tasks):
        if has_data:
            runstate.set_data_synced()

        #if has_samplesheet:
        #    runstate.set_sheet_synced()

        if has_data:
            runstate.set_flag_synced()


def _schedule_samplesheet_sync(args, src_dir, dst_url, tasks, has_data):
    """Checks for Schedules copying the samplesheet file to Azure; """
    log = logging.getLogger(__name__)

    if args.samplesheet_folder is None:
        samplesheet = src_dir / "SampleSheet.csv"
        if not has_data:
            # Sheet will be copied with data files
            return samplesheet.exists()
        # Data was copied, but sheet was omitted for whatever reason
    else:
        samplesheet = args.samplesheet_folder / src_dir.with_suffix(".csv").name

    if not samplesheet.exists():
        log.warning("samplesheet not found at '%s'", samplesheet)
        return False

    tasks.append(
        azsync.sync.CheckedCopy(samplesheet, urljoin(dst_url, "SampleSheet.csv"))
    )

    return True


def _schedule_data_sync(args, src_dir, dst_url, tasks):
    log = logging.getLogger(__name__)
    flag_file = src_dir / args.completion_flag
    if not flag_file.exists():
        log.info('Flag file is %s', str(flag_file))
        log.info("data folder is incomplete; skipping")
        return False

    youngest_allowed = time.time() - args.completion_delay
    for filepath in src_dir.iterdir():
        if filepath.stat().st_mtime > youngest_allowed:
            log.info("data folder is recently completed; skipping")
            return False

    tasks.append(azsync.sync.CheckedSync(src_dir, dst_url, timeout=args.timeout))
    return True
