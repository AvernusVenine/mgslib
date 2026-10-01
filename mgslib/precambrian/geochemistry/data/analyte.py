"""The object returned by ``data["Ti"]``: one analyte, in any unit, on the fly.

Nothing here is stored.  Each call works from the columns as they came in the
file and converts them when asked.
"""

from __future__ import annotations

import difflib

import numpy as np
import pandas as pd

from .columns import ELEMENT, IRON_TOTAL, OXIDE, ColumnInfo
from .units import (ELEMENT_SYMBOLS, STANDARD_OXIDES, UNIT_LABELS, form_factor,
                    parse_oxide, unit_factor)

# What the user may type for a unit -> unit code.
UNIT_NAMES = {
    "ppm": "ppm", "ppb": "ppb", "pct": "pct", "%": "pct", "wt%": "pct",
    "wt %": "pct", "wt_percent": "pct", "percent": "pct",
}

# Names that ask for iron, and the chemical form each one is expressed in.
IRON_FORMS = {"Fe": "Fe", "FeO": "FeO", "Fe2O3": "Fe2O3", "FeOt": "FeO", "Fe2O3t": "Fe2O3"}
_IRON_NAMES = {name.lower(): name for name in IRON_FORMS}
_IRON_NAMES.update({"feo*": "FeOt", "feotot": "FeOt", "feototal": "FeOt",
                    "fe2o3*": "Fe2O3t", "fe2o3tot": "Fe2O3t", "fe2o3total": "Fe2O3t"})


class UnknownAnalyteError(KeyError):
    """Raised when a name does not match anything in the data."""

    def __str__(self):
        return str(self.args[0])


def _chemical_form(info: ColumnInfo) -> str:
    """The form a column's numbers are in: FeOt is FeO, Fe2O3t is Fe2O3."""
    if info.kind == IRON_TOTAL:
        return IRON_FORMS[info.analyte]
    return info.analyte


class _Parts:
    """Values plus, row by row, their qualifier, limit and source column."""

    def __init__(self, index):
        self.values = pd.Series(np.nan, index=index, dtype=float)
        self.qualifier = pd.Series(None, index=index, dtype=object)
        self.limit = pd.Series(np.nan, index=index, dtype=float)
        self.source = pd.Series(None, index=index, dtype=object)

    @property
    def filled(self):
        return self.source.notna()

    def put(self, rows, values, qualifier, limit, source):
        """Fill the still-empty rows among ``rows``."""
        rows = rows & ~self.filled
        self.values[rows] = values[rows]
        if qualifier is not None:
            self.qualifier[rows] = qualifier[rows]
        if limit is not None:
            self.limit[rows] = limit[rows]
        self.source[rows] = source[rows] if isinstance(source, pd.Series) else source

    def scaled(self, factor):
        result = _Parts(self.values.index)
        result.values = self.values * factor
        result.limit = self.limit * factor
        result.qualifier, result.source = self.qualifier, self.source
        return result


