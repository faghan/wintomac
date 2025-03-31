from collections import namedtuple

from reportlab.rl_config import defaultPageSize

import interop.py_interop_run as _interop_run

from .report import stylesheet as _stylesheet

# Number of single-line rows per page when splitting larger tables
ROWS_PER_PAGE = 32

# A4 width and height in inches
PAGE_WIDTH, PAGE_HEIGHT = defaultPageSize
# Collection of ParagraphStyles
STYLES = _stylesheet()

# Default line-width used for plots
PLOT_LINE_WIDTH = 1


def _by_enum(metrics):
    return {it.enum: it for it in metrics.values()}


_Enum = namedtuple("_Enum", ("enum", "name", "description"))


A = _interop_run.A
C = _interop_run.C
G = _interop_run.G
T = _interop_run.T


INSTRUMENTS_BY_NAME = {
    _it.name: _it
    for _it in (
        _Enum(_interop_run.HiSeq, "HiSeq", "HiSeq"),
        _Enum(_interop_run.HiScan, "HiScan", "HiScan"),
        _Enum(_interop_run.MiSeq, "MiSeq", "MiSeq"),
        _Enum(_interop_run.NextSeq, "NextSeq", "NextSeq"),
        _Enum(_interop_run.MiniSeq, "MiniSeq", "MiniSeq"),
        _Enum(_interop_run.NovaSeq, "NovaSeq", "NovaSeq"),
        _Enum(_interop_run.iSeq, "iSeq", "iSeq"),
        _Enum(
            _interop_run.UnknownInstrument, "UnknownInstrument", "Unknown Instrument"
        ),
    )
}

METRIC_TYPES_BY_NAME = {
    _it.name: _it
    for _it in (
        _Enum(_interop_run.Intensity, "Intensity", "Intensity"),
        _Enum(_interop_run.FWHM, "FWHM", "FWHM"),
        _Enum(_interop_run.BasePercent, "BasePercent", "% Base"),
        _Enum(_interop_run.PercentNoCall, "PercentNoCall", "% Not Called"),
        _Enum(_interop_run.Q20Percent, "Q20Percent", "% >=Q20"),
        _Enum(_interop_run.Q30Percent, "Q30Percent", "% >=Q30"),
        _Enum(_interop_run.AccumPercentQ20, "AccumPercentQ20", "% >=Q20 (Accumulated)"),
        _Enum(_interop_run.AccumPercentQ30, "AccumPercentQ30", "% >=Q30 (Accumulated)"),
        _Enum(_interop_run.QScore, "QScore", "Median QScore"),
        _Enum(_interop_run.Clusters, "Clusters", "Density"),
        _Enum(_interop_run.ClustersPF, "ClustersPF", "Density PF"),
        _Enum(_interop_run.ClusterCount, "ClusterCount", "Cluster Count"),
        _Enum(_interop_run.ClusterCountPF, "ClusterCountPF", "Clusters PF"),
        _Enum(_interop_run.ErrorRate, "ErrorRate", "Error Rate"),
        _Enum(_interop_run.PercentPhasing, "PercentPhasing", "Legacy Phasing Rate"),
        _Enum(
            _interop_run.PercentPrephasing,
            "PercentPrephasing",
            "Legacy Prephasing Rate",
        ),
        _Enum(_interop_run.PercentAligned, "PercentAligned", "% Aligned"),
        _Enum(_interop_run.Phasing, "Phasing", "Phasing Weight"),
        _Enum(_interop_run.PrePhasing, "PrePhasing", "Prephasing Weight"),
        _Enum(_interop_run.CorrectedIntensity, "CorrectedIntensity", "Corrected Int"),
        _Enum(_interop_run.CalledIntensity, "CalledIntensity", "Called Int"),
        _Enum(_interop_run.SignalToNoise, "SignalToNoise", "Signal to Noise"),
        _Enum(_interop_run.OccupiedCountK, "OccupiedCountK", "Occupied Count (K)"),
        _Enum(_interop_run.PercentOccupied, "PercentOccupied", "% Occupied"),
        _Enum(_interop_run.PercentPF, "PercentPF", "% PF"),
        _Enum(_interop_run.UnknownMetricType, "UnknownMetricType", ""),
    )
}

CYCLE_METRICS_BY_NAME = {
    key: METRIC_TYPES_BY_NAME[key]
    for key in [
        "Intensity",
        "FWHM",
        "BasePercent",
        "PercentNoCall",
        "Q20Percent",
        "Q30Percent",
        "QScore",
        "ErrorRate",
        "CorrectedIntensity",
        "CalledIntensity",
        "SignalToNoise",
    ]
}

LANE_METRICS_BY_NAME = {
    key: METRIC_TYPES_BY_NAME[key]
    for key in [
        "Clusters",
        "ClusterCount",
        "PercentPhasing",
        "PercentPrephasing",
        "PercentAligned",
        "PercentPF",
    ]
}

FLOWCELL_METRICS_BY_NAME = {
    key: METRIC_TYPES_BY_NAME[key]
    for key in [
        "Clusters",
        "ClustersPF",
        "ClusterCount",
        "ClusterCountPF",
        "PercentPF",
    ]
}


CYCLE_METRICS = _by_enum(CYCLE_METRICS_BY_NAME)
FLOWCELL_METRICS = _by_enum(FLOWCELL_METRICS_BY_NAME)
INSTRUMENTS = _by_enum(INSTRUMENTS_BY_NAME)
LANE_METRICS = _by_enum(LANE_METRICS_BY_NAME)
METRIC_TYPES = _by_enum(METRIC_TYPES_BY_NAME)
