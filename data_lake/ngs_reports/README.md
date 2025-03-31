# INSTALLATION

The script can be installed using `setup.py`:

    $ python3 setup.py install
    $ ngs_reports --help

Alternatively, the 'ngs_reports' executable can be called directly, provided that the requirements in `requirements.txt` have been installed:

    $ python3 ngs_reports --help


# RUNNING NGS\_REPORTS

`ngs_reports` has three sub-commands:

* `reports`, which generates PDFs and CSVs for a single NGS run.
* `dashboard`, which generates a report of previously processed runs.
* `all`, which generates both of the above report types.

The `dashboard` command can furthermore be run in a couple of ways: If `--output` is omitted, no PDFs are generated. This is useful for processing and caching existing runs. If `--run` is omitted, only the PDF is generated.

Typical usage is using `all`:

    ngs_reports all --cache /path/to/cache --run /path/to/run --output /path/to/run/reports

The `--instrument` value should always be set to the value corresponding to the current run, as InterOp does not provide a reliable way to obtain this information.


# Notifications

If `--smtp-host`, `--smtp-port`, and one or more `--smtp-recipient` are specified, an email containing the generated files will be sent to the given recipients.


# CONFIGURATION

All command-line options can be set using the an ini-file (via `--config`):

    cache = /path/to/cache/
    output = /path/to/output/
    instrument = MiSeq

    smtp-host = mail.dtu.dk
    smtp-port = 587
    # smtp-user =
    # smtp-password =
    # smtp-recipient =
