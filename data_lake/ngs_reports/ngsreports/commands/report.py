#!/usr/bin/env python3
import csv
import logging

from reportlab.platypus import (
    Frame,
    FrameBreak,
    PageBreak,
    PageTemplate,
    Paragraph,
    Spacer,
)
from reportlab.lib.units import inch
from reportlab.platypus.doctemplate import BaseDocTemplate
from reportlab.platypus.tableofcontents import TableOfContents

import ngsreports.report.constants as consts
import ngsreports.report.report as report

from ngsreports.report.constants import PAGE_WIDTH, STYLES, ROWS_PER_PAGE
from ngsreports.report.plots import (
    LaneIndexingPlot,
    NoMetricDataToPlot,
    PlotByCycle,
    PlotByFlowCell,
    PlotByLane,
    PlotQScoreHeatmap,
    PlotQScoreHistogram,
)
from ngsreports.report.tables import (
    build_lane_indexing_counts,
    build_per_lane_index_summary,
    build_per_lane_metrics_card,
    build_per_read_metrics_card,
    RunSummaryTable,
)
from ngsreports.report.interop import iterop
from ngsreports.report.utils import split_into_blocks
from ngsreports.xmlsheet import IlluminaXML


_LOG_NAME = "report"


class NumberedPage:
    def __call__(self, canvas, doc):
        canvas.saveState()
        canvas.setFont("Times-Roman", 9)
        canvas.drawCentredString(PAGE_WIDTH / 2, 0.75 * inch, "Page %d " % (doc.page,))
        canvas.restoreState()


class DocTemplateWithTOS(BaseDocTemplate):
    def __init__(self, filename, **kw):
        super().__init__(filename, **kw)

        self.allowSplitting = 0

    def afterFlowable(self, flowable):
        if isinstance(flowable, Paragraph):
            text = flowable.getPlainText()
            if hasattr(flowable, "toctitle"):
                text = flowable.toctitle
                if text is None:
                    return

            if flowable.style == STYLES["H1"]:
                self.notify("TOCEntry", (0, text, self.page))
            elif flowable.style == STYLES["H2"]:
                self.notify("TOCEntry", (1, text, self.page))


def add_charts(log, cls, title, data, metrics):
    yield Paragraph(title, style=STYLES["H1"])

    nth_plot = 0
    for _, metric in sorted(metrics.items()):
        name = metric.description

        try:
            log.info("plotting [%s]: %s", metric.name, metric.description)
            plot = cls(data=data, metric=metric.name)
        except NoMetricDataToPlot:
            log.warning("Not data for cycle metric %r; skipping plots", name)
        else:
            if nth_plot % 2 == 0 and nth_plot:
                yield PageBreak()
            title = Paragraph(name, style=STYLES["H2"])
            title.toctitle = None
            yield title
            yield plot
            nth_plot += 1

    if nth_plot:
        yield PageBreak()


def experiment_name(root):
    # Variation in filename case (Run vs run) observed
    for filepath in sorted(root.iterdir()):
        if filepath.name.lower() == "runparameters.xml":
            params = IlluminaXML.from_file(filepath)

            try:
                return (
                    params.first_child("RunParameters")
                    .first_child("ExperimentName")
                    .data
                )
            except KeyError:
                pass

    return "Unknown experiment"


def instrument_type(metrics, fallback=None):
    params = metrics.run_parameters()
    instrument = consts.INSTRUMENTS[params.instrument_type()]

    if instrument.name == "UnknownInstrument" and fallback is not None:
        instrument = consts.INSTRUMENTS_BY_NAME[fallback]

    return instrument.description


