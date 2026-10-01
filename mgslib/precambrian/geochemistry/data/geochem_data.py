"""The cleaned geochemistry table and the plain-English ways to query it."""

from __future__ import annotations

from pathlib import Path

import pandas as pd

from .analyte import IRON_FORMS, Analyte
from .cleaning import (ABOVE_LIMIT_FACTOR, DUPLICATE_GROUP, FLAG_COLUMNS, FLAG_DUPLICATE,
                       clean, qaqc_rows)
from .columns import column_for_role
from .loader import SOURCE_ROW, SOURCE_SHEET, read_tables
from .units import UNIT_LABELS

_BELOW_DETECTION_WORDING = {
    "half": "replaced with half the detection limit",
    "limit": "replaced with the detection limit",
    "sqrt2": "replaced with the detection limit divided by the square root of 2",
    "null": "set to null",
}


def load_geochem(path, sheets=None, below_detection="half", zeros_are_missing=True,
                 utm_zone=15) -> "GeochemData":
    """Load a geochemistry Excel or CSV file, combine its tables and clean it.

    Parameters
    ----------
    path : the Excel (.xlsx) or CSV (.csv) file.
    sheets : sheet name, or list of sheet names, to load. By default every
        sheet that has data is loaded and they are stacked into one table.
    below_detection : what to put in place of a value reported as "<limit":
        "half" (half the limit, the default), "limit", "sqrt2" (limit / 1.414)
        or "null".
    zeros_are_missing : treat a 0 in an analyte column as "no value".
    utm_zone : UTM zone of the coordinates. For zone 15 the coordinates are
        also checked against the outline of Minnesota.

    Example
    -------
        data = load_geochem("data.xlsx")
        data.summary()
    """
    raw = read_tables(path, sheets)
    state = clean(raw, below_detection=below_detection,
                  zeros_are_missing=zeros_are_missing, utm_zone=utm_zone)
    return GeochemData(state.df, state.qualifiers, state.limits, state.issues,
                       state.columns, counts=state.counts,
                       settings={"below_detection": below_detection, "file": Path(path).name})


