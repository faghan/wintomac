import html
import logging
import smtplib
import time

from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart


# Timestamp of script startup; for convinience
_STARTED = time.time()

# Logging format for email messages
_FORMAT = "%(asctime)s %(name)s %(levelname)s %(message)s"
_FORMATTER = logging.Formatter(_FORMAT, datefmt="%H:%M:%S")


class MemoryHandler(logging.Handler):
    """Implements logging using an in-memory stream."""

    _format_date = logging.Formatter("%(asctime)s").format
    _format_name = logging.Formatter("%(name)s").format
    _format_level = logging.Formatter("%(levelname)s").format
    _format_msg = logging.Formatter("%(message)s").format

    def __init__(self):
        self._records = []
        self._max_level = logging.NOTSET
        logging.Handler.__init__(self)

    def emit(self, record):
        # Track the highest level log event observed
        self._max_level = max(self._max_level, record.levelno)

        self._records.append(record)

    def max_level(self):
        """Returns the highest log level observed by the stream."""
        return self._max_level

    def log_content(self):
        def _fmt(record, formatter):
            return (html.escape(formatter(record)),)

        lines = []
        lines.extend(self._HEADER)

        _append = lines.append
        for record in self._records:
            _append("        <tr class='%s'>" % (record.levelname.lower(),))
            _append("          <td>%s</td>" % _fmt(record, self._format_date))
            _append("          <td>%s</td>" % _fmt(record, self._format_name))
            _append("          <td>%s</td>" % _fmt(record, self._format_level))
            _append("          <td>%s</td>" % _fmt(record, self._format_msg))
            _append("        </tr>")

        lines.extend(self._TAIL)

        return "\n".join(lines)

    def log_records(self):
        return list(self._records)

    _HEADER = [
        "<html>",
        "  <head>",
        '    <meta charset="UTF-8">',
        "    <style>",
        "      .critical { color: darkred; font-weight: bold; }",
        "      .error { color: darkred; }",
        "      .warning { color: orange; }",
        "      .debug { color: gray; }",
        "      body { font-family: monospace; } ",
        "      thead > tr { background-color: gray; color: white; text-align: left; }",
        "      tr:nth-child(2n) { background-color: lightgray; }",
        "    </style>",
        "  </head>",
        "  <body>",
        '    <table border=0 style="width: 100%;">',
        "      <thead>",
        "        <tr>",
        "          <th>Timestamp</th>",
        "          <th>Name</th>",
        "          <th>Level</th>",
        "          <th>Message</th>",
        "        </tr>",
        "      </thead>",
        "      <tbody>",
    ]

    _TAIL = [
        "      </tbody>",
        "    </table>",
        "  </body>",
        "</html>",
    ]


def email(recipients, host, port, user, password, text):
    """Will attempt to email the given text to one or more recipients using
    the specified SMTP server. SSH is required except for localhost.
    """
    # Additional events wont be emailed, but are still needed in case emailing fails
    log = logging.getLogger("azsync")
    log.info("emailing log-file to %r using SMTP server %r", ",".join(recipients), host)

    message = MIMEMultipart("alternative")
    message["Subject"] = "Error while copying files to Azure"
    message["From"] = user or "noreply@localhost"
    message["To"] = ",".join(recipients)

    message.attach(MIMEText(text, "html"))

    with smtplib.SMTP(host=host, port=port) as server:
        if host not in ("localhost", "127.0.0.1"):
            server.starttls()
            server.ehlo()

        if user or password:
            server.login(user=user, password=password)

        server.sendmail(message["From"], message["To"], message.as_string())

    return True
