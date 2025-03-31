import io

import matplotlib.pyplot as plt

import reportlab.lib.enums as enums

from reportlab.lib.fonts import tt2ps
from reportlab.lib.styles import ParagraphStyle, StyleSheet1
from reportlab.lib.units import inch
from reportlab.platypus import Flowable, Image
from reportlab.rl_config import canvas_basefontname
from reportlab.rl_config import defaultPageSize

from svglib.svglib import svg2rlg


PAGE_WIDTH, PAGE_HEIGHT = defaultPageSize
FLOWABLE_WIDTH = PAGE_WIDTH - 2 * inch

IMAGE_WIDTH = PAGE_WIDTH - inch
# This height allows for 2 images, 1 H1, and 2 H2s on a single page
IMAGE_HEIGHT = 4.35 * inch

FONT = canvas_basefontname
FONT_BOLD = tt2ps(FONT, 1, 0)
FONT_ITALICS = tt2ps(FONT, 0, 1)


class DynamicImage(Image):
    def __init__(self, width=IMAGE_WIDTH, height=IMAGE_HEIGHT, sharex=False, **kwargs):
        data = self._prepare_data(**kwargs)
        nrows, ncols = self._layout_subplots(data)
        fig, ax = plt.subplots(
            nrows, ncols, figsize=(width / inch, height / inch), sharex=sharex,
        )
        try:
            self._draw_plot(fig, ax, data)
            image = self._render_to_rlg(fig)
        finally:
            plt.close()

        super().__init__(filename=image, width=width, height=height)

    def _prepare_data(self, **kwargs):
        raise NotImplementedError()

    def _layout_subplots(self, data):
        return (1, 1)

    def _draw_plot(self, fig, ax, data):
        raise NotImplementedError()

    def _render_to_rlg(self, figure):
        data = io.BytesIO()
        figure.savefig(data, format="svg")
        data.seek(0)

        return svg2rlg(data)


class DocumentTitle(Flowable):
    def __init__(self, text, width=PAGE_WIDTH - 2 * inch):
        super().__init__()

        self.width = width
        self.height = 0.25 * inch
        self.text = text

    def draw(self):
        canvas = self.canv
        canvas.setFont("Times-Bold", 16)
        canvas.drawCentredString(self.width / 2, 0.125 * inch, self.text)


class NoData(Flowable):
    def __init__(self, width, height):
        super().__init__()

        self.width = width
        self.height = height

    def draw(self):
        canvas = self.canv

        size = inch
        fontsize = 24
        margin = 0.1 * size

        left = self.width / 2 - size / 2
        bottom = self.height / 2 - size / 2 + fontsize / 2 + margin * 2
        right = left + size
        top = bottom + size

        canvas.setStrokeColorRGB(0.5, 0.5, 0.5)
        canvas.rect(x=0, y=0, width=self.width, height=self.height)

        canvas.setFont("Times-Bold", 24)
        canvas.setFillColorRGB(0.5, 0.5, 0.5)
        canvas.drawCentredString(
            x=self.width / 2, y=bottom - 2 * margin - 12, text="Plot not available",
        )

        canvas.setLineWidth(5)
        canvas.setStrokeColorRGB(0.7, 0.3, 0.3)
        canvas.line(left + margin, bottom + margin, right - margin, top - margin)
        canvas.line(left + margin, top - margin, right - margin, bottom + margin)


def stylesheet():
    Style = ParagraphStyle
    sheet = StyleSheet1()
    add = sheet.add

    add(Style(name="Normal", fontName=FONT, fontSize=10, leading=12))
    add(Style(name="BodyText", parent=sheet["Normal"], spaceBefore=6))
    add(Style(name="Italic", parent=sheet["BodyText"], fontName=FONT_ITALICS))
    add(Style(name="Bold", parent=sheet["BodyText"], fontName=FONT_BOLD))

    add(
        Style(
            name="Title",
            parent=sheet["Normal"],
            fontName=FONT_BOLD,
            fontSize=14,
            leading=16,
            alignment=enums.TA_CENTER,
        )
    )

    add(
        Style(
            name="Heading1",
            parent=sheet["Normal"],
            fontName=FONT_BOLD,
            fontSize=16,
            leading=14,
            spaceAfter=12,
        ),
        alias="H1",
    )

    add(
        Style(
            name="Heading2",
            parent=sheet["Normal"],
            fontName=FONT_BOLD,
            fontSize=12,
            leading=14,
            leftIndent=0.1 * inch,
        ),
        alias="H2",
    )

    add(Style(name="TOC1", parent=sheet["H1"], fontSize=12))
    add(Style(name="TOC2", parent=sheet["H2"], fontSize=10, leftIndent=inch / 4))

    for (key, alignment) in [
        ("Left", enums.TA_LEFT),
        ("Right", enums.TA_RIGHT),
        ("Center", enums.TA_CENTER),
    ]:
        add(
            Style(
                name=f"TableHead{key}",
                parent=sheet["Normal"],
                fontSize=8,
                fontName=FONT_BOLD,
                alignment=alignment,
            )
        )
        add(
            Style(
                name=f"TableHeadBig{key}", parent=sheet[f"TableHead{key}"], fontSize=12
            )
        )

    return sheet