def build_full_pdf(args, metrics, summary, index):
    log = logging.getLogger(_LOG_NAME)

    destination = args.output / "report.pdf"
    log.info("Building full NGS report at '%s'", destination)

    toc = TableOfContents()
    toc.levelStyles = [STYLES["TOC1"], STYLES["TOC2"]]

    items = [
        report.DocumentTitle(experiment_name(args.run)),
        Spacer(1, 0.2 * inch),
        RunSummaryTable(
            metrics=metrics,
            summary=summary,
            instrument_type=instrument_type(metrics, args.instrument),
        ),
        Spacer(1, 0.5 * inch),
        toc,
        PageBreak(),
        Paragraph("Run Metrics", style=STYLES["H1"]),
        Paragraph("Per Read", style=STYLES["H2"]),
        build_per_read_metrics_card(summary=summary),
        Spacer(1, 0.2 * inch),
        Paragraph("Per Lane", style=STYLES["H2"]),
        build_per_lane_metrics_card(summary=summary),
        PageBreak(),
        Paragraph("Indexing QC", style=STYLES["H1"]),
        Spacer(1, 0.2 * inch),
        build_per_lane_index_summary(index=index),
        Spacer(1, 0.2 * inch),
    ]

    try:
        plot = LaneIndexingPlot(data=index)
        items.extend((plot, PageBreak()))
    except NoMetricDataToPlot:
        pass

    for lane_idx, lane in enumerate(iterop(index), start=1):
        counts = list(iterop(lane))
        blocks = split_into_blocks(counts, size=ROWS_PER_PAGE)
        for idx, block in enumerate(blocks, start=1):
            title = Paragraph(f"Lane {lane_idx} [{idx}/{len(blocks)}]", STYLES["H2"])
            title.toctitle = f"Lane {lane_idx}" if idx == 1 else None

            items.append(title)
            items.append(build_lane_indexing_counts(counts=block))
            items.append(PageBreak())

    items.append(Paragraph("Quality Scores", style=STYLES["H1"]))

    log.info("plotting quality score histogram")
    try:
        plot = PlotQScoreHistogram(data=metrics)
        items.append(Paragraph("Histogram", style=STYLES["H2"]))
        items.append(plot)
    except NoMetricDataToPlot:
        log.warning("no data to plot quality score histogram")

    log.info("plotting quality score heatmaps")
    try:
        plot = PlotQScoreHeatmap(data=metrics)
        items.append(Paragraph("Heatmap", style=STYLES["H2"]))
        items.append(plot)
    except NoMetricDataToPlot:
        log.warning("no data to plot quality score heatmap")

    metric_plots = [
        ["cycle", PlotByCycle, consts.CYCLE_METRICS],
        ["lane", PlotByLane, consts.LANE_METRICS],
        ["flowcell", PlotByFlowCell, consts.FLOWCELL_METRICS],
    ]

    for name, cls, enums in metric_plots:
        log.info("plotting by cycle")
        items.extend(
            add_charts(
                cls=cls,
                log=log,
                title=f"Charts by {name.title()}",
                data=metrics,
                metrics=enums,
            )
        )

    doc = DocTemplateWithTOS(str(destination))
    doc.addPageTemplates(
        PageTemplate(
            id="First",
            frames=Frame(
                doc.leftMargin, doc.bottomMargin, doc.width, doc.height, id="normal"
            ),
            onPage=NumberedPage(),
            pagesize=doc.pagesize,
        )
    )

    log.info("building document")
    doc.multiBuild(items)
    log.info("done")

    return {"RunMetrics": destination}


def build_one_page_pdf(args, metrics, summary, index):
    log = logging.getLogger(_LOG_NAME)

    destination = args.output / "1page.pdf"
    log.info("Building 1-page NGS report at %r", destination)

    default_padding = {
        "leftPadding": inch / 4,
        "rightPadding": inch / 4,
        "topPadding": 0,
        "bottomPadding": 0,
    }

    scale = 1.5 * inch
    pagesize = (16 * scale, 9 * scale)
    doc = BaseDocTemplate(
        str(destination),
        pagesize=pagesize,
        showBoundary=0,
        leftMargin=inch / 4,
        rightMargin=inch / 4,
        topMargin=inch / 8,
        bottomMargin=inch / 8,
    )

    regular_image_width = doc.width * 3 / 8 - inch / 4
    regular_image_height = doc.height * 5 / 17 - inch / 2

    alt_image_width = doc.width * 2 / 8 - inch / 4
    alt_image_height = doc.height * 10 / 17 - inch / 2

    def _frame(x1, y1, width, height):
        return Frame(
            x1=doc.leftMargin + doc.width * x1,
            y1=doc.bottomMargin + doc.height * y1,
            width=doc.width * width,
            height=doc.height * height,
            **default_padding,
        )

    frames = [
        # Top row
        _frame(x1=0 / 8, y1=10 / 17, width=2 / 8, height=7 / 17),
        _frame(x1=2 / 8, y1=15 / 17, width=6 / 8, height=2 / 17),
        _frame(x1=2 / 8, y1=10 / 17, width=3 / 8, height=5 / 17),
        _frame(x1=5 / 8, y1=10 / 17, width=3 / 8, height=5 / 17),
        # Middle row
        _frame(x1=0 / 8, y1=0 / 17, width=2 / 8, height=10 / 17),
        _frame(x1=2 / 8, y1=5 / 17, width=3 / 8, height=5 / 17),
        _frame(x1=5 / 8, y1=5 / 17, width=3 / 8, height=5 / 17),
        # Bottom row
        _frame(x1=2 / 8, y1=0 / 17, width=3 / 8, height=5 / 17),
        _frame(x1=5 / 8, y1=0 / 17, width=3 / 8, height=5 / 17),
    ]

    def _image(cls, *args, **kwargs):
        kwargs.setdefault("width", regular_image_width)
        kwargs.setdefault("height", regular_image_height)

        try:
            return cls(*args, **kwargs)
        except NoMetricDataToPlot:
            return report.NoData(width=kwargs["width"], height=kwargs["height"])

    items = [
        Paragraph(experiment_name(args.run), style=STYLES["H1"]),
        RunSummaryTable(
            metrics=metrics,
            summary=summary,
            index=index,
            instrument_type=instrument_type(metrics, args.instrument),
            padding=3 * inch,
            fontsize=14,
        ),
        FrameBreak(),
        #
        build_per_lane_index_summary(index, bigfont=True),
        FrameBreak(),
        #
        Paragraph("Intensity by Cycle", style=STYLES["H1"]),
        _image(PlotByCycle, data=metrics, metric="Intensity"),
        FrameBreak(),
        #
        Paragraph("QScore Distribution", style=STYLES["H1"]),
        _image(PlotQScoreHistogram, data=metrics),
        FrameBreak(),
        #
        Paragraph("Density PF", style=STYLES["H1"]),
        _image(
            PlotByFlowCell,
            data=metrics,
            width=alt_image_width,
            height=alt_image_height,
            metric="ClustersPF",
        ),
        FrameBreak(),
        #
        Paragraph("% Aligned by Lane (Read 1)", style=STYLES["H1"]),
        _image(PlotByLane, data=metrics, metric="PercentAligned", read=1),
        FrameBreak(),
        #
        Paragraph("QScore Heatmap", style=STYLES["H1"]),
        _image(PlotQScoreHeatmap, data=metrics),
        FrameBreak(),
        Paragraph("Error Rate by Cycle", style=STYLES["H1"]),
        _image(PlotByCycle, data=metrics, metric="ErrorRate"),
        FrameBreak(),
        Paragraph("Indexing QC", style=STYLES["H1"]),
        _image(LaneIndexingPlot, data=index),
    ]

    doc.addPageTemplates([PageTemplate(frames=frames)])

    log.info("building document")
    doc.build(items)
    log.info("done")

    return {"RunSummary": destination}


