"""Quantities calculated from a GeochemData object: indices, ratios, norms.

Used by the plots and by ``data.CIA()`` and ``data.CIPW_norm()``.  Nothing here
reads raw columns.  It asks the data object for an analyte in the unit it
needs (``data["SiO2"].wt_percent()``), so unit and oxide conversion and the
iron rules all live in one place.
"""

from __future__ import annotations

import warnings

import numpy as np
import pandas as pd
from periodictable import formula

from .data.analyte import IRON_FORMS, UnknownAnalyteError
from .data.units import ELEMENT_SYMBOLS, parse_oxide

MAJOR_OXIDES = ["SiO2", "TiO2", "Al2O3", "FeOt", "MnO", "MgO", "CaO", "Na2O", "K2O", "P2O5"]
# The majors a whole-rock analysis must have before it is recalculated to 100 %.
CORE_OXIDES = ["SiO2", "Al2O3", "FeOt", "MgO", "CaO", "Na2O", "K2O"]

REE = ["La", "Ce", "Pr", "Nd", "Sm", "Eu", "Gd", "Tb", "Dy", "Ho", "Er", "Tm", "Yb", "Lu"]

_MOLAR_MASS = {name: formula("FeO" if name == "FeOt" else name).mass for name in MAJOR_OXIDES}
_FE2O3_AS_FEO = 2 * formula("FeO").mass / formula("Fe2O3").mass


def _empty(data) -> pd.Series:
    return pd.Series(np.nan, index=data.df.index, dtype=float)


def oxide(data, name: str) -> pd.Series:
    """An oxide in wt% (all-null if the data has nothing for it)."""
    try:
        return data[name].wt_percent().rename(name)
    except UnknownAnalyteError:
        return _empty(data).rename(name)


def trace(data, element: str) -> pd.Series:
    """A trace element in ppm (all-null if the data has nothing for it)."""
    try:
        return data[element].ppm().rename(element)
    except UnknownAnalyteError:
        return _empty(data).rename(element)


def major_oxides(data, names=MAJOR_OXIDES, volatile_free=False) -> pd.DataFrame:
    """Major oxides in wt%, one column each.

    With ``volatile_free`` each complete analysis (one that has all of
    CORE_OXIDES) is recalculated so its majors add up to 100 %.
    """
    table = pd.DataFrame({name: oxide(data, name) for name in MAJOR_OXIDES})
    if volatile_free:
        complete = table[CORE_OXIDES].notna().all(axis=1)
        total = table.sum(axis=1)
        table.loc[complete] = table.loc[complete].div(total[complete], axis=0) * 100.0
    return table[list(names)]


def moles(table: pd.DataFrame) -> pd.DataFrame:
    """Oxide wt% to moles of oxide (per 100 g)."""
    return table / pd.Series({name: _MOLAR_MASS[name] for name in table.columns})


def mg_number(data) -> pd.Series:
    """Mg# = 100 x molar Mg / (Mg + Fe), with all iron as FeO."""
    m = moles(major_oxides(data, ["MgO", "FeOt"]))
    return (100.0 * m["MgO"] / (m["MgO"] + m["FeOt"])).rename("Mg#")


def fe_index(data) -> pd.Series:
    """Fe# = FeOt / (FeOt + MgO), by weight."""
    t = major_oxides(data, ["FeOt", "MgO"])
    return (t["FeOt"] / (t["FeOt"] + t["MgO"])).rename("Fe#")


def a_cnk(data) -> pd.Series:
    """Molar Al2O3 / (CaO + Na2O + K2O)."""
    m = moles(major_oxides(data, ["Al2O3", "CaO", "Na2O", "K2O"]))
    return (m["Al2O3"] / (m["CaO"] + m["Na2O"] + m["K2O"])).rename("A/CNK")


def a_nk(data) -> pd.Series:
    """Molar Al2O3 / (Na2O + K2O)."""
    m = moles(major_oxides(data, ["Al2O3", "Na2O", "K2O"]))
    return (m["Al2O3"] / (m["Na2O"] + m["K2O"])).rename("A/NK")


def asi(data) -> pd.Series:
    """Aluminium saturation index of Frost et al. (2001): molecular
    Al / (Ca - 1.67 P + Na + K), i.e. A/CNK with the lime held in apatite
    removed.  In oxide moles that is Al2O3 / (CaO - 3.33 P2O5 + Na2O + K2O).
    Samples with no P2O5 are calculated without the correction."""
    m = moles(major_oxides(data, ["Al2O3", "CaO", "Na2O", "K2O", "P2O5"]))
    lime = m["CaO"] - (10.0 / 3.0) * m["P2O5"].fillna(0.0)
    return (m["Al2O3"] / (lime + m["Na2O"] + m["K2O"])).rename("ASI")


