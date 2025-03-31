#!/usr/bin/env python3
from reportlab.platypus import (
    Paragraph,
    Table,
)

from reportlab.lib import colors
from reportlab.lib.units import inch

import ngsreports.report.formatting as fmt
import ngsreports.report.report as report

from .constants import PAGE_WIDTH, STYLES
from .interop import iterop


class RunSummaryTable(Table):
    def __init__(
        self,
        metrics,
        summary,
        index=None,
        instrument_type=None,
        padding=2 * inch,
        fontsize=None,
    ):
        self._instrument_type = instrument_type
        data = self._build_rows(metrics, summary, index)
        style = [
            ("FONT", (0, 0), (0, -1), report.FONT_BOLD),
            ("ALIGN", (1, 0), (1, -1), "RIGHT"),
        ]

        if fontsize is not None:
            style.append(("FONTSIZE", (0, 0), (-1, -1), fontsize))

        for idx in range(1, len(data), 2):
            style.append(("BACKGROUND", (0, idx), (-1, idx), colors.HexColor(0xE7E7E7)))

        width = (PAGE_WIDTH - padding) // 2
        super().__init__(data=data, style=style, colWidths=[width, width])

    def _build_rows(self, metrics, summary, index):
        info = metrics.run_info()
        totals = summary.total_summary()
        date = info.date()

        # Basespace reports the last percent_pf; the reason for this is unknown
        if summary.size():
            items = summary.at(0)
            percent_pf = items.at(items.size() - 1).percent_pf().mean()
        else:
            percent_pf = float("NaN")

        cycles = []
        for row in iterop(summary):
            cycles.append(str(row.read().total_cycles()))

        return [
            ["Date:", f"20{date[:2]}-{date[2:4]}-{date[4:]}"],
            ["Flowcell ID", info.flowcell_id()],
            ["Run ID", info.name()],
            [],
            ["Instrument Name", info.instrument_name()],
            ["Instrument Type", self._instrument_type],
            ["PF", "%s %%" % (fmt.Percentage(percent_pf),)],
            ["≥Q30", "%s %%" % (fmt.Percentage(totals.percent_gt_q30()),)],
            ["Yield", fmt.YieldG(totals.yield_g())],
            ["Cycles", " | ".join(cycles)],
            [],
            ["Indexed", "yes" if info.is_indexed() else "no"],
            ["Paired-end", "yes" if info.is_paired_end() else "no"],
        ]


def build_data_card(
    header,
    rows,
    bigfont=False,
    has_labels=False,
    alignments="Right",
):
    header = list(header)
    rows = list(rows)

    if isinstance(alignments, str):
        alignments = [alignments.title()] * len(header)

    if len(header) != len(alignments):
        raise ValueError(f"{len(header)} alignments required, got {len(alignments)}")

    # A different style for each alignment
    bolds = {
        key: STYLES[f"TableHeadBig{key}" if bigfont else f"TableHead{key}"]
        for key in ("Left", "Right", "Center")
    }

    header_row = []
    # Header is build using Paragraphs, to enable splitting of long column names
    for name, alignment in zip(header, alignments):
        if not isinstance(name, Paragraph):
            name = Paragraph(str(name), style=bolds[alignment.title()])

        header_row.append(name)

    table = [header_row]
    for row in rows:
        row = [cell if isinstance(cell, Paragraph) else str(cell) for cell in row]
        if row and len(row) != len(header):
            raise ValueError(row)

        if row and has_labels and not isinstance(row[0], Paragraph):
            row[0] = Paragraph(row[0], style=bolds[alignments[0].title()])

        table.append(row)

    style = [
        ("FONT", (0, 0), (-1, -1), report.FONT),
        ("SIZE", (0, 0), (-1, -1), 12 if bigfont else 8),
    ]

    if has_labels:
        style.append(("FONT", (0, 1), (0, -1), report.FONT_BOLD))

    for column, alignment in enumerate(alignments):
        style.append(("ALIGN", (column, 0), (column, -1), alignment.upper()))

    for idx in range(1, len(rows) + 1, 2):
        style.append(("BACKGROUND", (0, idx), (-1, idx), colors.HexColor(0xE7E7E7)))

    flowable = Table(table, style=style)
    flowable.csv_header = lambda: [fmt.unwrap(value) for value in header]
    flowable.csv_rows = lambda: ([fmt.unwrap(value) for value in row] for row in rows)

    return flowable


