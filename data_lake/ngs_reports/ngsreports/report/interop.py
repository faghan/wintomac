import logging

from interop import (
    py_interop_plot,
    py_interop_run_metrics,
    py_interop_run,
    py_interop_summary,
)

import ngsreports.report.constants as consts


_LOG_NAME = "interop"


def iterop(obj, size=None):
    """Helper function designed to simplify iteration over interop collections; these
    tend to have either an 'at' or an __getitem__ function (blah[i]). The number of
    objects can usually, but not always, be retrieved using 'size', so a 'size'
    parameter is used for those cases.
    """
    size = obj.size() if size is None else size

    if hasattr(obj, "__getitem__"):
        for idx in range(size):
            yield obj[idx]
    elif hasattr(obj, "at"):
        for idx in range(size):
            yield obj.at(idx)
    else:
        raise TypeError(obj)


def load(root, instrument="MiSeq"):
    if instrument not in consts.INSTRUMENTS_BY_NAME:
        raise ValueError(instrument)

    log = logging.getLogger(_LOG_NAME)
    log.info("reading %s run from %s", instrument, str(root))

    run_metrics = py_interop_run_metrics.run_metrics()
    valid_to_load = py_interop_run.uchar_vector(py_interop_run.MetricCount, 0)
    # Load summary metrics
    py_interop_run_metrics.list_summary_metrics_to_load(
        valid_to_load, consts.INSTRUMENTS_BY_NAME[instrument].enum
    )
    # Load indexing metrics
    py_interop_run_metrics.list_index_metrics_to_load(valid_to_load)

    run_metrics.read(str(root), valid_to_load)

    return run_metrics


def summarize(run_metrics):
    summary = py_interop_summary.run_summary()
    py_interop_summary.summarize_run_metrics(run_metrics, summary)
    idx = py_interop_summary.index_flowcell_summary()
    py_interop_summary.summarize_index_metrics(run_metrics, idx)

    return summary, idx


def plot_by_cycle(metrics, metric):
    if metric not in consts.CYCLE_METRICS_BY_NAME:
        raise ValueError(metric)

    data = py_interop_plot.candle_stick_plot_data()
    options = _new_options(metrics)

    py_interop_plot.plot_by_cycle(metrics, metric, options, data)

    return data


def plot_by_lane(metrics, metric, read=None):
    if metric not in consts.LANE_METRICS_BY_NAME:
        raise ValueError(metric)

    data = py_interop_plot.candle_stick_plot_data()
    options = _new_options(metrics)
    if read is not None:
        options.read(read)

    py_interop_plot.plot_by_lane(metrics, metric, options, data)

    return data


def plot_by_flowcell(metrics, metric):
    if metric not in consts.FLOWCELL_METRICS_BY_NAME:
        raise ValueError(metric)

    data = py_interop_plot.flowcell_data()
    options = _new_options(metrics)

    py_interop_plot.plot_flowcell_map(metrics, metric, options, data)

    return data


def plot_qscore_histogram(metrics, read=0, acceptable_q=30):
    data = py_interop_plot.bar_plot_data()
    options = _new_options(metrics)
    options.read(read)

    py_interop_plot.plot_qscore_histogram(metrics, options, data, acceptable_q)

    return data


def plot_qscore_heatmap(metrics, lane=0):
    data = py_interop_plot.heatmap_data()
    options = _new_options(metrics)
    options.lane(lane)

    py_interop_plot.plot_qscore_heatmap(metrics, options, data)

    return data


def _new_options(metrics):
    naming_method = metrics.run_info().flowcell().naming_method()

    return py_interop_plot.filter_options(naming_method)
