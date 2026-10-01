"""X-Y diagrams.  Each takes a GeochemData object and works out the rest."""

from __future__ import annotations

import math

import matplotlib
import matplotlib.pyplot as plt
import numpy as np
import pandas as pd

from .. import chemistry as chem
from . import _fields as fields
from ._figure import (FIELD_LINE, FIELD_TEXT, INK, INK_SECONDARY, MUTED, SURFACE, NothingToPlot,
                      add_legend, complete_rows, finish, groups, halo_texts, new_axes,
                      remind_about_duplicates, scatter, style_axes)

HARKER_DEFAULTS = ["Al2O3", "MgO", "FeOt", "CaO", "Na2O", "TiO2", "K2O", "P2O5", "Mg#",
                   "Rb", "Sr", "Ba", "Zr", "La/Yb"]

SIO2_LABEL = "SiO2 (wt%)"


def _xy(data, x, y, what, title, color_by, ax, save, show, xlabel, ylabel, fields_drawer=None,
        log=False, xlim=None, ylim=None):
    """The common path for a single X-Y diagram."""
    table = complete_rows(pd.DataFrame({"x": x, "y": y}), what)
    if log:
        table = complete_rows(table.where(table > 0), what)
    ax, created = new_axes(ax, legend=color_by is not None)
    if log:
        ax.set_xscale("log" if log in ("both", "x") else "linear")
        ax.set_yscale("log" if log in ("both", "y") else "linear")
    if xlim:
        ax.set_xlim(*xlim)
    if ylim:
        ax.set_ylim(*ylim)
    scatter(ax, data, table, color_by)
    if fields_drawer:
        fields_drawer(ax)
    ax.set_xlabel(xlabel, color=INK_SECONDARY)
    ax.set_ylabel(ylabel, color=INK_SECONDARY)
    return finish(ax, data, len(table), title, color_by, created, save, show)


def Harker(data, x="SiO2", y=None, color_by=None, title=None, save=None, show=True, columns=4):
    """Harker variation diagrams: a grid of panels against one X axis.

    x : what goes on every X axis (default "SiO2").
    y : list of what to plot, one panel each.  Each entry is an analyte
        ("MgO", "Zr"), a sum ("Na2O+K2O"), a ratio ("La/Yb") or "Mg#", "Fe#",
        "ASI", "MALI", "A/CNK", "A/NK", "CIA".  Oxides are in wt%, elements in ppm.
        Default: Al2O3, MgO, FeOt, CaO, Na2O, TiO2, K2O, P2O5, Mg#, Rb, Sr, Ba,
        Zr and La/Yb.

    Returns the matplotlib figure.
    """
    y = HARKER_DEFAULTS if y is None else ([y] if isinstance(y, str) else list(y))
    x_values, x_label = chem.evaluate(data, x)
    columns = min(columns, len(y))
    rows = math.ceil(len(y) / columns)
    figure, axes = plt.subplots(rows, columns, figsize=(3.4 * columns, 2.7 * rows + 0.6),
                                facecolor=SURFACE, squeeze=False, sharex=True)
    plotted = pd.Index([])
    for panel, name in zip(axes.flat, y):
        style_axes(panel)
        y_values, y_label = chem.evaluate(data, name)
        table = pd.DataFrame({"x": x_values, "y": y_values})
        table = table.replace([np.inf, -np.inf], np.nan).dropna()
        panel.set_ylabel(y_label, color=INK_SECONDARY, fontsize=9)
        if table.empty:
            panel.text(0.5, 0.5, "no data", transform=panel.transAxes, ha="center", va="center",
                       color=MUTED, fontsize=9)
            continue
        scatter(panel, data, table, color_by)
        plotted = plotted.union(table.index)
    for panel in axes.flat[len(y):]:
        panel.set_visible(False)
    for column in range(columns):
        shown = [axes[row][column] for row in range(rows) if axes[row][column].get_visible()]
        shown[-1].set_xlabel(x_label, color=INK_SECONDARY, fontsize=9)
        shown[-1].tick_params(labelbottom=True)
    if not len(plotted):
        plt.close(figure)
        raise NothingToPlot(f"Nothing to plot for the Harker diagrams: no sample has {x} together "
                            f"with any of {', '.join(y)}.")

    figure.suptitle(title or f"Harker diagrams ({x})", color=INK, fontsize=12)
    figure.text(0.995, 0.005, f"n = {len(plotted):,} of {len(data):,} samples", ha="right",
                va="bottom", color=MUTED, fontsize=8)
    figure.tight_layout(rect=(0, 0.02, 1, 0.98))
    if color_by is not None:
        handles = {}
        for panel in axes.flat:
            found, names = panel.get_legend_handles_labels()
            handles.update(dict(zip(names, found)))
        key = figure.add_axes((0, 0, 0.01, 0.01))   # invisible holder for the legend entries
        key.axis("off")
        for name, _, _ in groups(data, plotted, color_by):
            key.scatter([], [], marker="o", color=handles[name].get_facecolor()[0], label=name)
        spare = list(axes.flat[len(y):])
        if spare:   # the legend goes where the first unused panel would be
            box = spare[0].get_position()
            add_legend(figure, color_by, source=key, loc="center",
                       bbox_to_anchor=(box.x0 + box.width / 2, box.y0 + box.height / 2))
        else:
            figure.subplots_adjust(bottom=0.14)
            add_legend(figure, color_by, source=key, loc="lower center", ncols=4)
    remind_about_duplicates(data)
    if save:
        figure.savefig(save, dpi=200, facecolor=SURFACE)
    if show and matplotlib.get_backend().lower() != "agg":
        plt.show()
    return figure


