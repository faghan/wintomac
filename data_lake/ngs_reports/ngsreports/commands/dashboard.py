import json
import logging
import math

import xlsxwriter

from ngsreports.samplesheet import read_samplesheet
from ngsreports.xmlsheet import IlluminaXMLParser, IlluminaXML


_LOG_NAME = "dashboard"


########################################################################################
# Collecting stats from existing NGS runs


def collect_stats(args, data, instrument):
    info = data.metrics.run_info()
    totals = data.summary.total_summary()
    worksheet = read_samplesheet(args.run / "SampleSheet.csv")

    runparams = None
    runparams_path = args.run / "RunParameters.xml"
    if runparams_path.exists():
        runparams = IlluminaXMLParser(runparams_path.read_text()).root

    total_pf_reads = 0
    total_cluster_count = 0  # Identified reads
    for it in data.iter(data.index):
        total_pf_reads += it.total_pf_reads()
        total_cluster_count += sum(it.cluster_count() for it in data.iter(it))

    cycles = []
    for row in data.iter(data.summary):
        read = row.read()

        if not read.is_index():
            cycles.append(read.total_cycles())

    return {
        "metadata": {
            "cycles": cycles,
            "date": data.run_date(),
            "flowcell_id": info.flowcell_id(),
            "instrument_name": info.instrument_name(),
            "instrument_type": instrument,
            "is_indexed": info.is_indexed(),
            "is_paired_end": info.is_paired_end(),
            "run_id": info.name(),
            "success": any(data.iter(data.index)),
        },
        "summary": {
            "error_rate": totals.error_rate(),
            "percent_aligned": totals.percent_aligned(),
            "q30+": totals.percent_gt_q30(),
            "yield_g": totals.yield_g(),
            "pf_reads": total_pf_reads,
            "pf_reads_identified": total_cluster_count,
        },
        "lanes": [
            {
                "error_rate": it.error_rate(),
                "percent_aligned": it.percent_aligned(),
                "q30+": it.percent_gt_q30(),
                "yield_g": it.yield_g(),
            }
            for it in (it.summary() for it in data.iter(data.summary))
        ],
        "indexing": [
            {
                "total_identified": it.total_fraction_mapped_reads(),
                "total_unidentified": 100 - it.total_fraction_mapped_reads(),
                "per_sample_identified": [
                    sample.fraction_mapped() for sample in data.iter(it)
                ],
            }
            for it in data.iter(data.index)
        ],
        "samplesheet": worksheet,
        "runparameters": runparams,
    }


def read_run_data(log, cache, instrument):
    data = {"all": []}

    for filepath in cache.iterdir():
        if filepath.suffix.lower() == ".json":
            log.debug("Collecting %s runs file '%s'", instrument, filepath)
            with filepath.open("rt") as handle:
                run = json.load(handle)

                instrument_type = run["metadata"]["instrument_type"]
                if instrument_type != instrument:
                    log.debug("%s run skipped: %s", instrument_type, filepath)
                    continue

                log.info("%s run found: %s", instrument_type, filepath)
                date = run["metadata"]["date"]
                data["all"].append(run)

                year = date.split("-", 1)[0]
                data.setdefault(year, []).append(run)

    for values in data.values():
        values.sort(key=lambda it: it["metadata"]["date"], reverse=True)

    return data


########################################################################################
# Generating dashboard XLSX


