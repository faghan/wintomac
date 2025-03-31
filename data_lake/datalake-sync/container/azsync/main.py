#!/usr/bin/env python3
# -*- coding: utf8 -*-
import logging
import logging.handlers
import os
import shutil
import sys
import traceback

import pid

from configargparse import ArgumentParser, ArgumentDefaultsHelpFormatter

import azsync.commands.ngs
import azsync.commands.metabolomics
import azsync.commands.proteomics
import azsync.logging
import azsync.sync

from azsync.fileutils import try_makedirs
from azsync.logging import MemoryHandler


_LOGGER = "azsync"
_LOG_FORMAT = "%(asctime)s %(name)s %(levelname)s %(message)s"
_LOG_MAX_SIZE = 1024 * 1042
_LOG_MAX_FILES = 5


def setup_logging(log_level, log_file):
    """Sets up logging and returns the module level logger and a StringIO
    object that will receive all logged messages. If log_file is not None, a
    rotating will be created at that path.

    Will use 'coloredlogs' if installed, otherwise will fall back to plain logs.
    """
    try:
        import coloredlogs

        coloredlogs.install(level=log_level, fmt=_LOG_FORMAT)
    except ModuleNotFoundError:
        logging.basicConfig(level=log_level, format=_LOG_FORMAT)

    root_log = logging.getLogger()
    if log_file is not None:
        handler = logging.handlers.RotatingFileHandler(
            filename=log_file, maxBytes=_LOG_MAX_SIZE, backupCount=_LOG_MAX_FILES
        )
        handler.setFormatter(logging.Formatter(_LOG_FORMAT))

        root_log.addHandler(handler)

    # Log to memory, allowing error messages to be emailed regardless of FS state
    handler = MemoryHandler()
    handler.setFormatter(logging.Formatter(_LOG_FORMAT))
    root_log.addHandler(handler)

    # Shut up overly verbose modules
    for path in ("pydatalake.gen2", "urllib3.connectionpool"):
        logging.getLogger(path).setLevel(logging.INFO)

    return logging.getLogger(_LOGGER), handler


def parse_args(argv):
    parser = ArgumentParser(
        formatter_class=ArgumentDefaultsHelpFormatter,
        default_config_files=["azcopy.cfg"],
        allow_abbrev=False,
    )
    # Value is overriden when user selects subparser
    parser.set_defaults(command_main=None)

    subparsers = parser.add_subparsers()
    azsync.commands.ngs.add_argparser(subparsers)
    azsync.commands.metabolomics.add_argparser(subparsers)
    azsync.commands.proteomics.add_argparser(subparsers)

    args = parser.parse_args(argv)
    if not args.command_main:
        parser.print_usage()
        parser.exit(status=1)

    return args


def main(argv):
    args = parse_args(argv)
    args.main_folder = args.main_folder.absolute()

    log, log_handler = setup_logging(log_level=args.log_level, log_file=args.log_file)
    log.info("running %s", " ".join(sys.argv))
    if args.log_recipients and not args.smtp_host:
        log.error("recipients for log-file specified, but no --smtp-host was provided")

    if not shutil.which(azsync.azcopy.EXECUTABLE):
        log.error("azcopy executable %r not found on PATH", azsync.azcopy.EXECUTABLE)

    try:
        if args.azcopy_logs is not None:
            try_makedirs(args.azcopy_logs)

            os.environ["AZCOPY_LOG_LOCATION"] = str(args.azcopy_logs)

        if not args.credentials.exists():
            log.error("azure credentials file not found: '%s'", args.credentials)
        else:
            log.info("reading azure credentials from '%s'", args.credentials)
            args.secret = args.credentials.read_text().strip()

        if log_handler.max_level() >= logging.ERROR:
            log.info("error occured during setup; command not executed")
        else:
            try:
                with pid.PidFile(args.pid_file.name, args.pid_file.parent):
                    args.command_main(args)
            except pid.PidFileError as error:
                log.warning("Process is already running: %r", error)
    except azsync.azcopy.AZError as error:
        log.error("error running azcopy command: %s", error)
    except Exception as error:
        log.error("unhandled exception %r", error)
        for line in traceback.format_exc().splitlines():
            log.error("%s", line)

    if log_handler.max_level() >= logging.ERROR:
        if args.log_recipients and args.smtp_host:
            try:
                azsync.logging.email(
                    recipients=args.log_recipients,
                    host=args.smtp_host,
                    port=args.smtp_port,
                    user=args.smtp_user,
                    password=args.smtp_password,
                    text=log_handler.log_content(),
                )
            except Exception as error:
                log.error("failed to email log using %r: %r", args.smtp_host, error)

        return 1

    return 0


def entry_point():
    sys.exit(main(sys.argv[1:]))


if __name__ == "__main__":
    entry_point()