def cia(data) -> pd.Series:
    """Chemical Index of Alteration: 100 x molar Al2O3 / (Al2O3 + CaO + Na2O + K2O).
    CaO is the total CaO, with no correction for carbonate or apatite."""
    m = moles(major_oxides(data, ["Al2O3", "CaO", "Na2O", "K2O"]))
    return (100.0 * m["Al2O3"] / (m["Al2O3"] + m["CaO"] + m["Na2O"] + m["K2O"])).rename("CIA")


def mali(data) -> pd.Series:
    """Modified alkali-lime index: Na2O + K2O - CaO (wt%)."""
    t = major_oxides(data, ["Na2O", "K2O", "CaO"])
    return (t["Na2O"] + t["K2O"] - t["CaO"]).rename("MALI")


def fmsb(data) -> pd.Series:
    """FMSB of Laurent et al. (2014): (FeOt + MgO) wt% x (Sr + Ba) wt%."""
    t = major_oxides(data, ["FeOt", "MgO"])
    sr_ba = (trace(data, "Sr") + trace(data, "Ba")) / 10_000.0
    return ((t["FeOt"] + t["MgO"]) * sr_ba).rename("FMSB")


def jensen_cations(data) -> pd.DataFrame:
    """Cation proportions for the Jensen plot: Al, Fe(total) + Ti, Mg."""
    m = moles(major_oxides(data, ["Al2O3", "FeOt", "TiO2", "MgO"]))
    return pd.DataFrame({"Al": 2.0 * m["Al2O3"], "Fe+Ti": m["FeOt"] + m["TiO2"], "Mg": m["MgO"]})


_SPECIAL = {"mg#": mg_number, "fe#": fe_index, "asi": asi, "mali": mali,
            "a/cnk": a_cnk, "a/nk": a_nk, "fmsb": fmsb, "cia": cia}
_LABELS = {"mg#": "Mg#", "fe#": "Fe#", "asi": "ASI", "mali": "Na2O + K2O - CaO (wt%)",
           "a/cnk": "A/CNK", "a/nk": "A/NK", "fmsb": "FMSB", "cia": "CIA"}


def _term(data, text: str):
    """One analyte: oxides in wt%, elements in ppm."""
    try:
        analyte = data[text]
    except UnknownAnalyteError:
        # A real element or oxide this data simply does not have: no values.
        # Anything else is a typing mistake and is reported.
        if text in ELEMENT_SYMBOLS:
            return _empty(data), "ppm"
        if parse_oxide(text):
            return _empty(data), "wt%"
        raise
    name = analyte.name
    if name in IRON_FORMS and name != "Fe" or parse_oxide(name) or name == "LOI":
        return analyte.wt_percent(), "wt%"
    if name in ELEMENT_SYMBOLS:
        return analyte.ppm(), "ppm"
    return analyte.values(), analyte.unit


def evaluate(data, expression: str):
    """Work out a quantity from its name.

    Accepts an analyte ("MgO", "Zr"), a sum ("Na2O+K2O"), a ratio ("La/Yb")
    or one of Mg#, Fe#, ASI, MALI, A/CNK, A/NK, FMSB, CIA.  Oxides are in wt% and
    elements in ppm.  Returns ``(values, axis label)``.
    """
    text = expression.strip()
    key = text.lower().replace(" ", "")
    if key in _SPECIAL:
        return _SPECIAL[key](data), _LABELS[key]

    def total(part):
        values, units = None, set()
        for name in part.split("+"):
            series, unit = _term(data, name.strip())
            values = series if values is None else values + series
            units.add(unit)
        return values, units

    if "/" in text:
        top, bottom = text.split("/", 1)
        (numerator, _), (denominator, _) = total(top), total(bottom)
        return (numerator / denominator).rename(text), text
    values, units = total(text)
    label = " + ".join(part.strip() for part in text.split("+"))
    return values.rename(text), f"{label} ({'/'.join(sorted(units))})"