class DefaultColumns:
    def header(self):
        return [
            "Year",
            "Date",
            # Currently not needed, due to reports only including a single instrument
            # "Instrument Type",
            # "Instrument Name",
            "Run ID",
            "Run status",
            "Yield (Gbp)",
            "Error rate (%)",
            "Q30+ (%)",
            "Indexed (%)",
            "Length 1",
            "Length 2",
        ]

    def formats(self):
        return {
            "Yield (Gbp)": "0.0",
            "Error rate (%)": "0.00",
            "Q30+ (%)": "0.0",
            "Indexed (%)": "0.0",
        }

    def get_cells(self, item):
        metadata = item["metadata"]
        summary = item["summary"]

        pf_reads = summary["pf_reads"]
        pf_reads_identified = summary["pf_reads_identified"]
        pct_identified = (
            (pf_reads_identified * 100) / pf_reads if pf_reads else float("nan")
        )

        cycles = list(metadata["cycles"])
        while len(cycles) < 2:
            cycles.append(None)

        return {
            "Year": metadata["date"].split("-")[0],
            "Date": metadata["date"],
            "Instrument Type": metadata["instrument_type"],
            "Instrument Name": metadata["instrument_name"],
            "Run ID": metadata["run_id"],
            "Run status": "OK" if item["indexing"] else "Failed",
            "Yield (Gbp)": summary["yield_g"],
            "Error rate (%)": summary["error_rate"],
            "Q30+ (%)": summary["q30+"],
            "Indexed (%)": pct_identified,
            "Length 1": cycles[0],
            "Length 2": cycles[1],
        }


class MiSeqColumns(DefaultColumns):
    COLUMNS = [
        "Application",
        "Assay",
        "Index Adapters",
        "Chemistry",
        # 'Date',
        # 'Description',
        # 'IEMFileVersion',
        # 'Instrument Type',
        "Investigator Name",
        # 'Workflow',
        "Experiment Name",
    ]

    def header(self):
        return super().header() + self.COLUMNS

    def get_cells(self, item):
        cells = super().get_cells(item)
        header = item["samplesheet"]["Header"]
        for key in self.COLUMNS:
            cells[key] = header.get(key)

        return cells


class NextSeqColumns(DefaultColumns):
    def header(self):
        return super().header() + [
            # -- Samplesheet --
            # "ContainerID",
            # "ContainerType",
            # "FileVersion",
            "LibraryPrepKit",
            # "Notes",
            # -- RunParameters --
            "Chemistry",
            "Experiment Name",
        ]

    def get_cells(self, item):
        cells = super().get_cells(item)

        header = item["samplesheet"]["Header"]
        cells["LibraryPrepKit"] = header.get("LibraryPrepKit")

        params = IlluminaXML(item["runparameters"]).first_child("RunParameters")
        cells["Chemistry"] = params.first_child("Chemistry").data
        cells["Experiment Name"] = params.first_child("ExperimentName").data

        return cells


# Inches to the units used for column widths (number of chars in default font)
_INCHES_TO_CURSED_UNITS = 70 / 6.88
# Inches to 72 DPI
_INCHES_TO_CHART_WIDTH = 72
# Chart width in inches
_CHART_WIDTH = 6


def estimate_column_width(label, values, fmt):
    if fmt == "0.0":
        fmt = "{:.1f}"
    elif fmt == "0.00":
        fmt = "{:.2f}"
    else:
        fmt = "{}"

    return max(len(label), max(len(fmt.format(value)) for value in values))


def _write_float_value(worksheet, row, col, number, format=None):
    if math.isnan(number) or math.isinf(number):
        return worksheet.write_formula(row, col, "=NA()", format)

    return worksheet.write_number(row, col, number, format)


def _main_build_barchart(workbook, worksheet, header, key, items, offset):
    col_categories = header.index("Date") + 1
    col_values = header.index(key) + 1

    points = {
        "OK": {"fill": {"color": "blue"}, "line": {"color": "blue"}},
        "Failed": {"fill": {"color": "red"}, "line": {"color": "red"}},
    }

    chart = workbook.add_chart({"type": "column"})
    chart.add_series(
        {
            "categories": [
                worksheet.name,
                1,
                col_categories,
                len(items),
                col_categories,
            ],
            "values": [worksheet.name, 1, col_values, len(items), col_values],
            # Formatting for individual data-points
            "points": [points[item["Run status"]] for item in items],
        }
    )

    # Disable legend
    chart.set_legend({"position": "none"})

    # X and Y axis labels and units; explicit rotation needed for some readers
    chart.set_y_axis({"name": key, "name_font": {"rotation": -90}})
    chart.set_x_axis({"num_font": {"size": 7, "rotation": -45}})

    # Explicitly disable title; required for some readers
    chart.set_title({"none": True})

    chart.set_size({"width": _CHART_WIDTH * _INCHES_TO_CHART_WIDTH, "height": 300})

    worksheet.insert_chart(
        0,
        0,
        chart,
        {
            "y_offset": offset * (chart.height + 25) + 25,
            # Do not move or resize with cells
            "object_position": 3,
        },
    )


