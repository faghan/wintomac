#!/usr/bin/env python3
import logging
import smtplib

from pathlib import Path

from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
from email.mime.application import MIMEApplication


_LOG_NAME = "email"


class EmailNotification:
    def __init__(self):
        self._host = None
        self._port = None
        self._user = None
        self._pass = None
        self._recipients = []

        self._title = "NGS Reports"
        self._text = ""
        self._attachments = []

        self._log = logging.getLogger(_LOG_NAME)

    def set_title(self, title):
        self._title = title

    def add_recipient(self, address):
        self._recipients.append(address)

    def add_attachment(self, path_or_bytes, name, subtype):
        if not isinstance(path_or_bytes, bytes):
            path_or_bytes = Path(path_or_bytes).read_bytes()

        attachment = MIMEApplication(path_or_bytes, _subtype=subtype)
        attachment.add_header("content-disposition", "attachment", filename=name)

        self._attachments.append(attachment)

    def set_smtp_server(self, host, port, user=None, password=None):
        self._host = host and host.strip()
        self._port = int(port) if port is not None else port
        self._user = user and user.strip()
        self._pass = password

        if self._port is not None and not 0 <= self._port <= 65535:
            raise ValueError("invalid port {}".format(port))

    def can_send(self):
        if not (self._host and self._recipients):
            if self._host:
                self._log.warning("has SMTP host, but no recipients specified")
            elif self._recipients:
                self._log.warning("no SMTP server specified; cannot send emails")

            return False

        return True

    def send(self):
        if not self.can_send():
            return False

        message = self._build_message()

        with smtplib.SMTP(host=self._host, port=self._port) as server:
            if self._host not in ("localhost", "127.0.0.1"):
                server.starttls()
                server.ehlo()

            if self._user or self._pass:
                server.login(user=self._user, password=self._pass)

            server.sendmail(message["From"], message["To"], message.as_string())

        return True

    def _build_message(self):
        message = MIMEMultipart()

        message["Subject"] = self._title
        message["From"] = self._user or "root@localhost"
        message["To"] = ",".join(self._recipients)

        if self._text:
            message.attach(MIMEText(self.text, "html"))

        for attachment in self._attachments:
            message.attach(attachment)

        return message


def email(recipients, host, port, user, password, text=None, attachments=()):
    """Will attempt to email the given text to one or more recipients using
    the specified SMTP server. SSH is required except for localhost.
    """
    # Additional events wont be emailed, but are still needed in case emailing fails
    log = logging.getLogger(_LOG_NAME)
    log.info("sending email via %s:%i", host, port)
    log.info("sending email to %r", recipients)

    return True