def iron_split(data, setting="plutonic") -> pd.DataFrame:
    """FeO and Fe2O3 (wt%) for every row, for norm calculations.

    Measured FeO and Fe2O3 are used where a sample has both.  Otherwise total
    iron is divided using the oxidation ratio of Le Maitre (1976), which
    depends on SiO2 and the alkalis and on whether the rock is plutonic or
    volcanic.
    """
    from pyrolite.mineral.normative import LeMaitreOxRatio

    majors = major_oxides(data, ["SiO2", "Na2O", "K2O", "FeOt"])
    ratio = LeMaitreOxRatio(majors[["SiO2", "Na2O", "K2O"]], mode=setting)   # FeO/(FeO+Fe2O3)
    oxides = majors["FeOt"] / (ratio + _FE2O3_AS_FEO * (1.0 - ratio))
    split = pd.DataFrame({"FeO": ratio * oxides, "Fe2O3": (1.0 - ratio) * oxides})
    measured = pd.DataFrame({"FeO": oxide(data, "FeO"), "Fe2O3": oxide(data, "Fe2O3")})
    both = measured.notna().all(axis=1)
    split.loc[both] = measured.loc[both]
    return split


def cipw(data, setting="plutonic") -> pd.DataFrame:
    """CIPW norm (wt%) for every sample with a complete major-element analysis.

    Columns are mineral names: quartz, orthoclase, albite, anorthite, ...
    Samples missing any of CORE_OXIDES are left out.
    """
    from pyrolite.mineral.normative import CIPW_norm

    majors = major_oxides(data)
    complete = majors[CORE_OXIDES].notna().all(axis=1)
    table = majors.loc[complete].drop(columns="FeOt").fillna(0.0)
    table[["FeO", "Fe2O3"]] = iron_split(data, setting).loc[complete]
    if table.empty:
        return pd.DataFrame(index=table.index, columns=["quartz", "orthoclase", "albite", "anorthite"],
                            dtype=float)
    with warnings.catch_warnings():
        warnings.simplefilter("ignore")
        norm = CIPW_norm(table)
    return norm


# pyrolite reports diopside, hypersthene and olivine both as totals and as
# their Mg and Fe end-members.  Summing a row would count those twice, so
# tables handed to users leave the end-members out.
NORM_END_MEMBERS = ["clinoenstatite", "clinoferrosilite", "enstatite", "ferrosilite",
                    "forsterite", "fayalite"]


_MODAL_WORDS = {
    "Q": ("quartz", "qtz"),
    "A": ("alkalifeldspar", "alkfeldspar", "kfeldspar", "kspar", "kfs", "afs", "orthoclase",
          "microcline"),
    "P": ("plagioclase", "plag"),
}


def modal_qap(data):
    """Modal quartz, alkali feldspar and plagioclase, if the file has columns
    for all three (matched on the column header).  Otherwise None."""
    found = {}
    for info in data.column_info:
        key = "".join(ch for ch in info.original.lower() if ch.isalnum())
        for corner, words in _MODAL_WORDS.items():
            if corner not in found and info.numeric and any(word in key for word in words):
                found[corner] = info.name
    if len(found) < 3:
        return None
    return pd.DataFrame({corner: data.df[found[corner]] for corner in "QAP"})


# Reference compositions for normalised REE diagrams: option -> (pyrolite name, citation).
CHONDRITES = {
    "MS95": ("Chondrite_MS95", "McDonough & Sun (1995)"),
    "SM89": ("Chondrite_SM89", "Sun & McDonough (1989)"),
    "PON": ("Chondrite_PON", "Palme & O'Neill (2014)"),
}
PRIMITIVE_MANTLES = {
    "SM89": ("PM_SM89", "Sun & McDonough (1989)"),
    "MS95": ("Pyrolite_MS95", "McDonough & Sun (1995)"),
    "PON": ("PM_PON", "Palme & O'Neill (2014)"),
}


def reference_values(choices: dict, reference: str, what: str):
    """REE values (ppm) of a reference composition and its citation."""
    from pyrolite.geochem.norm import get_reference_composition

    key = str(reference).upper()
    if key not in choices:
        raise ValueError(f"Unknown {what} '{reference}'. Choose from: {', '.join(choices)}.")
    name, citation = choices[key]
    composition = get_reference_composition(name)
    composition.set_units("ppm")
    return composition.comp[REE].astype(float), citation


def chondrite(reference="MS95") -> pd.Series:
    """Chondrite REE values in ppm."""
    return reference_values(CHONDRITES, reference, "chondrite")[0]


def primitive_mantle(reference="SM89") -> pd.Series:
    """Primitive-mantle REE values in ppm."""
    return reference_values(PRIMITIVE_MANTLES, reference, "primitive mantle")[0]