def _main_build_page(workbook, worksheet, items, instrument, formats):
    if instrument == "MiSeq":
        builder = MiSeqColumns()
    elif instrument == "NextSeq":
        builder = NextSeqColumns()
    else:
        builder = DefaultColumns()

        log = logging.getLogger(_LOG_NAME)
        log.warning("no additional headers for %s instrument", instrument)

    header = builder.header()
    column_formats = builder.formats()

    # Write #NA() in cells containing NaN or +/- inf
    worksheet.add_write_handler(float, _write_float_value)

    # Add empty column for charts
    worksheet.write(0, 0, "Charts", formats["bold"])
    worksheet.set_column(0, 0, _CHART_WIDTH * _INCHES_TO_CURSED_UNITS)

    # Turn data area into a proper table
    worksheet.add_table(
        0,
        1,
        len(items),
        len(header),
        {
            "style": "Table Style Light 1",
            "columns": [{"header": key} for key in header],
        },
    )

    widths = []
    items = [builder.get_cells(item) for item in items]
    for col, key in enumerate(header, start=1):
        fmt = column_formats.get(key)
        values = [item[key] for item in items]
        widths.append(estimate_column_width(key, values, fmt))

        worksheet.write_column(
            row=1,
            col=col,
            data=values,
            cell_format=formats.get(fmt),
        )

    bar_charts = ("Yield (Gbp)", "Error rate (%)", "Q30+ (%)", "Indexed (%)")
    for row, key in enumerate(bar_charts):
        _main_build_barchart(
            workbook=workbook,
            worksheet=worksheet,
            header=header,
            key=key,
            items=items,
            offset=row,
        )

    # Rough estimation of column widths
    for column, width in enumerate(widths, start=1):
        worksheet.set_column(column, column, max(len(header[column - 1]), width) * 1.25)


def main_build(args, data):
    log = logging.getLogger(_LOG_NAME)
    args.cache.mkdir(parents=True, exist_ok=True)

    log.info("Reading run data from '%s':", args.cache)
    data = read_run_data(log, args.cache, args.instrument)

    destination = args.output / "dashboard.xlsx"
    log.info("Writing NGS dashboard report to %r", destination)

    workbook = xlsxwriter.Workbook(destination)
    formats = {
        "bold": workbook.add_format({"bold": True}),
        "0.0": workbook.add_format({"num_format": "0.0"}),
        "0.00": workbook.add_format({"num_format": "0.00"}),
    }

    # Page containing all data
    worksheet = workbook.add_worksheet(name=args.instrument)
    _main_build_page(
        workbook=workbook,
        worksheet=worksheet,
        items=data.pop("all"),
        instrument=args.instrument,
        formats=formats,
    )

    for key, items in sorted(data.items(), reverse=True):
        worksheet = workbook.add_worksheet(name=key)

        _main_build_page(
            workbook=workbook,
            worksheet=worksheet,
            items=items,
            instrument=args.instrument,
            formats=formats,
        )

    workbook.close()

    log.info("Done")
    return {"Dashboard": destination}


def main_collect(args, data):
    log = logging.getLogger(_LOG_NAME)
    args.cache.mkdir(parents=True, exist_ok=True)

    stats = collect_stats(args, data, instrument=args.instrument)

    run_name = data.metrics.run_info().name()
    temp_file = args.cache / (run_name + ".tmp")
    destination = temp_file.with_suffix(".json")

    with temp_file.open("wt") as handle:
        json.dump(stats, handle)
    log.info("saving statistics to '%s'", destination)
    temp_file.rename(destination)

    return {}


def main(args, data):
    output_files = {}

    for path, func in ((args.run, main_collect), (args.output, main_build)):
        if path is not None:
            output = func(args, data)
            if output is None:
                return None

            output_files.update(output)

    return output_files