class GeochemData:
    """A cleaned geochemistry table.

    Filters return a new, smaller ``GeochemData`` so they can be chained::

        data.filter_by_rock_type("Sedimentary").filter_above("SiO2", 50)

    ``data["Ti"]`` gives one analyte, which can be asked for in any unit::

        data["Ti"].ppm()

    ``data.df`` is the plain pandas table.
    """

    def __init__(self, df, qualifiers, limits, issues, columns, counts=None, settings=None):
        self.df = df
        self.qualifiers = qualifiers
        self.limits = limits
        self.issues = issues
        self.column_info = list(columns)
        self._counts = dict(counts or {})
        self._settings = dict(settings or {})

    # --- plumbing -------------------------------------------------------------------

    def _new(self, df, qualifiers=None, limits=None, issues=None, columns=None):
        return GeochemData(
            df,
            self.qualifiers if qualifiers is None else qualifiers,
            self.limits if limits is None else limits,
            self.issues if issues is None else issues,
            self.column_info if columns is None else columns,
            self._counts, self._settings,
        )

    def _keep(self, mask) -> "GeochemData":
        """A new table holding only the rows where ``mask`` is True."""
        mask = pd.Series(mask, index=self.df.index).fillna(False).astype(bool)
        rows = self.df.index[mask.to_numpy()]
        issues = self.issues[self.issues["row"].isna() | self.issues["row"].isin(rows)]
        return self._new(self.df.loc[rows], self.qualifiers.loc[rows],
                         self.limits.loc[rows], issues.reset_index(drop=True))

    def _role(self, role: str, what: str) -> str:
        name = column_for_role(self.column_info, role)
        if name is None:
            raise ValueError(f"This data has no {what} column.")
        return name

    @property
    def _analyte_columns(self):
        return [c for c in self.column_info if c.is_analyte]

    def __getitem__(self, name) -> Analyte:
        return Analyte(self, name)

    def __len__(self):
        return len(self.df)

    def __repr__(self):
        return f"{self._headline()}\n{self.df!r}"

    def _repr_html_(self):
        return f"<p>{self._headline()}</p>{self.df._repr_html_()}"

    def _headline(self):
        return (f"GeochemData: {len(self.df):,} rows, "
                f"{len(self._analyte_columns)} analyte columns")

    def head(self, n=5) -> pd.DataFrame:
        """The first ``n`` rows."""
        return self.df.head(n)

    # --- filters on analyte values ---------------------------------------------------

    def _values(self, analyte, unit):
        item = self[analyte]
        return item.values() if unit is None else item.in_unit(unit)

    def filter_by_detection_limit(self, analyte, limit=None, unit=None) -> "GeochemData":
        """Keep rows where ``analyte`` is accurate enough to use.

        A row is kept if the analyte was measured above detection, or if it
        was below detection but the lab's detection limit for that row was
        ``limit`` or smaller.  For example, with
        ``data.filter_by_detection_limit("Ag", 1)`` a value reported as
        "<0.5" or "<1" is kept, and one reported as "<5" is dropped.

        With no ``limit``, only rows measured above detection are kept.
        Rows with no value at all are always dropped.  The limit is in the
        unit the analyte was stored in unless ``unit`` says otherwise.
        """
        item = self[analyte]
        mask = item.is_measured() | item.is_above_upper_limit()
        if limit is not None:
            mask |= item.is_below_detection() & (item.detection_limit_per_row(unit) <= limit)
        return self._keep(mask)

    def filter_above(self, analyte, value, unit=None) -> "GeochemData":
        """Keep rows where ``analyte`` is greater than ``value``."""
        return self._keep(self._values(analyte, unit) > value)

    def filter_below(self, analyte, value, unit=None) -> "GeochemData":
        """Keep rows where ``analyte`` is less than ``value``."""
        return self._keep(self._values(analyte, unit) < value)

    def filter_between(self, analyte, low, high, unit=None) -> "GeochemData":
        """Keep rows where ``analyte`` is from ``low`` to ``high`` (inclusive)."""
        return self._keep(self._values(analyte, unit).between(low, high))

    def _require_analytes(self, analytes):
        if not analytes:
            raise ValueError("Name at least one analyte, e.g. data.filter_below_detection('Te').")

    def filter_below_detection(self, *analytes) -> "GeochemData":
        """Keep rows the lab reported as below detection ("<") for every analyte named."""
        self._require_analytes(analytes)
        mask = pd.Series(True, index=self.df.index)
        for analyte in analytes:
            mask &= self[analyte].is_below_detection()
        return self._keep(mask)

    def filter_above_upper_limit(self, *analytes) -> "GeochemData":
        """Keep rows the lab reported as over the upper limit (">") for every analyte named."""
        self._require_analytes(analytes)
        mask = pd.Series(True, index=self.df.index)
        for analyte in analytes:
            mask &= self[analyte].is_above_upper_limit()
        return self._keep(mask)

    def filter_measured(self, *analytes) -> "GeochemData":
        """Keep rows with a real measurement (not null, "<" or ">") for every analyte named."""
        self._require_analytes(analytes)
        mask = pd.Series(True, index=self.df.index)
        for analyte in analytes:
            mask &= self[analyte].is_measured()
        return self._keep(mask)

    # --- filters on descriptions ------------------------------------------------------

    def _filter_text(self, role, what, values, contains=False) -> "GeochemData":
        if not values:
            raise ValueError(f"Give at least one {what} to keep.")
        column = self.df[self._role(role, what)]
        lowered = column.str.lower()
        wanted = [str(v).strip().lower() for v in values]
        if contains:
            mask = pd.Series(False, index=column.index)
            for value in wanted:
                mask |= lowered.str.contains(value, regex=False).fillna(False).astype(bool)
        else:
            mask = lowered.isin(wanted)
            available = set(lowered.dropna())
            unknown = [str(v) for v, low in zip(values, wanted) if low not in available]
            if unknown:
                options = sorted(column.dropna().unique())
                shown = ", ".join(options[:25]) + (", ..." if len(options) > 25 else "")
                raise ValueError(f"No {what} called {unknown}. Available: {shown}")
        return self._keep(mask)

    def filter_by_rock_type(self, *rock_types) -> "GeochemData":
        """Keep rows of the given rock type(s), e.g. "Sedimentary"."""
        return self._filter_text("rock_type", "rock type", rock_types)

    def filter_by_rock_name(self, *words) -> "GeochemData":
        """Keep rows whose rock name contains any of the given words, e.g. "iron formation"."""
        return self._filter_text("rock_name", "rock name", words, contains=True)

    def filter_by_lithology(self, *lithologies) -> "GeochemData":
        """Keep rows of the given simple lithology."""
        return self._filter_text("lithology", "lithology", lithologies)

    def filter_by_reference(self, *references) -> "GeochemData":
        """Keep rows from the given reference(s) / data source(s)."""
        return self._filter_text("reference", "reference", references)

    def filter_by_unit_name(self, *unit_names) -> "GeochemData":
        """Keep rows from the given geologic unit(s), e.g. "Virginia Formation"."""
        return self._filter_text("unit_name", "unit name", unit_names)

    def filter_by_hole(self, *hole_ids) -> "GeochemData":
        """Keep rows from the given drill hole or outcrop ID(s)."""
        return self._filter_text("hole_id", "hole or outcrop ID", hole_ids)

    def filter_by_sheet(self, *sheets) -> "GeochemData":
        """Keep rows that came from the given sheet(s) of the file."""
        mask = self.df[SOURCE_SHEET].isin([str(s) for s in sheets])
        return self._keep(mask)

    def filter_by_depth(self, top=None, bottom=None) -> "GeochemData":
        """Keep rows whose depth is between ``top`` and ``bottom``."""
        depth = self.df[self._role("depth", "depth")]
        mask = depth.notna()
        if top is not None:
            mask &= depth >= top
        if bottom is not None:
            mask &= depth <= bottom
        return self._keep(mask)

    def filter_by_area(self, east_min, east_max, north_min, north_max) -> "GeochemData":
        """Keep rows inside a rectangle of UTM coordinates."""
        east = self.df[self._role("easting", "easting")]
        north = self.df[self._role("northing", "northing")]
        return self._keep(east.between(east_min, east_max) & north.between(north_min, north_max))

    def only_primary_samples(self) -> "GeochemData":
        """Drop QAQC rows (standards, blanks, lab duplicates)."""
        return self._keep(~qaqc_rows(self.df, self.column_info))

    def only_qaqc(self) -> "GeochemData":
        """Keep only QAQC rows (standards, blanks, lab duplicates)."""
        return self._keep(qaqc_rows(self.df, self.column_info))

    # --- detection limits --------------------------------------------------------

    def detection_limits(self, analyte=None) -> pd.DataFrame:
        """The detection limits found in the data.

        With no name: one line per analyte column, listing every lower and
        upper limit seen and how many values were below / above / measured.
        With a name (``data.detection_limits("Te")``): the limits for that
        analyte broken down by source sheet and lab.
        """
        if analyte is not None:
            return self._detection_limits_for(analyte)
        rows = []
        for info in self._analyte_columns:
            qualifier, limit = self.qualifiers[info.name], self.limits[info.name]
            below, above = qualifier == "<", qualifier == ">"
            rows.append({
                "analyte": info.analyte,
                "column": info.name,
                "unit": UNIT_LABELS.get(info.unit, ""),
                "lower_limits": _list_numbers(limit[below]),
                "upper_limits": _list_numbers(limit[above]),
                "n_below": int(below.sum()),
                "n_above": int(above.sum()),
                "n_measured": int((self.df[info.name].notna() & qualifier.isna()).sum()),
            })
        return pd.DataFrame(rows)

    def _detection_limits_for(self, analyte) -> pd.DataFrame:
        lab = column_for_role(self.column_info, "analytical_lab")
        frames = []
        for info in self[analyte]._sources:
            qualifier = self.qualifiers[info.name]
            flagged = qualifier.notna()
            frame = pd.DataFrame({
                "column": info.name,
                "unit": UNIT_LABELS.get(info.unit, ""),
                SOURCE_SHEET: self.df.loc[flagged, SOURCE_SHEET].astype(object),
                "analytical_lab": (self.df.loc[flagged, lab].astype(object).fillna("")
                                   if lab else ""),
                "reported_as": qualifier[flagged].map(
                    {"<": "below detection", ">": "above upper limit"}),
                "limit": self.limits.loc[flagged, info.name],
            })
            frames.append(frame)
        table = pd.concat(frames)
        keys = ["column", "unit", SOURCE_SHEET, "analytical_lab", "reported_as", "limit"]
        return (table.groupby(keys, dropna=False, sort=False).size()
                .rename("n_values").reset_index())

    def elements_below_detection(self) -> pd.DataFrame:
        """Which analyte columns have values below detection, and how many."""
        return self._qualifier_counts("<", "n_below", "lower_limits")

    def elements_above_upper_limit(self) -> pd.DataFrame:
        """Which analyte columns have values over the upper limit, and how many."""
        return self._qualifier_counts(">", "n_above", "upper_limits")

    def _qualifier_counts(self, qualifier, count, limits) -> pd.DataFrame:
        table = self.detection_limits()
        table = table[table[count] > 0].sort_values(count, ascending=False)
        return table[["analyte", "column", "unit", limits, count]].reset_index(drop=True)

    # --- flags and issues -----------------------------------------------------------

    def _flag(self, kind):
        if kind not in FLAG_COLUMNS:
            raise ValueError(f"Unknown flag '{kind}'. Choose from: {', '.join(FLAG_COLUMNS)}.")
        return FLAG_COLUMNS[kind]

    def _show_flagged(self, kind, first_columns) -> pd.DataFrame:
        flag, reason = self._flag(kind)
        first = [reason] + [c for c in first_columns if c and c in self.df.columns]
        first += [SOURCE_SHEET, SOURCE_ROW]
        rest = [c for c in self.df.columns if c not in first]
        return self.df.loc[self.df[flag], first + rest]

    def show_duplicates(self) -> pd.DataFrame:
        """The rows flagged as duplicates, with each group of copies together."""
        role = lambda r: column_for_role(self.column_info, r)
        table = self._show_flagged("duplicate", [DUPLICATE_GROUP, role("sample_id"), role("lab_id")])
        return table.sort_values(DUPLICATE_GROUP, kind="stable")

    def show_xyz_errors(self) -> pd.DataFrame:
        """The rows flagged for a location (easting, northing or depth) problem."""
        role = lambda r: column_for_role(self.column_info, r)
        return self._show_flagged("xyz", [role("sample_id"), role("hole_id"), role("easting"),
                                          role("northing"), role("depth")])

    def show_unit_conflicts(self) -> pd.DataFrame:
        """Unit problems: column-level notes (no unit in the header, the same
        analyte in two columns) and the individual rows that were flagged."""
        return self.show_issues("units")

    def show_issues(self, kind=None) -> pd.DataFrame:
        """The log of everything found during cleaning.

        ``kind`` narrows it to "formatting", "missing", "xyz", "units" or
        "duplicate".
        """
        if kind is None:
            return self.issues
        kinds = sorted(self.issues["kind"].unique())
        if kind not in kinds:
            raise ValueError(f"No issues of kind '{kind}'. Kinds in this data: {', '.join(kinds)}.")
        return self.issues[self.issues["kind"] == kind].reset_index(drop=True)

    def only_flagged(self, kind) -> "GeochemData":
        """Keep only rows flagged as "duplicate", "xyz" or "units"."""
        return self._keep(self.df[self._flag(kind)[0]])

    def remove_flagged(self, kind) -> "GeochemData":
        """Drop every row flagged as "duplicate", "xyz" or "units".

        For duplicates this drops all copies; use ``remove_duplicates()`` to
        keep one of each.
        """
        return self._keep(~self.df[self._flag(kind)[0]])

    def remove_duplicates(self, keep="raw") -> "GeochemData":
        """Keep one row from each group of duplicates.

        keep : "raw" keeps the copy with the most "<"/">" values, i.e. the
            lab's original numbers (the default); "most_complete" keeps the
            copy with the most analyte values; "first" / "last" keep by
            position in the file.

        Blank descriptive fields (rock type, reference, ...) on the kept row
        are filled in from the copies that are removed.  Analyte values are
        never mixed between copies.
        """
        options = ("raw", "most_complete", "first", "last")
        if keep not in options:
            raise ValueError(f"keep must be one of {options}, not '{keep}'.")
        df = self.df
        flagged = df[FLAG_DUPLICATE]
        if not flagged.any():
            return self._new(df)

        analytes = [c.name for c in self._analyte_columns]
        order = pd.DataFrame({"group": df.loc[flagged, DUPLICATE_GROUP],
                              "position": range(int(flagged.sum()))})
        if keep == "raw":
            order["score"] = -self.qualifiers.loc[flagged, analytes].notna().sum(axis=1)
        elif keep == "most_complete":
            order["score"] = -df.loc[flagged, analytes].notna().sum(axis=1)
        elif keep == "last":
            order["score"] = -order["position"]
        else:
            order["score"] = 0
        order = order.sort_values(["group", "score", "position"])
        keepers = order.drop_duplicates("group").index
        dropped = flagged & ~df.index.isin(keepers)

        result = df.copy()
        descriptive = [c.name for c in self.column_info if not c.is_analyte]
        descriptive += [c for c in df.columns if c.startswith(("depth_from", "depth_to"))]
        first_values = df.loc[flagged].groupby(DUPLICATE_GROUP)[descriptive].first()
        fill = first_values.loc[df.loc[keepers, DUPLICATE_GROUP]].set_axis(keepers)
        result.loc[keepers, descriptive] = df.loc[keepers, descriptive].fillna(fill)
        flag, reason = FLAG_COLUMNS["duplicate"]
        result.loc[keepers, flag] = False
        result.loc[keepers, reason] = pd.NA
        result.loc[keepers, DUPLICATE_GROUP] = pd.NA
        return self._new(result)._keep(~dropped)

    # --- information and export -------------------------------------------------------

    def list_analytes(self) -> list:
        """Every name that can go in ``data[...]``."""
        names = list(dict.fromkeys(c.analyte for c in self._analyte_columns))
        if any(c.element == "Fe" for c in self._analyte_columns):
            names += [n for n in IRON_FORMS if n not in names]
        return names

    def list_columns(self) -> pd.DataFrame:
        """Every column: its name here, its header in the file, and its unit."""
        return pd.DataFrame([{
            "column": c.name,
            "header_in_file": c.original,
            "kind": c.kind,
            "analyte": c.analyte or "",
            "unit": UNIT_LABELS.get(c.unit, ""),
            "unit_assumed": c.unit_assumed,
        } for c in self.column_info])

    def select(self, *analytes) -> "GeochemData":
        """Keep the descriptive columns plus only the analytes named."""
        self._require_analytes(analytes)
        wanted = {c.name for analyte in analytes for c in self[analyte]._sources}
        dropped = [c.name for c in self._analyte_columns if c.name not in wanted]
        columns = [c for c in self.column_info if c.name not in dropped]
        return self._new(self.df.drop(columns=dropped), self.qualifiers.drop(columns=dropped),
                         self.limits.drop(columns=dropped),
                         self.issues[~self.issues["column"].isin(dropped)].reset_index(drop=True),
                         columns)

    def summary(self) -> None:
        """Print a plain-English report of what is in the table and what was cleaned."""
        print(self._summary_text())

    def _summary_text(self) -> str:
        df, issues = self.df, self.issues
        lines = [self._headline()]
        if self._settings.get("file"):
            lines[0] += f" (from {self._settings['file']})"
        for sheet, count in df[SOURCE_SHEET].value_counts(sort=False).items():
            lines.append(f"  {sheet}: {count:,} rows")
        qaqc = int(qaqc_rows(df, self.column_info).sum())
        if qaqc:
            lines.append(f"  {qaqc:,} of these are QAQC rows (standards, blanks, lab duplicates)")

        lines.append("")
        lines.append("Cleaning")
        below = int((self.qualifiers == "<").sum().sum())
        above = int((self.qualifiers == ">").sum().sum())
        wording = _BELOW_DETECTION_WORDING.get(self._settings.get("below_detection"), "treated")
        lines.append(f"  {below:,} values below detection {wording}")
        lines.append(f"  {above:,} values above the upper limit set to "
                     f"{ABOVE_LIMIT_FACTOR:g} x the limit")
        for label, issue in (("zeros set to null", "zero"),
                             ("not-reported values (NR, -9000, ...) set to null",
                              ("not reported", "not-reported code")),
                             ("negative values set to null", "negative value"),
                             ("badly formatted numbers repaired", "badly formatted number"),
                             ("unreadable values set to null",
                              ("could not be read as a number", "could not be read as a depth"))):
            wanted = [issue] if isinstance(issue, str) else list(issue)
            lines.append(f"  {int(issues['issue'].isin(wanted).sum()):,} {label}")
        for label, count in self._counts.items():
            lines.append(f"  {count:,} {label} (whole file)")

        lines.append("")
        lines.append("Flagged for review (nothing was removed)")
        groups = df[DUPLICATE_GROUP].nunique()
        lines.append(f"  duplicates: {int(df[FLAG_DUPLICATE].sum()):,} rows in {groups:,} groups"
                     "  -> data.show_duplicates()")
        lines.append(f"  location (XYZ): {int(df[FLAG_COLUMNS['xyz'][0]].sum()):,} rows"
                     "  -> data.show_xyz_errors()")
        column_notes = int(((issues["kind"] == "units") & issues["row"].isna()).sum())
        lines.append(f"  units: {int(df[FLAG_COLUMNS['units'][0]].sum()):,} rows and "
                     f"{column_notes} column notes  -> data.show_unit_conflicts()")
        return "\n".join(lines)

    def to_csv(self, path) -> Path:
        """Save the cleaned table as a CSV file."""
        path = Path(path)
        self.df.to_csv(path, index=False)
        return path

    def to_excel(self, path) -> Path:
        """Save to an Excel file: the cleaned table, plus sheets recording which
        values were below/above detection, the limits, the issue log and the
        column list."""
        path = Path(path)
        sample_id = column_for_role(self.column_info, "sample_id")
        labels = self.df[[c for c in (sample_id, SOURCE_SHEET, SOURCE_ROW) if c]]
        with pd.ExcelWriter(path) as writer:
            self.df.to_excel(writer, sheet_name="Data", index=False)
            pd.concat([labels, self.qualifiers], axis=1).to_excel(
                writer, sheet_name="Below-Above detection", index=False)
            self.detection_limits().to_excel(writer, sheet_name="Detection limits", index=False)
            self.issues.to_excel(writer, sheet_name="Issues", index=False)
            self.list_columns().to_excel(writer, sheet_name="Columns", index=False)
        return path


def _list_numbers(values) -> str:
    """Distinct numbers as text, e.g. "0.05, 0.1"."""
    return ", ".join(f"{v:g}" for v in sorted(pd.Series(values).dropna().unique()))