def TAS(data, color_by=None, title=None, ax=None, save=None, show=True, show_fields=True,
        rock_type="volcanic"):
    """Total alkali-silica diagram: Na2O + K2O against SiO2.

    Complete analyses are recalculated volatile-free to 100 % first, as the
    classification requires.  ``rock_type="volcanic"`` draws the fields of
    Le Bas et al. (1986) / Le Maitre; ``rock_type="plutonic"`` draws those of
    Middlemost (1994).
    """
    if rock_type not in ("volcanic", "plutonic"):
        raise ValueError("rock_type must be 'volcanic' or 'plutonic'.")
    majors = chem.major_oxides(data, ["SiO2", "Na2O", "K2O"], volatile_free=True)
    table = complete_rows(pd.DataFrame({"SiO2": majors["SiO2"],
                                        "alkalis": majors["Na2O"] + majors["K2O"]}),
                          "the TAS diagram")
    ax, created = new_axes(ax, figsize=(8.0, 6.0), legend=color_by is not None)
    if show_fields:
        from pyrolite.plot.templates import TAS as template

        template(ax=ax, which_model="LeMaitre" if rock_type == "volcanic" else None,
                 add_labels=True, color=MUTED, linewidth=0.8, fontsize=6,
                 which_labels="volcanic" if rock_type == "volcanic" else "intrusive")
        halo_texts(ax)
    scatter(ax, data, table, color_by)
    ax.set_xlim(35, 85)
    ax.set_ylim(0, 16)
    ax.set_xlabel(SIO2_LABEL, color=INK_SECONDARY)
    ax.set_ylabel("Na2O + K2O (wt%)", color=INK_SECONDARY)
    source = "Le Bas et al. 1986" if rock_type == "volcanic" else "Middlemost 1994"
    return finish(ax, data, len(table), title or f"Total alkali-silica ({source})", color_by,
                  created, save, show)


def Shand_Index(data, color_by=None, title=None, ax=None, save=None, show=True, show_fields=True):
    """Shand's index: A/NK against A/CNK (molar), separating metaluminous,
    peraluminous and peralkaline rocks (Shand 1943; Maniar & Piccoli 1989)."""
    def draw(ax):
        if not show_fields:
            return
        ax.axvline(1.0, **FIELD_LINE)
        ax.axhline(1.0, **FIELD_LINE)
        (x0, x1), (y0, y1) = ax.get_xlim(), ax.get_ylim()
        ax.text((x0 + 1) / 2, y1 - 0.08 * (y1 - y0), "Metaluminous", **FIELD_TEXT)
        ax.text((x1 + 1) / 2, y1 - 0.08 * (y1 - y0), "Peraluminous", **FIELD_TEXT)
        ax.text((x0 + 1) / 2, (y0 + 1) / 2, "Peralkaline", **FIELD_TEXT)

    return _xy(data, chem.a_cnk(data), chem.a_nk(data), "the Shand index diagram",
               title or "Shand index", color_by, ax, save, show,
               "A/CNK  =  molar Al2O3 / (CaO + Na2O + K2O)", "A/NK  =  molar Al2O3 / (Na2O + K2O)",
               draw, xlim=(0.5, 2.0), ylim=(0.5, 3.0))


