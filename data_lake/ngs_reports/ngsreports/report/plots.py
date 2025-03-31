#!/usr/bin/env python3
import matplotlib
import matplotlib.pyplot as plt
import matplotlib as mpl

from mpl_toolkits.axes_grid1 import make_axes_locatable

import ngsreports.report.interop as interop
import ngsreports.report.report as report


from .constants import PLOT_LINE_WIDTH
from .interop import iterop
from .utils import split_into_blocks


class NoMetricDataToPlot(Exception):
    pass


class InteropImage(report.DynamicImage):
    def _prepare_data(self, *args, **kwargs):
        data = self._do_prepare_data(*args, **kwargs)
        if data.empty():
            raise NoMetricDataToPlot()

        return data

    def _draw_plot(self, fig, ax, data):
        if not self._do_draw_plot(fig, ax, data):
            ax.set_xlim(data.x_axis().min(), data.x_axis().max())
            ax.set_ylim(data.y_axis().min(), data.y_axis().max())

            ax.set_xlabel(data.x_axis().label())
            ax.set_ylabel(data.y_axis().label())

            fig.tight_layout()

    def _do_prepare_data(self, *args, **kwargs):
        raise NotImplementedError()

    def _do_draw_plot(self, fig, ax, data):
        raise NotImplementedError()


class LaneIndexingPlot(report.DynamicImage):
    def _prepare_data(self, data, **kwargs):
        try:
            lane = next(iterop(data))
        except StopIteration:
            raise NoMetricDataToPlot()

        return list(iterop(lane))

    def _draw_plot(self, fig, ax, data):
        ax.bar(
            x=range(1, len(data) + 1),
            height=[item.fraction_mapped() for item in data],
            width=1,
        )

        plt.xticks(range(0, len(data) + 1, 5))

        ax.set_xlabel("Index Number")
        ax.set_ylabel("Identified Reads PF (%)")

        ax.set_xlim(0, len(data) + 1)

        fig.tight_layout()


class PlotByCycle(InteropImage):
    def _do_prepare_data(self, data, metric):
        return interop.plot_by_cycle(data, metric)

    def _do_draw_plot(self, fig, ax, data):
        legend_labels = []
        legend_objects = []

        for series in iterop(data):
            if series.series_type() == series.Candlestick:
                colorprop = {"color": series.color()}

                boxplot = ax.boxplot(
                    [
                        [it.lower(), it.p25(), it.p50(), it.p75(), it.upper()]
                        for it in iterop(series)
                    ],
                    positions=[point.x() for point in iterop(series)],
                    manage_ticks=False,
                    whiskerprops=colorprop,
                    capprops=colorprop,
                    boxprops=colorprop,
                )

                legend_labels.append(series.title())
                legend_objects.extend(boxplot["boxes"])
            elif series.series_type() == series.Line:
                lines = ax.plot(
                    [point.x() for point in iterop(series)],
                    [point.y() for point in iterop(series)],
                    label=series.title(),
                    color=series.color(),
                    linewidth=PLOT_LINE_WIDTH,
                )

                legend_labels.append(series.title())
                legend_objects.extend(lines)
            else:
                raise NotImplementedError(
                    f"Unsupported cycle plot: {series.series_type()}"
                )

        if any(legend_labels):
            ax.legend(legend_objects, legend_labels)


class PlotByLane(InteropImage):
    def _do_prepare_data(self, data, metric, **kwargs):
        return interop.plot_by_lane(data, metric, **kwargs)

    def _do_draw_plot(self, fig, ax, data):
        labels = []
        boxes = []
        colors = []
        for series in iterop(data):
            colorprop = {"color": series.color()}
            if not any(iterop(series)):
                raise NoMetricDataToPlot()

            result = ax.boxplot(
                [
                    [it.lower(), it.p25(), it.p50(), it.p75(), it.upper()]
                    for it in iterop(series)
                ],
                positions=[point.x() for point in iterop(series)],
                labels=[int(point.x()) for point in iterop(series)],
                whiskerprops=colorprop,
                capprops=colorprop,
                boxprops=colorprop,
            )

            labels.append(series.title())
            boxes.extend(result["boxes"])
            colors.append(series.color())

        legend = ax.legend(boxes, labels)
        for handle, color in zip(legend.legendHandles, colors):
            handle.set_color(color)