class Analyte:
    """One analyte of a :class:`GeochemData` table.

    ``data["Ti"].ppm()``, ``.ppb()`` and ``.wt_percent()`` give the analyte you
    named in that unit; ``.oxide_wt_percent()`` gives its oxide.  Each returns
    one value per row of the table, ready to plot.
    """

    def __init__(self, data, name: str):
        self._data = data
        self._kind, self.name, self._sources, self._form = _resolve(data.column_info, name)

    # --- how the numbers are put together ---------------------------------

    def _coalesce(self, sources, form=None, unit=None) -> _Parts:
        """Row by row, take the first source column that has a value,
        converted to ``form`` and ``unit``.  Columns already in the requested
        form are preferred."""
        data = self._data
        parts = _Parts(data.df.index)
        if form is not None:
            sources = sorted(sources, key=lambda c: _chemical_form(c) != form)
        for info in sources:
            factor = 1.0
            if unit is not None:
                if info.unit is None:
                    raise ValueError(f"The unit of '{info.name}' is not known, so it cannot be converted.")
                factor *= unit_factor(info.unit, unit)
            if form is not None:
                factor *= form_factor(_chemical_form(info), form)
            qualifier = data.qualifiers[info.name]
            rows = data.df[info.name].notna() | qualifier.notna()
            parts.put(rows, data.df[info.name] * factor, qualifier,
                      data.limits[info.name] * factor, info.name)
        return parts

    def _iron(self, form, unit) -> _Parts:
        """Iron, whichever iron columns each row happens to have."""
        def columns(test):
            return [c for c in self._sources if test(c)]

        def as_total(source):
            return source.map(lambda s: s if s is None else f"{s} (taken as total iron)")

        feo = self._coalesce(columns(lambda c: c.analyte == "FeO"), "FeO", "pct")
        fe2o3 = self._coalesce(columns(lambda c: c.analyte == "Fe2O3"), "Fe2O3", "pct")
        both = feo.values.notna() & fe2o3.values.notna()
        index = self._data.df.index

        if self.name in ("FeO", "Fe2O3"):
            # A single species is only known where both were measured.
            species = feo if self.name == "FeO" else fe2o3
            result = _Parts(index)
            result.put(both, species.values, species.qualifier, species.limit, species.source)
        else:
            # Total iron, worked out as FeO.
            ferric_as_feo = form_factor("Fe2O3", "FeO")
            total_column = self._coalesce(columns(lambda c: c.kind == IRON_TOTAL), "FeO", "pct")
            element = self._coalesce(columns(lambda c: c.kind == ELEMENT), "FeO", "pct")
            result = _Parts(index)
            result.put(both, feo.values + ferric_as_feo * fe2o3.values,
                       fe2o3.qualifier.where(fe2o3.qualifier.notna(), feo.qualifier),
                       None, "FeO + Fe2O3")
            result.put(total_column.filled, total_column.values, total_column.qualifier,
                       total_column.limit, total_column.source)
            result.put(fe2o3.filled, fe2o3.values * ferric_as_feo, fe2o3.qualifier,
                       fe2o3.limit * ferric_as_feo, as_total(fe2o3.source))
            result.put(element.filled & element.qualifier.isna(), element.values,
                       element.qualifier, element.limit, element.source)
            result.put(feo.filled, feo.values, feo.qualifier, feo.limit, as_total(feo.source))
            # Last resort: an iron value the lab only gave as "<" or ">".
            result.put(element.filled, element.values, element.qualifier,
                       element.limit, element.source)
            result = result.scaled(form_factor("FeO", form))
        return result.scaled(unit_factor("pct", unit))

    def _parts(self, form=None, unit=None) -> _Parts:
        if self._kind == "iron":
            return self._iron(form or self._form, unit or "pct")
        if self._kind == "simple":
            return self._coalesce(self._sources, None, unit or self._natural_unit)
        return self._coalesce(self._sources, form or self._form, unit or self._natural_unit)

    @property
    def _natural_unit(self):
        if self._kind == "iron":
            return "pct"
        if self._kind == "chem":
            for info in self._sources:
                if info.analyte == self._form:
                    return info.unit
        return self._sources[0].unit

    def _series(self, form=None, unit=None) -> pd.Series:
        values = self._parts(form, unit).values
        label = form or self._form or self.name
        if self._kind == "iron":
            label = {"Fe": "Fe2O3t"}.get(self.name, self.name) if form else self.name
        unit = unit or self._natural_unit
        return values.rename(f"{label}_{unit}" if unit else label)

    # --- what the user calls ---------------------------------------------------

    def values(self) -> pd.Series:
        """The values in the unit they were stored in (see ``.unit``)."""
        return self._series()

    def ppm(self) -> pd.Series:
        """Parts per million."""
        return self._series(unit="ppm")

    def ppb(self) -> pd.Series:
        """Parts per billion."""
        return self._series(unit="ppb")

    def wt_percent(self) -> pd.Series:
        """Weight percent of the analyte as named (``data["Ti"]`` gives Ti wt%,
        ``data["TiO2"]`` gives TiO2 wt%)."""
        return self._series(unit="pct")

    def oxide_wt_percent(self) -> pd.Series:
        """Weight percent as the oxide (``data["Ti"]`` gives TiO2 wt%)."""
        return self._series(form=self.oxide, unit="pct")

    def in_unit(self, unit: str) -> pd.Series:
        """The values in a unit given by name: "ppm", "ppb", "wt%" or "oxide wt%"."""
        key = str(unit).strip().lower()
        if key in ("oxide wt%", "oxide", "oxide_wt_percent", "oxide %"):
            return self.oxide_wt_percent()
        if key not in UNIT_NAMES:
            raise ValueError(f"Unknown unit '{unit}'. Use 'ppm', 'ppb', 'wt%' or 'oxide wt%'.")
        return self._series(unit=UNIT_NAMES[key])

    @property
    def unit(self) -> str:
        """The unit the values came in: "wt%", "ppm" or "ppb"."""
        return UNIT_LABELS.get(self._natural_unit, "unknown")

    @property
    def oxide(self) -> str:
        """The oxide this analyte is reported as, e.g. "TiO2" for Ti."""
        if self._kind == "iron":
            return {"Fe": "Fe2O3"}.get(self.name, self._form)
        if self._kind == "chem":
            if parse_oxide(self._form):
                return self._form
            in_data = list(dict.fromkeys(c.analyte for c in self._sources if c.kind == OXIDE))
            if len(in_data) == 1:
                return in_data[0]
            if self._form in STANDARD_OXIDES:
                return STANDARD_OXIDES[self._form]
        raise ValueError(f"{self.name} has no standard oxide, so it has no oxide wt%.")

    def source(self) -> pd.Series:
        """Which column each row's value was taken from."""
        return self._parts().source.rename(f"{self.name}_source")

    def is_below_detection(self) -> pd.Series:
        """True where the lab reported the value as below detection ("<")."""
        return (self._parts().qualifier == "<").rename(f"{self.name}_below_detection")

    def is_above_upper_limit(self) -> pd.Series:
        """True where the lab reported the value as over its upper limit (">")."""
        return (self._parts().qualifier == ">").rename(f"{self.name}_above_upper_limit")

    def is_measured(self) -> pd.Series:
        """True where there is a real measurement (not null, not "<" or ">")."""
        parts = self._parts()
        return (parts.values.notna() & parts.qualifier.isna()).rename(f"{self.name}_measured")

    def detection_limit_per_row(self, unit=None) -> pd.Series:
        """The limit the lab gave for each row that was reported as "<" or ">"
        (null where the value was measured).  In ``.unit`` unless ``unit`` is
        given as "ppm", "ppb" or "wt%"."""
        if unit is not None:
            key = str(unit).strip().lower()
            if key not in UNIT_NAMES:
                raise ValueError(f"Unknown unit '{unit}'. Use 'ppm', 'ppb' or 'wt%'.")
            unit = UNIT_NAMES[key]
        return self._parts(unit=unit).limit.rename(f"{self.name}_detection_limit")

    def _limits(self, qualifier) -> list:
        parts = self._parts()
        found = parts.limit[parts.qualifier == qualifier].dropna().unique()
        return sorted(float(f"{v:.6g}") for v in found)

    @property
    def detection_limit(self) -> list:
        """Every lower detection limit seen for this analyte, in ``.unit``."""
        return self._limits("<")

    @property
    def upper_limit(self) -> list:
        """Every upper reporting limit seen for this analyte, in ``.unit``."""
        return self._limits(">")

    def detection_limits(self) -> pd.DataFrame:
        """The limits for this analyte, by source sheet and lab."""
        return self._data.detection_limits(self.name)

    def __repr__(self):
        parts = self._parts()
        sources = ", ".join(dict.fromkeys(parts.source.dropna()))
        return (f"{self.name}: {int(parts.values.notna().sum()):,} values in {self.unit}"
                f" (from {sources or 'no columns'}). "
                "Use .ppm(), .ppb(), .wt_percent() or .oxide_wt_percent().")


