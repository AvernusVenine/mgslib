"""Ternary diagrams.  Each takes a GeochemData object and works out the rest."""

from __future__ import annotations

import warnings

import pandas as pd

from .. import chemistry as chem
from . import _fields as fields
from ._figure import (FIELD_LINE, FIELD_TEXT, INK_SECONDARY, MUTED, complete_rows, finish,
                      halo_texts, new_axes, scatter)


def _ternary(data, table, what, labels, title, color_by, ax, save, show, fields_drawer=None):
    """The common path.  ``table`` has three columns in the order top, left, right."""
    table = complete_rows(table, what)
    table = table[(table >= 0).all(axis=1) & (table.sum(axis=1) > 0)]
    table = complete_rows(table, what)
    ax, created = new_axes(ax, ternary=True, figsize=(7.0, 6.4), legend=color_by is not None)
    if fields_drawer:
        with warnings.catch_warnings():
            warnings.simplefilter("ignore")   # template chatter about zero-valued corners
            fields_drawer(ax)
    scatter(ax, data, table, color_by)
    top, left, right = labels
    ax.set_tlabel(top, color=INK_SECONDARY)
    ax.set_llabel(left, color=INK_SECONDARY)
    ax.set_rlabel(right, color=INK_SECONDARY)
    return finish(ax, data, len(table), title, color_by, created, save, show)


def _draw_lines(ax, lines):
    """Draw boundary lines given as lists of (top, left, right) points.
    A line may be given as ``(points, dashed)``."""
    for line in lines:
        points, dashed = line if isinstance(line, tuple) else (line, False)
        ax.plot(*zip(*points), **FIELD_LINE, linestyle="--" if dashed else "-")


def _draw_labels(ax, labels):
    for name, position in labels.items():
        ax.text(*position, name, **FIELD_TEXT)


def AFM_Ternary(data, color_by=None, title=None, ax=None, save=None, show=True, show_fields=True):
    """AFM diagram: A = Na2O + K2O, F = total iron as FeO, M = MgO (wt%), with
    the tholeiitic / calc-alkaline boundary of Irvine & Baragar (1971)."""
    majors = chem.major_oxides(data, ["Na2O", "K2O", "FeOt", "MgO"])
    table = pd.DataFrame({"F": majors["FeOt"], "A": majors["Na2O"] + majors["K2O"],
                          "M": majors["MgO"]})

    def draw(ax):
        if not show_fields:
            return
        a, f, m = zip(*fields.AFM_IRVINE_BARAGAR)
        ax.plot(f, a, m, **FIELD_LINE)
        ax.text(60, 15, 25, "Tholeiitic", **FIELD_TEXT)
        ax.text(30, 30, 40, "Calc-alkaline", **FIELD_TEXT)

    return _ternary(data, table, "the AFM diagram",
                    ("F  (FeOt)", "A  (Na2O + K2O)", "M  (MgO)"),
                    title or "AFM (Irvine & Baragar 1971)", color_by, ax, save, show, draw)


def Jensen_Ternary(data, color_by=None, title=None, ax=None, save=None, show=True,
                   show_fields=True):
    """Jensen cation plot: Al, Fe(total) + Ti and Mg as cation percent, with
    the komatiite, tholeiite and calc-alkaline fields of Jensen (1976)."""
    cations = chem.jensen_cations(data)
    table = cations[["Fe+Ti", "Al", "Mg"]]

    def draw(ax):
        if not show_fields:
            return
        from pyrolite.plot.templates import JensenPlot

        JensenPlot(ax=ax, add_labels=True, color=MUTED, linewidth=0.8, fontsize=7)
        halo_texts(ax)

    return _ternary(data, table, "the Jensen cation plot",
                    ("Fe(total) + Ti", "Al", "Mg"),
                    title or "Jensen cation plot (Jensen 1976)", color_by, ax, save, show, draw)


def Normative_Feldspar_Ternary(data, color_by=None, title=None, ax=None, save=None, show=True,
                               show_fields=True, rock_type="plutonic"):
    """Normative feldspar ternary: anorthite, albite and orthoclase from the
    CIPW norm, with the tonalite, trondhjemite, granodiorite, quartz monzonite
    and granite fields of O'Connor (1965).

    ``rock_type`` ("plutonic" or "volcanic") sets how total iron is divided
    into FeO and Fe2O3 for the norm when only total iron was analysed.
    """
    norm = chem.cipw(data, rock_type)
    table = norm.reindex(columns=["anorthite", "albite", "orthoclase"]).reindex(data.df.index)

    def draw(ax):
        if show_fields:
            _draw_lines(ax, fields.FELDSPAR_LINES)
            _draw_labels(ax, fields.FELDSPAR_LABELS)

    return _ternary(data, table, "the normative feldspar ternary (needs a full major-element analysis)",
                    ("An", "Ab", "Or"), title or "Normative feldspar (O'Connor 1965)",
                    color_by, ax, save, show, draw)


