#!/usr/bin/env python3
# -*- coding: utf8 -*-
import csv
import logging
import re


_LOG_NAME = "samplesheet"
_RE_SECTION = re.compile(r"^\[(.*)\]$")


class SampleSheetError(Exception):
    pass


def read_samplesheet(filepath):
    log = logging.getLogger(_LOG_NAME)

    # Samplesheets are supposed to be a subset of ASCII, but names have been observed to
    # contain non-ASCII symbols, some of which are misencoded; `errors="replace"` is
    # used handle those. `encoding="utf-8-sig"` is used since at least one samplesheet
    # with a BOM header was observed.
    log.debug("reading samplesheet from %r", filepath)
    with filepath.open(errors="replace", encoding="utf-8-sig") as handle:
        reader = csv.reader(handle)
        rows = list(reader)

    sections = _split_sections(rows)

    # Required sections
    data = {"Header": _parse_mapping(sections.pop("Header"))}

    if "Reads" in sections:
        log.debug("found 'Reads' section in samplesheet")
        data["Reads"] = _parse_list(sections.pop("Reads"), int)

    if "Settings" in sections:
        log.debug("found 'Settings' section in samplesheet")
        data["Settings"] = _parse_mapping(sections.pop("Settings"))

    log.debug("skipping samplesheet sections %r", sections.keys())

    return data


def _split_sections(rows):
    section = None
    sections = {}
    for row in rows:
        # Trim empty columns. Most samplesheets contain a number of empty columns,
        # corresponding to the maximum number of columns (normally the Data section).
        while row and not row[-1].strip():
            row.pop()

        if row:
            header = _RE_SECTION.match(row[0].strip())
            if header is not None:
                (key,) = header.groups()
                section = []
                sections[key] = section
            elif section is not None:
                section.append(row)
            else:
                raise SampleSheetError(f"non-header line before first header: {row!r}")

    return sections


def _parse_mapping(rows):
    mapping = {}
    for row in rows:
        assert row, "empty rows should be filtered in _split_sections"
        if len(row) == 1:
            row.append("")

        key = row[0]
        if key in mapping:
            raise SampleSheetError(f"duplicate {key!r} keys")

        # Older samplesheets are not proper csv, but seem to be r"([^,]+),(.*)";
        # therefore it is assumed that multiple columns in a mapping represent
        # additional parts of the same text string
        value = ",".join(row[1:])

        mapping[key] = value or None

    return mapping


def _parse_list(rows, type):
    result = []
    for row in rows:
        # See comment in _parse_mapping
        value = ",".join(row)
        result.append(type(value))

    return result