def _resolve(columns, name):
    """Work out what a name refers to.

    Returns ``(kind, canonical name, source columns, form)`` where kind is
    "iron", "chem" (an element or oxide, convertible) or "simple" (anything
    else) and form is the element or oxide the values are expressed as.
    """
    if not isinstance(name, str):
        raise UnknownAnalyteError(f"Use a name in quotes, e.g. data['SiO2'], not {name!r}.")
    text = name.strip()
    analytes = [c for c in columns if c.is_analyte]

    iron = _IRON_NAMES.get(text.lower())
    if iron:
        sources = [c for c in analytes if c.element == "Fe" and c.unit]
        if sources:
            return "iron", iron, sources, IRON_FORMS[iron]

    def kind_of(info):
        return "chem" if info.kind in (ELEMENT, OXIDE) and info.unit else "simple"

    def single(info):
        chem = kind_of(info) == "chem"
        return ("chem" if chem else "simple"), info.name, [info], (info.analyte if chem else None)

    known = list(dict.fromkeys(c.analyte for c in analytes))
    matches = [a for a in known if a == text] or [a for a in known if a.lower() == text.lower()]
    if len(matches) > 1:
        raise UnknownAnalyteError(
            f"'{name}' could mean any of {matches}. Type it with the exact capitals.")

    if not matches:
        # A full column name ("SiO2_pct") or the header as written in the file.
        for info in analytes:
            if text.lower() in (info.name.lower(), info.original.strip().lower()):
                return single(info)

    if matches:
        analyte = matches[0]
    else:
        # Not a column, but maybe an element or oxide we can calculate.
        analyte = next((s for s in ELEMENT_SYMBOLS if s.lower() == text.lower()), None)
        if analyte is None and parse_oxide(text):
            analyte = text

    if analyte is not None:
        own = [c for c in analytes if c.analyte == analyte]
        if own and kind_of(own[0]) == "simple":
            return "simple", analyte, own, None
        if analyte in ELEMENT_SYMBOLS:
            element = analyte
            oxides = [c for c in analytes if c.kind == OXIDE and c.element == element and c.unit]
            if len({c.analyte for c in oxides}) > 1:
                oxides = []  # e.g. two kinds of water: not interchangeable
            sources = own + oxides
        else:
            element = parse_oxide(analyte)[0]
            sources = own + [c for c in analytes
                             if c.kind == ELEMENT and c.element == element and c.unit]
        if sources:
            return "chem", analyte, sources, analyte

    names = list(dict.fromkeys(known + list(IRON_FORMS)))
    suggestions = difflib.get_close_matches(text, names, n=5, cutoff=0.5)
    hint = f" Did you mean: {', '.join(suggestions)}?" if suggestions else ""
    raise UnknownAnalyteError(
        f"'{name}' is not in this data.{hint} Use data.list_analytes() to see what is available.")
