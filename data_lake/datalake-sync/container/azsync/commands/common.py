from pathlib import Path

from configargparse import ArgumentDefaultsHelpFormatter

from azsync.azcopy import AZCOPY_LOG_LEVELS


def new_subparser(subparsers, command, cfgname=None):
    """Adds command-line options shared between sub-commands; these must be
    added to each parser in order to allow use with ConfigArgParser.
    """
    parser = subparsers.add_parser(
        command,
        allow_abbrev=False,
        formatter_class=ArgumentDefaultsHelpFormatter,
    )
    parser.set_defaults(parser=command)

    parser.add_argument(
        "--config",
        help="Read command-line options from this file (see above)",
        type=Path,
        is_config_file=True,
    )
    parser.add_argument("--retry-times", help="Max retries", type=int, default=5)
    parser.add_argument(
        "--timeout",
        help="Time-out in seconds when attemping to hash files",
        type=float,
        default=5 * 60,
    )
    parser.add_argument(
        "--pid-file",
        help="Path to pid file",
        type=Path,
        default=Path(f"~/.azsync/{cfgname or command}.pid").expanduser(),
    )
    parser.add_argument(
        "--state-file",
        help="Path to file storing persistent state",
        type=Path,
        default=Path(f"~/.azsync/{cfgname or command}.db").expanduser(),
    )

    group = parser.add_argument_group("logging")
    group.add_argument(
        "--log-file",
        help="Append log messages to file; files are rotated at 1MB",
        type=Path,
    )
    group.add_argument(
        "--log-level",
        help="Minimum log-level",
        default="INFO",
        choices=("DEBUG", "INFO", "WARNING", "ERROR"),
        type=str.upper,
    )
    group.add_argument("--azcopy-logs", help="Location of azcopy log files", type=Path)
    group.add_argument(
        "--azcopy-log-level",
        help="Minimum log-level for azcopy",
        default="WARNING",
        choices=AZCOPY_LOG_LEVELS,
        type=str.upper,
    )

    group = parser.add_argument_group("email notification")
    group.add_argument(
        "--log-recipient",
        dest="log_recipients",
        help="Email the log to this email address on errors",
        nargs="+",
    )
    group.add_argument("--smtp-host", help="Hostname of SMTP server")
    group.add_argument("--smtp-port", help="Port of SMTP server", type=int, default=0)
    group.add_argument("--smtp-user", help="Username for SMTP server")
    group.add_argument("--smtp-password", help="Password for STMP server")

    # Azure options
    group = parser.add_argument_group("azure")
    group.add_argument("--tenant-id", required=True)
    group.add_argument("--application-id", dest="app_id", required=True)
    group.add_argument("--storage-account", help="Storage account URL", required=True)
    group.add_argument("--container-name", help="Container name", required=True)
    group.add_argument(
        "--credentials",
        help="Plain-text file containing Azure the client secret",
        default=Path("credentials.txt"),
        type=Path,
    )

    return parser
