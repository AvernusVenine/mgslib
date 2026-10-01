"""What every plot shares: axes, colours, legend, sample count, save and show."""

from __future__ import annotations

import warnings

import matplotlib
import matplotlib.patheffects as patheffects
import matplotlib.pyplot as plt
import pandas as pd

from ..data.cleaning import FLAG_DUPLICATE

# Chart colours.
SURFACE = "#fcfcfb"
INK = "#0b0b0b"
INK_SECONDARY = "#52514e"
MUTED = "#898781"
GRID = "#e1e0d9"
AXIS = "#c3c2b7"
# Group colours, always used in this order.
SERIES = ["#2a78d6", "#eb6834", "#1baf7a", "#eda100", "#e87ba4", "#008300", "#4a3aa7", "#e34948"]
OTHER = "#898781"

MARKER_SIZE = 30
FIELD_LINE = {"color": MUTED, "linewidth": 1.0, "zorder": 1}
# Field names sit above the points, with a pale outline so they stay readable.
HALO = [patheffects.withStroke(linewidth=2.5, foreground=SURFACE)]
FIELD_TEXT = {"color": INK_SECONDARY, "fontsize": 8, "ha": "center", "va": "center", "zorder": 5,
              "path_effects": HALO}
LEGEND_WIDTH = 2.7   # inches added to the right of a figure for the legend


class NothingToPlot(ValueError):
    """Raised when no sample has the analytes a plot needs."""


def new_axes(ax=None, ternary=False, figsize=(7.0, 6.0), legend=False):
    """Return ``(ax, created)``: the axes to draw on and whether we made it.
    ``legend`` leaves room on the right for a legend."""
    if ax is not None:
        return ax, False
    if legend:
        figsize = (figsize[0] + LEGEND_WIDTH, figsize[1])
    figure = plt.figure(figsize=figsize, facecolor=SURFACE)
    if ternary:
        import mpltern  # noqa: F401  (registers the "ternary" projection)
        ax = figure.add_subplot(projection="ternary")
    else:
        ax = figure.add_subplot()
    style_axes(ax, ternary)
    return ax, True


def style_axes(ax, ternary=False):
    ax.set_facecolor(SURFACE)
    ax.tick_params(colors=INK_SECONDARY, labelsize=9)
    if ternary:
        return
    for side in ("top", "right"):
        ax.spines[side].set_visible(False)
    for side in ("left", "bottom"):
        ax.spines[side].set_color(AXIS)
    ax.grid(True, color=GRID, linewidth=0.6, zorder=0)
    ax.set_axisbelow(True)


def complete_rows(table: pd.DataFrame, what: str) -> pd.DataFrame:
    """Keep the rows that have every value; complain clearly if none do."""
    table = table.replace([float("inf"), float("-inf")], float("nan"))
    kept = table.dropna()
    if kept.empty:
        missing = [str(c) for c in table.columns if table[c].notna().sum() == 0]
        detail = (f"The data has no values for: {', '.join(missing)}." if missing else
                  f"No sample has all of: {', '.join(str(c) for c in table.columns)}.")
        raise NothingToPlot(f"Nothing to plot for {what}. {detail}")
    return kept


def groups(data, rows, color_by):
    """Split rows into coloured groups.

    Returns a list of ``(label, colour, row index)``.  With more groups than
    there are colours, the smallest ones are combined as "Other".
    """
    if color_by is None:
        return [(None, SERIES[0], rows)]
    if color_by not in data.df.columns:
        choices = [c.name for c in data.column_info if not c.is_analyte and not c.numeric]
        raise ValueError(f"Cannot colour by '{color_by}': no such column. "
                         f"Try one of: {', '.join(choices)}.")
    # Colours are fixed by the whole table, not by the rows a plot happens to
    # use, so a group keeps its colour from one diagram to the next.
    everyone = data.df[color_by].astype(object)
    everyone = everyone.where(everyone.notna(), "Not recorded").astype(str)
    names = list(everyone.value_counts().index)
    if len(names) > len(SERIES):
        names = names[:len(SERIES) - 1]
    labels = everyone.loc[rows]
    result = []
    for colour, name in zip(SERIES, names):
        members = rows[(labels == name).to_numpy()]
        if len(members):
            result.append((name, colour, members))
    rest = rows[(~labels.isin(names)).to_numpy()]
    if len(rest):
        result.append(("Other", OTHER, rest))
    return result


def scatter(ax, data, table: pd.DataFrame, color_by=None):
    """Draw one point per row of ``table`` (2 columns, or 3 for a ternary)."""
    for label, colour, rows in groups(data, table.index, color_by):
        columns = [table.loc[rows, c] for c in table.columns]
        ax.scatter(*columns, s=MARKER_SIZE, marker="o", color=colour, edgecolors=SURFACE, linewidths=0.6,
                   alpha=0.9, label=label, zorder=3)


def finish(ax, data, plotted, title, color_by, created, save, show, legend=True):
    """Title, legend, sample count, duplicate reminder, then save and show."""
    figure = ax.figure
    if title:
        ax.set_title(title, color=INK, fontsize=12, pad=14 if ax.name == "ternary" else 8)
    figure.text(0.99, 0.01, f"n = {plotted:,} of {len(data):,} samples", ha="right", va="bottom",
                color=MUTED, fontsize=8)
    remind_about_duplicates(data)
    if created:
        with warnings.catch_warnings():
            warnings.simplefilter("ignore")   # ternary axes are not fully tight-layout aware
            figure.tight_layout()
    if legend and color_by is not None:
        if created:   # the legend goes in the space kept free on the right
            width = figure.get_size_inches()[0]
            figure.subplots_adjust(right=min(figure.subplotpars.right, 1 - LEGEND_WIDTH / width))
            add_legend(figure, color_by, source=ax, loc="center left",
                       bbox_to_anchor=(1 - LEGEND_WIDTH / width + 0.01, 0.5))
        else:
            add_legend(ax, color_by)
    if save:
        figure.savefig(save, dpi=200, facecolor=SURFACE)
    if show and created and matplotlib.get_backend().lower() != "agg":
        plt.show()
    return ax


def halo_texts(ax):
    """Restyle field names drawn by a pyrolite template to match ours."""
    for text in ax.texts:
        text.set_color(INK_SECONDARY)
        text.set_path_effects(HALO)
        text.set_zorder(5)


def add_legend(target, color_by, source=None, **options):
    """Add a legend to ``target`` (axes or figure) from the labelled marks on ``source``."""
    handles, labels = (source or target).get_legend_handles_labels()
    unique = dict(zip(labels, handles))
    if not unique:
        return
    settings = {"title": color_by.replace("_", " ").capitalize(), "fontsize": 8, "title_fontsize": 8,
                "frameon": False, "labelcolor": INK_SECONDARY}
    settings.update(options)
    legend = target.legend(unique.values(), unique.keys(), **settings)
    legend.get_title().set_color(INK_SECONDARY)


def remind_about_duplicates(data):
    if FLAG_DUPLICATE in data.df.columns:
        count = int(data.df[FLAG_DUPLICATE].sum())
        if count:
            print(f"Note: {count:,} of these rows are flagged as duplicates and are plotted more "
                  "than once. Use data.remove_duplicates() first to plot each sample once.")