def build_per_read_metrics_card(summary):
    def _build_row(label, cycles, data):
        return [
            label,
            cycles,
            fmt.YieldG(data.yield_g()),
            fmt.YieldG(data.projected_yield_g()),
            fmt.Percentage(data.percent_aligned()),
            fmt.Percentage(data.error_rate()),
            fmt.Number(data.first_cycle_intensity()),
            fmt.Percentage(data.percent_gt_q30()),
        ]

    header = [
        "",
        "Cycles",
        "Yield",
        "Projected Yield",
        "Aligned (%)",
        "Error Rate (%)",
        "Intensity Cycle 1",
        "≥Q30 (%)",
    ]

    rows = []
    for idx, row in enumerate(iterop(summary), start=1):
        label = f"Read {idx}"
        if row.read().is_index():
            label += " (I)"

        rows.append(
            _build_row(
                label=label, cycles=row.read().total_cycles(), data=row.summary()
            )
        )

    rows.append(
        _build_row(
            label="Non-Index\nReads Total",
            cycles=sum(
                row.read().total_cycles()
                for row in iterop(summary)
                if not row.read().is_index()
            ),
            data=summary.nonindex_summary(),
        )
    )
    rows.append(
        _build_row(
            label="Totals",
            cycles=sum(row.read().total_cycles() for row in iterop(summary)),
            data=summary.total_summary(),
        )
    )

    return build_data_card(header=header, rows=rows, has_labels=True)


def build_per_lane_metrics_card(summary, sparse=True):
    header = [
        "Lane",
        "Read",
        "Cluster PF (%)",
        "≥Q30 (%)",
        "Yield",
        "Error Rate (%)",
        "Reads PF",
        "Density",
        "Titles",
        "Intensity",
    ]

    rows = []
    for lane_idx in range(summary.lane_count()):
        lane_label = str(lane_idx + 1)

        for read_idx, read in enumerate(iterop(summary), start=1):
            lane = read.at(lane_idx)

            read_label = f"{read_idx}"
            if read.read().is_index():
                read_label += " (I)"

            if read_idx == 1:
                percent_pf = fmt.Percentage(lane.percent_pf())
                # FIXME: Reads_of does not exactly match BaseSpace; unclear why
                reads_pf = fmt.Number(lane.reads_pf())
                density = fmt.Number(value=lane.density(), scale=0.001)
                tiles = fmt.Number(lane.tile_count())
            elif sparse:
                lane_label = ""
                percent_pf = ""
                reads_pf = ""
                density = ""
                tiles = ""

            rows.append(
                [
                    lane_label,
                    read_label,
                    percent_pf,
                    fmt.Percentage(lane.percent_gt_q30()),
                    fmt.YieldG(lane.yield_g()),
                    fmt.Percentage(lane.error_rate()),
                    reads_pf,
                    density,
                    tiles,
                    fmt.Number(lane.first_cycle_intensity()),
                ]
            )

    return build_data_card(rows=rows, header=header)


def build_per_lane_index_summary(index, bigfont=False):
    header = [
        "Lane",
        "Total Reads",
        "PF Reads",
        "Identified Reads PF (%)",
        "Undetermined Reads PF (%)",
        "CV",
        "Min",
        "Max",
    ]

    rows = [
        [
            lane_idx,
            fmt.Number(lane.total_reads()),
            fmt.Number(lane.total_pf_reads()),
            fmt.Percentage(lane.total_fraction_mapped_reads()),
            fmt.Percentage(100 - lane.total_fraction_mapped_reads()),
            fmt.Number(lane.mapped_reads_cv(), digits=4),
            fmt.Number(lane.min_mapped_reads(), digits=4),
            fmt.Number(lane.max_mapped_reads(), digits=4),
        ]
        for lane_idx, lane in enumerate(iterop(index), start=1)
    ]

    return build_data_card(rows=rows, header=header, bigfont=bigfont)


def build_lane_indexing_counts(counts):
    header = [
        "Index",
        "Biosample",
        "Index 1 (I7)",
        "Index 2 (I5)",
        "Identified Reads PF",
        "Identified Reads PF (%)",
    ]

    rows = [
        [
            item.id(),
            item.sample_id(),
            item.index1(),
            item.index2(),
            fmt.Number(item.cluster_count()),
            fmt.Percentage(item.fraction_mapped()),
        ]
        for item in counts
    ]

    return build_data_card(header=header, rows=rows)