def MALI(data, color_by=None, title=None, ax=None, save=None, show=True, show_fields=True):
    """Modified alkali-lime index, Na2O + K2O - CaO, against SiO2, with the
    alkalic to calcic fields of Frost et al. (2001)."""
    def draw(ax):
        if not show_fields:
            return
        silica = np.linspace(50, 80, 100)
        curves = [fields.mali_boundary(c, silica) for c in fields.MALI_BOUNDARIES.values()]
        for curve in curves:
            ax.plot(silica, curve, **FIELD_LINE)
        at = 77.0
        edges = [fields.mali_boundary(c, at) for c in fields.MALI_BOUNDARIES.values()]
        heights = [edges[0] + 1.2, (edges[0] + edges[1]) / 2, (edges[1] + edges[2]) / 2,
                   edges[2] - 1.2]
        for label, height in zip(fields.MALI_FIELD_LABELS, heights):
            ax.text(at, height, label, **FIELD_TEXT)

    silica = chem.oxide(data, "SiO2")
    return _xy(data, silica, chem.mali(data), "the MALI diagram",
               title or "Modified alkali-lime index (Frost et al. 2001)", color_by, ax, save, show,
               SIO2_LABEL, "Na2O + K2O - CaO (wt%)", draw, xlim=(45, 80), ylim=(-8, 12))


def ASI(data, color_by=None, title=None, ax=None, save=None, show=True, show_fields=True):
    """Aluminium saturation index against SiO2.  ASI is molecular
    Al / (Ca - 1.67 P + Na + K), which corrects for lime held in apatite
    (Frost et al. 2001).  Above 1 is peraluminous."""
    def draw(ax):
        if not show_fields:
            return
        ax.axhline(1.0, **FIELD_LINE)
        x0, x1 = ax.get_xlim()
        ax.text(x0 + 0.12 * (x1 - x0), 1.04, "Peraluminous", **FIELD_TEXT)
        ax.text(x0 + 0.12 * (x1 - x0), 0.96, "Metaluminous", **FIELD_TEXT)

    return _xy(data, chem.oxide(data, "SiO2"), chem.asi(data), "the ASI diagram",
               title or "Aluminium saturation index (Frost et al. 2001)", color_by, ax, save, show,
               SIO2_LABEL, "ASI  =  Al / (Ca - 1.67 P + Na + K), molecular", draw,
               xlim=(45, 80), ylim=(0.5, 1.6))


def Fe_Index(data, color_by=None, title=None, ax=None, save=None, show=True, show_fields=True):
    """Fe-index: Fe# = FeOt / (FeOt + MgO) against SiO2, separating ferroan
    from magnesian rocks (Frost et al. 2001; boundary of Frost & Frost 2008)."""
    def draw(ax):
        if not show_fields:
            return
        silica = np.array([45.0, 80.0])
        ax.plot(silica, fields.fe_index_boundary(silica), **FIELD_LINE)
        ax.text(52, fields.fe_index_boundary(52) + 0.05, "Ferroan", **FIELD_TEXT)
        ax.text(52, fields.fe_index_boundary(52) - 0.05, "Magnesian", **FIELD_TEXT)

    return _xy(data, chem.oxide(data, "SiO2"), chem.fe_index(data), "the Fe-index diagram",
               title or "Fe-index (Frost et al. 2001)", color_by, ax, save, show,
               SIO2_LABEL, "Fe#  =  FeOt / (FeOt + MgO)", draw, xlim=(45, 80), ylim=(0.2, 1.0))


def Granite_Tectonic(data, color_by=None, title=None, ax=None, save=None, show=True,
                     show_fields=True):
    """Tectonic setting of granites: Rb against Y + Nb (ppm, log scales), with
    the fields of Pearce et al. (1984): syn-collisional (syn-COLG), within-plate
    (WPG), volcanic-arc (VAG) and ocean-ridge (ORG) granites."""
    def draw(ax):
        if not show_fields:
            return
        for line in fields.PEARCE_RB_YNB_LINES:
            ax.plot(*zip(*line), **FIELD_LINE)
        for label, position in fields.PEARCE_RB_YNB_LABELS.items():
            ax.text(*position, label, **FIELD_TEXT)

    y_nb = chem.trace(data, "Y") + chem.trace(data, "Nb")
    return _xy(data, y_nb, chem.trace(data, "Rb"), "the granite tectonic diagram",
               title or "Granite tectonic setting (Pearce et al. 1984)", color_by, ax, save, show,
               "Y + Nb (ppm)", "Rb (ppm)", draw, log="both", xlim=(2, 2000), ylim=(1, 2000))