class PlotByFlowCell(InteropImage):
    def _do_prepare_data(self, data, metric):
        return interop.plot_by_flowcell(data, metric)

    def _layout_subplots(self, data):
        return (1, data.lane_count())

    def _do_draw_plot(self, fig, axs, data):
        # matplotlib will reduce dimensions by default
        if isinstance(axs, matplotlib.axes.Axes):
            axs = [axs]

        cmap = mpl.colors.LinearSegmentedColormap.from_list(
            "flowcell", ["#0000FF", "#00FFFE", "#FFFE00", "#FFA500"], N=1000
        )

        nrows = data.tile_count()
        values = list(iterop(data, size=data.length()))
        columns = split_into_blocks(values, size=nrows)
        lanes = split_into_blocks(columns, size=data.swath_count())

        norm = matplotlib.colors.Normalize(vmin=min(values), vmax=max(values))

        for ax, lane in zip(axs, lanes):
            rows = list(zip(*lane))

            im = ax.imshow(rows, interpolation="none", aspect="auto", cmap=cmap)
            im.set_norm(norm)

            # For a lighter look
            ax.set_frame_on(False)

            # FIXME: This adds an thick border to the plot; it is unclear why
            ax.grid(which="major", color="black", linestyle="-", linewidth=0.5)

            # Center grid-lines between cells
            ax.set_xticks([idx - 0.5 for idx in range(1, data.swath_count())])
            ax.set_yticks([idx - 0.5 for idx in range(1, len(rows))])

            # Hide tickmarks and labels
            ax.set_xticklabels([])
            ax.set_yticklabels([])
            ax.tick_params(left=False, bottom=False)

        # It is not possible to use tight_layout with a colorbar
        # This is roughly equivalent in terms of margins
        plt.subplots_adjust(0.025, 0.025, 1.05, 0.975)
        fig.colorbar(im, ax=axs)

        return True


class PlotQScoreHistogram(InteropImage):
    def _do_prepare_data(self, data, read=0):
        return interop.plot_qscore_histogram(data, read=read)

    def _do_draw_plot(self, fig, ax, data):
        for series in iterop(data):
            series_type = series.series_type()
            if series_type == series.Bar:
                # Positions are shifted right in order to match the look on BaseSpace
                x = [point.x() + point.width() / 2 for point in iterop(series)]
                y = [point.y() for point in iterop(series)]
                w = [point.width() - 0.05 for point in iterop(series)]

                plt.bar(x, y, width=w, color=series.color())
            elif series_type == series.Line:
                pass  # line indicating Q>=30; this is also shown using colors
            else:
                raise NotImplementedError(series_type)


class PlotQScoreHeatmap(InteropImage):
    def _do_prepare_data(self, data, lane=0):
        return interop.plot_qscore_heatmap(data, lane=lane)

    def _do_draw_plot(self, fig, ax, data):
        cmap = mpl.colors.LinearSegmentedColormap.from_list(
            "wgyr", ["white", "green", "yellow", "red"], N=1000
        )

        columns = data.column_count()
        values = list(iterop(data, size=data.length()))
        rows = list(zip(*split_into_blocks(values, size=columns)))

        im = ax.imshow(
            rows,
            interpolation="none",
            aspect="auto",
            cmap=cmap,
        )

        divider = make_axes_locatable(plt.gca())
        cax = divider.append_axes("right", "4%", pad="3%")
        plt.colorbar(im, cax=cax)
        cbar = plt.colorbar(im, cax=cax)
        cbar.ax.set_ylabel("% Of Max", rotation=-90, va="bottom")
