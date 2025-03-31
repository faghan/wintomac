#!/usr/bin/env python3
# -*- coding: utf8 -*-
import logging
import logging.handlers
import sys
import traceback

import coloredlogs
import configargparse

from pathlib import Path

import pasx_savvy_sync.savvy as savvy
import pasx_savvy_sync.dwh as dwh

_LOG_FORMAT = "%(asctime)s %(name)s %(levelname)s %(message)s"
_LOG_MAX_SIZE = 1024 * 1042
_LOG_MAX_FILES = 5


def setup_logging(args):
    coloredlogs.install(fmt=_LOG_FORMAT, level=args.log_level)

    root_log = logging.getLogger()
    if args.log_file is not None:
        handler = logging.handlers.RotatingFileHandler(
            filename=args.log_file, maxBytes=_LOG_MAX_SIZE, backupCount=_LOG_MAX_FILES
        )
        handler.setFormatter(logging.Formatter(_LOG_FORMAT))

        root_log.addHandler(handler)


class HelpFormatter(configargparse.ArgumentDefaultsHelpFormatter):
    def __init__(self, *args, **kwargs):
        kwargs.setdefault("width", 79)

        super().__init__(*args, **kwargs)


def parse_args(argv):
    parser = configargparse.ArgumentParser(
        formatter_class=HelpFormatter,
        # Abbreviated arguments interact poorly with arguments taken from config files
        allow_abbrev=False,
    )

    parser.add_argument("--config", is_config_file=True)

    group = parser.add_argument_group("Logging")
    group.add_argument(
        "--log-file",
        help="Append log messages to file; files are rotated at 1MB",
        type=Path,
    )
    parser.add_argument(
        "--log-level",
        default="INFO",
        choices=("DEBUG", "INFO", "WARNING", "ERROR"),
    )

    group = parser.add_argument_group("Savvy settings")
    group.add_argument("--savvy-server", required=True, help="Savvy base URL")
    group.add_argument("--savvy-username", required=True, help="Savvy username")
    group.add_argument("--savvy-password", required=True, help="Savvy password")

    group = parser.add_argument_group("Azure PostgreSQL DWH settings")
    group.add_argument("--dwh-server", required=True, help="PostgreSQL DWH server URL")
    group.add_argument(
        "--dwh-database", required=True, help="PostgreSQL DWH database name"
    )
    group.add_argument("--dwh-username", required=True, help="PostgreSQL DWH username")
    group.add_argument("--dwh-password", required=True, help="PostgreSQL DWH password")

    return parser.parse_args(argv)


def main(argv):
    args = parse_args(argv)
    setup_logging(args)

    try:
        # Creates clients and attempts to authenticate using credentials
        savvy_client = savvy.Client(
            server_url=args.savvy_server,
            username=args.savvy_username,
            password=args.savvy_password,
        )

        # Create DWH client; entering client connects and initiates a new batch update
        # by calling the `log_load_start` stored procedure. Exiting the client calls the
        # `log_load_finish` stored procedure and stores the outcome (fails on exception)
        with dwh.Client(
            server=args.dwh_server,
            database=args.dwh_database,
            username=args.dwh_username,
            password=args.dwh_password,
        ) as dwh_client:
            # `api_list` calls below return generators in order to allow data-sets to
            # be processed without being stored in memory in their entirety.
            users = savvy_client.api_list(savvy.USERS)
            dwh_client.update_users(users)

            unit_operations = savvy_client.api_list(savvy.UNIT_OPERATIONS)
            dwh_client.update_unit_operations(unit_operations)

            batches = savvy_client.api_list(savvy.BATCHES)
            dwh_client.update_batches(batches)

            dwh_client.update_variable_details(
                savvy_client.api_list(
                    savvy.VARIABLES_DETAILED_LIST,
                    # Needed for raw `data` values instead of averages, etc.
                    replicate_measure="raw",
                )
            )
    except Exception as error:
        log = logging.getLogger("main")
        log.error("unhandled exception %r", error)
        for line in traceback.format_exc().splitlines():
            log.error("%s", line)

        return 1

    return 0


def entry_point():
    sys.exit(main(sys.argv[1:]))


if __name__ == "__main__":
    entry_point()