def Magnetic_Susceptibility(data, color_by=None, title=None, ax=None, save=None, show=True):
    """Magnetic susceptibility (SI units, log scale) against SiO2."""
    name = next((c.name for c in data.column_info
                 if c.name.startswith(("magnetic_susceptibility", "mag_sus", "magsus"))), None)
    if name is None:
        raise NothingToPlot("Nothing to plot: this data has no magnetic susceptibility column.")
    return _xy(data, chem.oxide(data, "SiO2"), data.df[name], "magnetic susceptibility",
               title or "Magnetic susceptibility", color_by, ax, save, show,
               SIO2_LABEL, "Magnetic susceptibility (SI)", log="y")


def Mafic_Oxides(data, color_by=None, title=None, ax=None, save=None, show=True):
    """Ferromagnesian oxides, FeOt + MgO + MnO + TiO2, against SiO2
    (as used by Laurent et al. 2014 to compare granitoid groups)."""
    majors = chem.major_oxides(data, ["FeOt", "MgO", "MnO", "TiO2"])
    return _xy(data, chem.oxide(data, "SiO2"), majors.sum(axis=1, skipna=False),
               "the ferromagnesian oxides diagram", title or "Ferromagnesian oxides",
               color_by, ax, save, show, SIO2_LABEL, "FeOt + MgO + MnO + TiO2 (wt%)")


# --- Sedimentary provenance ------------------------------------------------------------

def Sediment_Tectonic(data, color_by=None, title=None, ax=None, save=None, show=True):
    """Tectonic setting of sandstone-mudstone suites: K2O/Na2O (log scale)
    against SiO2 (Roser & Korsch 1986).  Passive-margin sediments plot at high
    SiO2 and K2O/Na2O, oceanic island-arc sediments at low values, and active
    continental margins between.

    The field boundaries are not drawn: published reproductions of them
    disagree with each other, so they could not be reliably digitised.
    """
    majors = chem.major_oxides(data, ["SiO2", "K2O", "Na2O"])
    return _xy(data, majors["SiO2"], majors["K2O"] / majors["Na2O"],
               "the sediment tectonic-setting diagram",
               title or "Tectonic setting of sediments (Roser & Korsch 1986)",
               color_by, ax, save, show, SIO2_LABEL, "K2O / Na2O", log="y")


def Sediment_Recycling(data, color_by=None, title=None, ax=None, save=None, show=True):
    """Provenance against recycling: Th/Sc against Zr/Sc, both on log scales
    (McLennan et al. 1993).  Th/Sc follows the composition of the source;
    Zr/Sc rises as zircon is concentrated by sorting and recycling."""
    scandium = chem.trace(data, "Sc")
    return _xy(data, chem.trace(data, "Zr") / scandium, chem.trace(data, "Th") / scandium,
               "the sediment recycling diagram",
               title or "Sediment provenance and recycling (McLennan et al. 1993)",
               color_by, ax, save, show, "Zr / Sc", "Th / Sc", log="both")


def Th_U_Weathering(data, color_by=None, title=None, ax=None, save=None, show=True,
                    show_fields=True):
    """Th/U against Th (ppm), both on log scales (McLennan et al. 1993).  The line is the
    upper-crust value, Th/U = 3.8.  Weathering and recycling remove U and
    raise Th/U above it; sediment from depleted mantle sources plots below."""
    def draw(ax):
        if not show_fields:
            return
        crust = fields.TH_U_UPPER_CRUST
        ax.axhline(crust, **FIELD_LINE)
        x0, x1 = ax.get_xlim()
        y0, y1 = ax.get_ylim()
        left = x0 * (x1 / x0) ** 0.03
        style = {**FIELD_TEXT, "ha": "left"}
        ax.text(left, crust * 1.18, "Upper crust (Th/U = 3.8)", **style)
        ax.text(left, max(crust * 2.5, (crust * y1) ** 0.5), "Weathering trend (rising Th/U)", **style)
        ax.text(left, min(crust / 2.5, (crust * y0) ** 0.5), "Depleted mantle sources", **style)

    thorium = chem.trace(data, "Th")
    return _xy(data, thorium, thorium / chem.trace(data, "U"), "the Th/U weathering diagram",
               title or "Th/U against Th (McLennan et al. 1993)", color_by, ax, save, show,
               "Th (ppm)", "Th / U", draw, log="both")


