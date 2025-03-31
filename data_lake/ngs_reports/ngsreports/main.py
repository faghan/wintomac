#!/usr/bin/env python3
# -*- coding: utf8 -*-
import datetime
import io
import logging
import sys
import zipfile

from pathlib import Path

import coloredlogs
import configargparse

import ngsreports.commands.dashboard as dashboard
import ngsreports.commands.report as report
import ngsreports.report.constants as consts
import ngsreports.report.interop as interop

from ngsreports.email import EmailNotification


_LOG_FORMAT = "%(asctime)s %(name)s %(levelname)s %(message)s"


class InterOpData:
    def __init__(self, dirpath, instrument):
        self.metrics = interop.load(dirpath, instrument)
        self.summary, self.index = interop.summarize(self.metrics)

    def run_date(self):
        date = self.metrics.run_info().date()

        return f"20{date[:2]}-{date[2:4]}-{date[4:]}"

    @classmethod
    def iter(cls, obj):
        return interop.iterop(obj)


def add_email_attachments(email, output_files, filename_tmpl):
    log = logging.getLogger("main")
    log.info("adding attachments")

    tables = output_files.pop("Tables", None)
    for name, filepath in sorted(output_files.items()):
        filename = filename_tmpl.format(name, filepath.suffix)

        log.info("adding attachment: %s", filename)
        email.add_attachment(filepath, filename, subtype=filepath.suffix.strip("."))

    if tables:
        filename = filename_tmpl.format("Tables", ".zip")
        log.info("adding zip attachment for CSV tables: %s", filename)

        zipdata = io.BytesIO()
        with zipfile.ZipFile(zipdata, "w", compression=zipfile.ZIP_DEFLATED) as handle:
            for filepath in tables:
                handle.writestr(filepath.name, filepath.read_bytes())

        email.add_attachment(zipdata.getvalue(), filename, subtype="zip")


def send_email_notification(args, data, output_files):
    log = logging.getLogger("main")

    email = EmailNotification()
    email.set_smtp_server(
        host=args.smtp_host,
        port=args.smtp_port,
        user=args.smtp_username,
        password=args.smtp_password,
    )

    for recipient in args.smtp_recipients:
        email.add_recipient(recipient)

    if not email.can_send():
        log.info("email notification not configured")
        return True

    log.info("composing email notifications to %s", ", ".join(args.smtp_recipients))

    # If possible, use the date at which the current run was generated
    if data is None:
        runname = None
        rundate = datetime.datetime.today().strftime("%Y-%m-%d")
    else:
        runname = data.metrics.run_info().name()
        rundate = data.run_date()

    if args.main is dashboard.main:
        email.set_title("{} dashboard ({})".format(args.instrument, rundate))
    else:
        email.set_title("{} run {}".format(args.instrument, runname))

    add_email_attachments(
        email=email,
        output_files=output_files,
        filename_tmpl=f"{rundate.replace('-', '')}{args.instrument}{{}}{{}}",
    )

    log.info("sending email")
    if not email.send():
        return False

    return True


def add_path(parser, name, help, required=True):
    parser.add_argument(
        name,
        type=Path,
        metavar="FOLDER",
        required=required,
        help="{} ({})".format(help, "required" if required else "optional"),
    )


def add_instruments(parser):
    parser.add_argument(
        "--instrument",
        required=True,
        choices=consts.INSTRUMENTS_BY_NAME,
        help="Instrument used for sequencing run [%(default)s]",
    )


def add_email_notification(parser):
    group = parser.add_argument_group("email notification")
    group.add_argument("--smtp-host", help="Hostname of SMTP server")
    group.add_argument("--smtp-port", help="Port of SMTP server", type=int, default=0)
    group.add_argument("--smtp-username", help="Username for SMTP server")
    group.add_argument("--smtp-password", help="Password for STMP server")
    group.add_argument(
        "--smtp-recipient",
        nargs="+",
        default=[],
        dest="smtp_recipients",
        help="Recipients of the PDF files",
    )


def add_args_dashboard(parser):
    parser.set_defaults(main=dashboard.main)
    parser.add_argument("--config", is_config_file=True, help="Config file path")

    add_path(parser, "--cache", "Folder containing cached run data", required=True)
    add_path(parser, "--run", "Folder containing NGS run", required=False)
    add_path(parser, "--output", "Output folder for PDFs", required=False)

    add_instruments(parser)
    add_email_notification(parser)


def add_args_report(parser):
    parser.set_defaults(main=report.main)
    parser.add_argument("--config", is_config_file=True, help="Config file path")

    add_path(parser, "--cache", configargparse.SUPPRESS, required=False)
    add_path(parser, "--run", "Folder containing NGS run", required=True)
    add_path(parser, "--output", "Output folder for PDFs", required=True)

    parser.add_argument(
        "--reports",
        default=[],
        type=str.lower,
        action="append",
        choices=sorted(report.COMMANDS),
        help="Generate only the specified reports. May be specified multiple times and "
        "defaults to 'all' if not set.",
    )

    add_instruments(parser)
    add_email_notification(parser)


def add_args_all(parser):
    parser.set_defaults(main=main_all, reports=[])
    parser.add_argument("--config", is_config_file=True, help="Config file path")

    add_path(parser, "--cache", "Folder containing cached run data", required=True)
    add_path(parser, "--run", "Folder containing NGS run", required=True)
    add_path(parser, "--output", "Output folder for PDFs/CSVs", required=True)

    add_instruments(parser)
    add_email_notification(parser)


def build_parser():
    parser = configargparse.ArgumentParser()
    parser.set_defaults(main=None)

    subparsers = parser.add_subparsers()
    for name, setup, aliases in [
        ("dashboard", add_args_dashboard, []),
        ("report", add_args_report, ["reports"]),
        ("all", add_args_all, []),
    ]:
        setup(subparsers.add_parser(name, aliases=aliases, allow_abbrev=False))

    return parser


def main_all(args, data):
    report_output = report.main(args, data)
    if report_output is None:
        return None

    dashboard_output = dashboard.main(args, data)
    if dashboard_output is None:
        return None

    output_files = {}
    output_files.update(report_output)
    output_files.update(dashboard_output)

    return output_files


def main(argv):
    coloredlogs.install(fmt=_LOG_FORMAT)

    parser = build_parser()
    args = parser.parse_args(argv)
    log = logging.getLogger("main")

    if args.main is None:
        parser.print_help()
        return 1

    if args.output is not None:
        args.output.mkdir(parents=True, exist_ok=True)

    data = None
    if args.run is not None:
        log.info("collecting statistics from '%s'", args.run)
        data = InterOpData(dirpath=args.run, instrument=args.instrument)

    output_files = args.main(args, data)
    if output_files is None:
        return 1

    if not send_email_notification(args, data, output_files):
        return 1

    return 0


def entry_point():
    sys.exit(main(sys.argv[1:]))


if __name__ == "__main__":
    entry_point()