class CSVWriter:
    def __init__(self, filename):
        self._handle = open(filename, "wt", newline="")
        self._writer = csv.writer(
            self._handle,
            delimiter="\t",
            quotechar='"',
            quoting=csv.QUOTE_MINIMAL,
        )

    def writerow(self, row, extras=[]):
        if extras:
            row = extras + row

        self._writer.writerow(row)

    def writerows(self, rows, extras=[]):
        for row in rows:
            self.writerow(row, extras)

    def __enter__(self, *args, **kwargs):
        return self

    def __exit__(self, *args, **kwargs):
        self._handle.close()


def build_csv(args, metrics, summary, index):
    log = logging.getLogger(_LOG_NAME)
    log.info("Building CVS tables for '%s'", args.output)

    extra_headers = ["Run ID"]
    extra_values = [metrics.run_info().name()]

    with CSVWriter(args.output / "read_metrics.csv") as writer:
        card = build_per_read_metrics_card(summary=summary)
        header = card.csv_header()
        header[0] = "Read"

        writer.writerow(header, extra_headers)
        writer.writerows(card.csv_rows(), extra_values)

    with CSVWriter(args.output / "lane_metrics.csv") as writer:
        card = build_per_lane_metrics_card(summary=summary, sparse=False)
        writer.writerow(card.csv_header(), extra_headers)
        writer.writerows(card.csv_rows(), extra_values)

    with CSVWriter(args.output / "index_summary.csv") as writer:
        card = build_per_lane_index_summary(index=index)
        writer.writerow(card.csv_header(), extra_headers)
        writer.writerows(card.csv_rows(), extra_values)

    with CSVWriter(args.output / "indexing.csv") as writer:
        for idx, lane in enumerate(iterop(index), start=1):
            card = build_lane_indexing_counts(counts=list(iterop(lane)))

            if idx == 1:
                writer.writerow(card.csv_header(), extra_headers + ["Lane"])

            writer.writerows(card.csv_rows(), extra_values + [idx])

    return {
        "Tables": [
            args.output / "read_metrics.csv",
            args.output / "lane_metrics.csv",
            args.output / "index_summary.csv",
            args.output / "indexing.csv",
        ]
    }


COMMANDS = {
    "1page": [build_one_page_pdf],
    "all": [build_one_page_pdf, build_csv, build_full_pdf],
    "csv": [build_csv],
    "full": [build_full_pdf],
}


def main(args, data):
    log = logging.getLogger(_LOG_NAME)

    commands = []
    for name in args.reports:
        funcs = COMMANDS.get(name)
        if funcs is None:
            log.error("Unknown command %r", args.command)
            return 1

        for func in funcs:
            if func not in commands:
                commands.append(func)

    if not commands:
        commands = COMMANDS["all"]

    args.output.mkdir(parents=True, exist_ok=True)

    output_files = {}
    for command in commands:
        files = command(
            args=args,
            metrics=data.metrics,
            summary=data.summary,
            index=data.index,
        )

        if files is None:
            return None

        output_files.update(files)

    return output_files