def Al_Ti_Provenance(data, color_by=None, title=None, ax=None, save=None, show=True,
                     show_fields=True):
    """Source-rock type from Al2O3/TiO2 (log scale) against Al2O3.  Al and Ti
    stay together through weathering, so the ratio reflects the source:
    mafic 3-8, intermediate 8-21, felsic 21-70 (Hayashi et al. 1997)."""
    def draw(ax):
        if not show_fields:
            return
        x0, x1 = ax.get_xlim()
        for value in sorted({edge for band in fields.AL_TI_BANDS.values() for edge in band}):
            ax.axhline(value, **FIELD_LINE)
        for name, (low, high) in fields.AL_TI_BANDS.items():
            ax.text(x1 - 0.02 * (x1 - x0), (low * high) ** 0.5, name, **{**FIELD_TEXT, "ha": "right"})

    majors = chem.major_oxides(data, ["Al2O3", "TiO2"])
    return _xy(data, majors["Al2O3"], majors["Al2O3"] / majors["TiO2"],
               "the Al2O3/TiO2 provenance diagram",
               title or "Source rock from Al2O3/TiO2 (Hayashi et al. 1997)",
               color_by, ax, save, show, "Al2O3 (wt%)", "Al2O3 / TiO2", draw, log="y")


def Ti_Zr_Provenance(data, color_by=None, title=None, ax=None, save=None, show=True,
                     show_fields=True):
    """Source-rock type from TiO2 against Zr.  The lines are TiO2/Zr = 200 and
    55 (TiO2 taken as ppm): mafic sources above 200, intermediate between,
    felsic below 55 (after Hayashi et al. 1997)."""
    def draw(ax):
        if not show_fields:
            return
        x0, x1 = ax.get_xlim()
        y0, y1 = ax.get_ylim()
        ratios = sorted(fields.TI_ZR_RATIOS.values(), reverse=True)
        slopes = [ratio / fields.TIO2_PERCENT_TO_PPM for ratio in ratios]
        for slope in slopes:
            ax.plot([0, x1], [0, slope * x1], **FIELD_LINE)
        ax.set_xlim(x0, x1)
        ax.set_ylim(y0, y1)
        # Labels sit along the top or right edge, between the lines.
        at = 0.9 * y1
        ax.text(min(at / slopes[0] * 0.5, 0.9 * x1), at, "Mafic", **FIELD_TEXT)
        ax.text(min((at / slopes[0] + at / slopes[1]) / 2, 0.9 * x1),
                min(at, 0.9 * x1 * (slopes[0] + slopes[1]) / 2), "Intermediate", **FIELD_TEXT)
        ax.text(0.9 * x1, 0.45 * x1 * slopes[1], "Felsic", **FIELD_TEXT)

    return _xy(data, chem.trace(data, "Zr"), chem.oxide(data, "TiO2"),
               "the TiO2-Zr provenance diagram",
               title or "Source rock from TiO2 and Zr (Hayashi et al. 1997)",
               color_by, ax, save, show, "Zr (ppm)", "TiO2 (wt%)", draw)


def K_Rb_Provenance(data, color_by=None, title=None, ax=None, save=None, show=True,
                    show_fields=True):
    """Rb against K2O, both on log scales (Floyd & Leveridge 1987).  The line is
    the "main trend" of igneous rocks, K/Rb = 230.  Sediment from acid and
    intermediate sources plots at the high-K, high-Rb end and sediment from
    basic sources at the low end.

    The original also draws a boundary between those two groups.  It could not
    be reliably located, so only the trend line and the two labels are drawn.
    """
    def draw(ax):
        if not show_fields:
            return
        x0, x1 = ax.get_xlim()
        slope = fields.K2O_PERCENT_TO_K_PPM / fields.K_RB_MAIN_TREND
        ax.plot([x0, x1], [slope * x0, slope * x1], **FIELD_LINE)
        ax.set_xlim(x0, x1)
        high, low = x0 * (x1 / x0) ** 0.8, x0 * (x1 / x0) ** 0.2
        ax.text(high, slope * high * 2.2, "K/Rb = 230", **FIELD_TEXT)
        ax.text(high, slope * high / 2.6, "Acid + intermediate\ncompositions", **FIELD_TEXT)
        ax.text(low, slope * low / 2.6, "Basic\ncompositions", **FIELD_TEXT)

    return _xy(data, chem.oxide(data, "K2O"), chem.trace(data, "Rb"), "the K2O-Rb diagram",
               title or "Source rock from K2O and Rb (Floyd & Leveridge 1987)",
               color_by, ax, save, show, "K2O (wt%)", "Rb (ppm)", draw, log="both")