def QAP_Ternary(data, color_by=None, title=None, ax=None, save=None, show=True, show_fields=True,
                rock_type="plutonic"):
    """QAP diagram (Streckeisen 1974).

    Uses modal quartz, alkali feldspar and plagioclase if the file has columns
    for them.  Otherwise it uses the CIPW norm (Q = quartz, A = orthoclase,
    P = albite + anorthite) and says so in the title; a normative QAP is only
    an approximation of the modal one.
    """
    modal = chem.modal_qap(data)
    if modal is not None and modal.dropna().shape[0] > 0:
        table, kind = modal, "modal"
    else:
        norm = chem.cipw(data, rock_type).reindex(data.df.index)
        table = pd.DataFrame({"Q": norm.get("quartz"), "A": norm.get("orthoclase"),
                              "P": norm.get("albite") + norm.get("anorthite")})
        kind = "normative (CIPW)"

    def draw(ax):
        if not show_fields:
            return
        from pyrolite.plot.templates import QAP

        QAP(ax=ax, add_labels=True, which_labels="ID", color=MUTED, linewidth=0.8, fontsize=6)
        halo_texts(ax)

    return _ternary(data, table[["Q", "A", "P"]], f"the QAP diagram ({kind})",
                    ("Q", "A", "P"), title or f"QAP, {kind} (Streckeisen 1974)",
                    color_by, ax, save, show, draw)


def Laurent_Granitoid_Ternary(data, color_by=None, title=None, ax=None, save=None, show=True,
                              show_fields=True):
    """Late-Archean granitoid classification of Laurent et al. (2014):
    Na2O/K2O, 2 x A/CNK and 2 x FMSB, where FMSB = (FeOt + MgO) wt% x
    (Sr + Ba) wt%.

    Fields, read from the paper's figure: sanukitoids where 2 x FMSB is above
    30 %; TTG where it is below 30 % and Na2O/K2O is above 40 %; biotite and
    two-mica granites where both are below.  The dashed box in the middle is
    the hybrid granitoid field, which overlaps the other three.
    """
    majors = chem.major_oxides(data, ["Na2O", "K2O"])
    table = pd.DataFrame({"Na2O/K2O": majors["Na2O"] / majors["K2O"],
                          "2 A/CNK": 2.0 * chem.a_cnk(data),
                          "2 FMSB": 2.0 * chem.fmsb(data)})

    def draw(ax):
        if show_fields:
            _draw_lines(ax, fields.LAURENT_GRANITOID_LINES)
            _draw_labels(ax, fields.LAURENT_GRANITOID_LABELS)

    return _ternary(data, table, "the Laurent granitoid ternary",
                    ("Na2O / K2O", "2 x A/CNK", "2 x FMSB"),
                    title or "Late-Archean granitoids (Laurent et al. 2014)",
                    color_by, ax, save, show, draw)


def Laurent_Source_Ternary(data, color_by=None, title=None, ax=None, save=None, show=True,
                           show_fields=True):
    """Granitoid source diagram of Laurent et al. (2014):
    3 x CaO, Al2O3 / (FeOt + MgO) and 5 x (K2O / Na2O), used to judge whether
    a granitoid melt came from tonalite, metasediment, or low-K or high-K
    mafic rock."""
    majors = chem.major_oxides(data, ["Al2O3", "FeOt", "MgO", "CaO", "K2O", "Na2O"])
    table = pd.DataFrame({"3 CaO": 3.0 * majors["CaO"],
                          "Al/(Fe+Mg)": majors["Al2O3"] / (majors["FeOt"] + majors["MgO"]),
                          "5 K/Na": 5.0 * majors["K2O"] / majors["Na2O"]})

    def draw(ax):
        if show_fields:
            _draw_lines(ax, fields.LAURENT_SOURCE_LINES)
            _draw_labels(ax, fields.LAURENT_SOURCE_LABELS)

    return _ternary(data, table, "the Laurent source ternary",
                    ("3 x CaO", "Al2O3 / (FeOt + MgO)", "5 x (K2O / Na2O)"),
                    title or "Granitoid sources (Laurent et al. 2014)",
                    color_by, ax, save, show, draw)
