import math

from reportlab.platypus import Paragraph
from interop.py_interop_summary import metric_stat


def unwrap(value):
    if isinstance(value, Paragraph):
        value = value.text

    if isinstance(value, Formatter):
        value = value._value

    if isinstance(value, metric_stat):
        value = value.mean()

    return value


class Formatter:
    def __init__(self, value):
        self._value = value

    def __str__(self):
        if not isinstance(self._value, metric_stat):
            return self._format(value=self._value)

        metric = self._format(value=self._value.mean())
        stddev = self._format(value=self._value.stddev())

        return f"{metric} ± {stddev}"

    def _format(self, value):
        raise NotImplementedError()


class Number(Formatter):
    def __init__(self, value, scale=1, digits=0):
        super().__init__(value)
        self._scale = scale
        self._digits = digits

    def _format(self, value):
        if math.isnan(value):
            value = 0

        return f"{value * self._scale:,.{self._digits}f}"


class Percentage(Number):
    def __init__(self, value, scale=1, digits=2):
        super().__init__(value, scale, digits)


class YieldG(Formatter):
    def _format(self, value):
        if math.isnan(value):
            return "N/A"

        if value < 1.0:
            return "%.2f Mbp" % (value * 1000,)

        return "%.2f Gbp" % (value,)
