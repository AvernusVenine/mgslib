"""The cleaning steps, applied in order by :func:`clean`.

Each step takes the :class:`CleaningState`, changes it, and records what it
did in the issue log (one line per problem) or in ``counts`` (for routine
tidying that would swamp the log, such as trimming spaces).
"""

from __future__ import annotations

import math
import re
from dataclasses import dataclass, field

import numpy as np
import pandas as pd

from .columns import ELEMENT, OXIDE, ColumnInfo, build_columns, column_for_role
from .loader import SOURCE_ROW, SOURCE_SHEET
from .units import form_factor, unit_factor

# --- settings -------------------------------------------------------------

BELOW_DETECTION_OPTIONS = ("half", "limit", "null", "sqrt2")

# Easting/northing limits of the UTM system itself.
UTM_EASTING_RANGE = (100_000, 900_000)
UTM_NORTHING_RANGE = (0, 10_000_000)
# Generous box around Minnesota in UTM zone 15N (metres).
MINNESOTA_UTM15N_BOUNDS = {"easting": (150_000, 780_000), "northing": (4_800_000, 5_480_000)}
# One hole should have one collar; allow this much rounding difference (metres).
HOLE_COORDINATE_TOLERANCE = 5.0

# Text that means "no value".
NOT_REPORTED_WORDS = {
    "nr", "n.r.", "na", "n/a", "n.a.", "nan", "null", "none", "-", "--", "---",
    "ns", "is", "lnr", "not reported", "not analyzed", "not analysed",
}
# Text that means "below detection" without saying what the limit was.
BELOW_DETECTION_WORDS = {"bdl", "b.d.l.", "nd", "n.d.", "<dl", "<lod", "bd"}
# Negative numbers at or below this are "not reported" codes such as -9000.
SENTINEL_CUTOFF = -99
# A value reported as over the upper limit (">25") becomes the limit times this.
ABOVE_LIMIT_FACTOR = 1.2

# An element and its oxide that differ by more than this many times point to a
# unit mix-up (ppm entered as %, and so on).  Smaller differences are normal:
# different digestions, rounding, values near the detection limit.
ELEMENT_OXIDE_MAX_RATIO = 5.0
# ...and are only compared where the larger of the two is at least this (wt% oxide).
ELEMENT_OXIDE_MIN_PCT = 0.1
# Major oxides (plus LOI) should not add up to more than this (wt%).
MAJOR_TOTAL_LIMIT = 105.0
MAJOR_OXIDES = ("SiO2", "TiO2", "Al2O3", "Fe2O3", "FeO", "MnO", "MgO", "CaO",
                "Na2O", "K2O", "P2O5", "LOI")

FLAG_DUPLICATE = "flag_duplicate"
FLAG_XYZ = "flag_xyz"
FLAG_UNITS = "flag_units"
FLAG_COLUMNS = {
    "duplicate": (FLAG_DUPLICATE, "duplicate_reason"),
    "xyz": (FLAG_XYZ, "xyz_issue"),
    "units": (FLAG_UNITS, "unit_issue"),
}
DUPLICATE_GROUP = "duplicate_group"

ISSUE_COLUMNS = ["row", SOURCE_SHEET, SOURCE_ROW, "column", "kind", "issue",
                 "original_value", "action"]

_CATEGORY_ROLES = ("rock_type", "rock_name", "lithology", "sample_type")
_QAQC_WORDS = ("qaqc", "qa/qc", "standard", "duplicate", "blank", "crm")
_JUNK_CHARACTERS = set("»«﻿​‌‍")

_NUMBER = r"-?\d+(?:\.\d+)?(?:[eE][-+]?\d+)?"
_QUALIFIED = re.compile(rf"^([<>])=?({_NUMBER})$")
_RANGE = re.compile(rf"^(\d+(?:\.\d+)?)\s*(?:-|–|—|to)\s*(\d+(?:\.\d+)?)$")
_THOUSANDS = re.compile(r"^-?\d{1,3}(,\d{3})+(\.\d+)?$")
_DECIMAL_COMMA = re.compile(r"^-?\d+,\d+$")


@dataclass
class CleaningState:
    df: pd.DataFrame
    columns: list[ColumnInfo]
    qualifiers: pd.DataFrame = None
    limits: pd.DataFrame = None
    issue_rows: list = field(default_factory=list)
    counts: dict = field(default_factory=dict)

    def log(self, row, column, kind, issue, original=None, action=""):
        self.issue_rows.append((row, column, kind, issue, original, action))

    def count(self, what, number):
        if number:
            self.counts[what] = self.counts.get(what, 0) + int(number)

    def role(self, role):
        return column_for_role(self.columns, role)

    @property
    def analyte_columns(self):
        return [c for c in self.columns if c.is_analyte]

    @property
    def issues(self) -> pd.DataFrame:
        frame = pd.DataFrame(
            self.issue_rows,
            columns=["row", "column", "kind", "issue", "original_value", "action"],
        )
        on_rows = frame["row"].notna()
        rows = frame.loc[on_rows, "row"].astype(int)
        frame[SOURCE_SHEET] = pd.Series(self.df[SOURCE_SHEET].reindex(rows).to_numpy(), index=rows.index)
        frame[SOURCE_ROW] = pd.Series(self.df[SOURCE_ROW].reindex(rows).to_numpy(), index=rows.index)
        frame["row"] = frame["row"].astype("Int64")
        frame[SOURCE_ROW] = frame[SOURCE_ROW].astype("Int64")
        frame["original_value"] = frame["original_value"].map(
            lambda v: None if v is None else str(v))
        return frame[ISSUE_COLUMNS]


# --- step 1: standard column names ------------------------------------------

def start(raw: pd.DataFrame) -> CleaningState:
    """Work out what each column is and give it its standard name."""
    headers = [c for c in raw.columns if c not in (SOURCE_SHEET, SOURCE_ROW)]
    columns = build_columns(headers, raw)
    df = raw.rename(columns={c.original: c.name for c in columns}).reset_index(drop=True)
    return CleaningState(df=df, columns=columns)


# --- step 2: text and formatting ---------------------------------------------

def _clean_text(value):
    if not isinstance(value, str):
        return value
    text = value.replace("\xa0", " ")
    text = "".join(
        ch for ch in text
        if ch not in _JUNK_CHARACTERS and (ch.isprintable() or ch.isspace())
    )
    return " ".join(text.split()) or None


def tidy_text(state: CleaningState) -> CleaningState:
    """Trim spaces, remove line breaks and stray characters, blank -> null,
    and give category columns consistent capitals."""
    df = state.df
    for info in state.columns:
        before = df[info.name]
        after = before.map(_clean_text)
        changed = sum(a != b for a, b in zip(after, before) if isinstance(b, str))
        state.count("text cells tidied (spaces, line breaks, stray characters)", changed)
        df[info.name] = after

    for role in _CATEGORY_ROLES:
        name = state.role(role)
        if name is None:
            continue
        before = df[name]
        after = before.map(lambda v: v[:1].upper() + v[1:] if isinstance(v, str) else v)
        state.count("category values given consistent capitals",
                    sum(a != b for a, b in zip(after, before) if isinstance(b, str)))
        df[name] = after
    return state


# --- step 3: numbers, detection limits, zeros -----------------------------

def _read_number(text: str):
    try:
        number = float(text)
    except ValueError:
        return None
    return number if math.isfinite(number) else None


def parse_value(value):
    """Read one cell of a numeric column.

    Returns ``(number, qualifier, status)`` where qualifier is "<", ">" or None
    and status is one of "ok", "empty", "text_number", "repaired",
    "not_reported", "below_unknown" or "unreadable".  For a qualified value
    the number is the limit itself.
    """
    if value is None or (isinstance(value, float) and math.isnan(value)):
        return np.nan, None, "empty"
    if isinstance(value, bool):
        return np.nan, None, "unreadable"
    if isinstance(value, (int, float, np.integer, np.floating)):
        return float(value), None, "ok"
    text = str(value).strip()
    lowered = text.lower()
    if lowered in NOT_REPORTED_WORDS:
        return np.nan, None, "not_reported"
    if lowered in BELOW_DETECTION_WORDS:
        return np.nan, "<", "below_unknown"
    number = _read_number(text)
    if number is not None:
        return number, None, "text_number"

    compact = text.replace(" ", "")
    if _THOUSANDS.match(compact):
        compact = compact.replace(",", "")
    elif _DECIMAL_COMMA.match(compact):
        compact = compact.replace(",", ".")
    qualified = _QUALIFIED.match(compact)
    if qualified:
        return float(qualified.group(2)), qualified.group(1), "ok"
    number = _read_number(compact)
    if number is not None:
        return number, None, "repaired"
    return np.nan, None, "unreadable"


def _below_detection_value(limits: np.ndarray, option: str) -> np.ndarray:
    if option == "half":
        return limits / 2.0
    if option == "limit":
        return limits
    if option == "sqrt2":
        return limits / math.sqrt(2.0)
    return np.full_like(limits, np.nan)


def parse_numbers(state: CleaningState, below_detection="half",
                  zeros_are_missing=True) -> CleaningState:
    """Turn every numeric column into real numbers.

    Handles numbers stored as text, broken formatting ("1857 .00"), values
    below/above detection ("<0.05", ">25"), "not reported" codes (NR, -9000),
    negatives and zeros.
    """
    if below_detection not in BELOW_DETECTION_OPTIONS:
        raise ValueError(
            f"below_detection must be one of {BELOW_DETECTION_OPTIONS}, not '{below_detection}'."
        )
    df = state.df
    index = df.index
    qualifier_columns, limit_columns = {}, {}
    depth = state.role("depth")

    for info in state.columns:
        if not info.numeric or info.name == depth:
            continue
        original = df[info.name].tolist()
        parsed = [parse_value(v) for v in original]
        values = np.array([p[0] for p in parsed], dtype=float)
        qualifiers = np.array([p[1] for p in parsed], dtype=object)
        statuses = np.array([p[2] for p in parsed], dtype=object)

        state.count("numbers stored as text converted", (statuses == "text_number").sum())
        for i in np.flatnonzero(statuses == "repaired"):
            state.log(index[i], info.name, "formatting", "badly formatted number",
                      original[i], f"read as {values[i]:g}")
        for i in np.flatnonzero(statuses == "unreadable"):
            state.log(index[i], info.name, "formatting", "could not be read as a number",
                      original[i], "set to null")
        for i in np.flatnonzero(statuses == "not_reported"):
            state.log(index[i], info.name, "missing", "not reported", original[i], "set to null")

        if not info.is_analyte:
            # Coordinates and the like: a "<" or ">" makes no sense here.
            for i in np.flatnonzero(pd.notna(qualifiers)):
                state.log(index[i], info.name, "formatting", "could not be read as a number",
                          original[i], "set to null")
                values[i] = np.nan
            df[info.name] = values
            continue

        below = qualifiers == "<"
        above = qualifiers == ">"
        limits = np.where(below | above, values, np.nan)
        values[below] = _below_detection_value(limits[below], below_detection)
        values[above] = limits[above] * ABOVE_LIMIT_FACTOR

        keeps_negatives = info.analyte == "LOI"   # LOI can truly be negative
        sentinel = (values <= SENTINEL_CUTOFF) & ~above & ~below
        negative = (values < 0) & ~sentinel & ~above & ~below
        if keeps_negatives:
            negative[:] = False
        for i in np.flatnonzero(sentinel):
            state.log(index[i], info.name, "missing", "not-reported code", original[i], "set to null")
        for i in np.flatnonzero(negative):
            state.log(index[i], info.name, "missing", "negative value", original[i], "set to null")
        values[sentinel | negative] = np.nan

        if zeros_are_missing:
            zero = values == 0
            for i in np.flatnonzero(zero):
                state.log(index[i], info.name, "missing", "zero", original[i], "set to null")
            values[zero] = np.nan

        df[info.name] = values
        qualifier_columns[info.name] = qualifiers
        limit_columns[info.name] = limits

    state.qualifiers = pd.DataFrame(qualifier_columns, index=index, dtype=object)
    state.qualifiers = state.qualifiers.where(state.qualifiers.notna(), None)
    state.limits = pd.DataFrame(limit_columns, index=index, dtype=float)
    return state


# --- step 4: depth -----------------------------------------------------------

def parse_depth(state: CleaningState) -> CleaningState:
    """Depth to numbers.  A range such as "135-140" becomes its midpoint, with
    the two ends kept in separate from/to columns."""
    name = state.role("depth")
    if name is None:
        return state
    df = state.df = state.df.copy()   # one solid block again after many column edits
    original = df[name].tolist()
    depth = np.full(len(df), np.nan)
    top = np.full(len(df), np.nan)
    bottom = np.full(len(df), np.nan)
    ranges = 0
    for i, value in enumerate(original):
        number, qualifier, status = parse_value(value)
        if status in ("ok", "text_number") and qualifier is None:
            depth[i] = number
            continue
        if status == "empty":
            continue
        match = _RANGE.match(str(value).strip())
        if match:
            top[i], bottom[i] = float(match.group(1)), float(match.group(2))
            depth[i] = (top[i] + bottom[i]) / 2.0
            ranges += 1
        elif status == "repaired":
            depth[i] = number
            state.log(df.index[i], name, "formatting", "badly formatted number",
                      value, f"read as {number:g}")
        else:
            state.log(df.index[i], name, "formatting", "could not be read as a depth",
                      value, "set to null")
    state.count("depth ranges converted to their midpoint", ranges)

    df[name] = depth
    position = df.columns.get_loc(name)
    df.insert(position + 1, name.replace("depth", "depth_from", 1), top)
    df.insert(position + 2, name.replace("depth", "depth_to", 1), bottom)
    return state


# --- step 5: column types ------------------------------------------------------

def finish_types(state: CleaningState) -> CleaningState:
    """Text columns become proper text columns with true nulls."""
    df = state.df
    for info in state.columns:
        if info.numeric:
            df[info.name] = df[info.name].astype(float)
        else:
            df[info.name] = df[info.name].map(
                lambda v: None if v is None or v != v else str(v)).astype("string")
    df[SOURCE_SHEET] = df[SOURCE_SHEET].astype("string")
    df[SOURCE_ROW] = df[SOURCE_ROW].astype(int)
    state.df = df.copy()   # one solid block again after many column edits
    return state


# --- helpers for the checks ----------------------------------------------------

def qaqc_rows(df: pd.DataFrame, columns) -> pd.Series:
    """True for standards, blanks and lab duplicates."""
    name = column_for_role(columns, "analytical_type")
    if name is None:
        return pd.Series(False, index=df.index)
    text = df[name].str.lower().fillna("")
    result = pd.Series(False, index=df.index)
    for word in _QAQC_WORDS:
        result |= text.str.contains(word, regex=False)
    return result


def _add_flag(state: CleaningState, kind: str, reasons: dict) -> None:
    """Write a true/false flag column and a column explaining it."""
    flag, text = FLAG_COLUMNS[kind]
    df = state.df
    df[flag] = df.index.isin(list(reasons))
    df[text] = pd.Series({row: "; ".join(dict.fromkeys(r)) for row, r in reasons.items()},
                         dtype="string").reindex(df.index)
    for row, row_reasons in reasons.items():
        for reason in dict.fromkeys(row_reasons):
            state.log(row, None, kind, reason, None, "flagged")


def _note(reasons: dict, mask: pd.Series, reason: str) -> None:
    for row in mask.index[mask.fillna(False).to_numpy(dtype=bool)]:
        reasons.setdefault(row, []).append(reason)


# --- step 6: location checks ---------------------------------------------------

def check_xyz(state: CleaningState, utm_zone=15) -> CleaningState:
    """Flag coordinate and depth problems."""
    df = state.df
    reasons: dict = {}
    east, north = state.role("easting"), state.role("northing")
    depth, hole = state.role("depth"), state.role("hole_id")
    sample_type = state.role("sample_type")
    not_qaqc = ~qaqc_rows(df, state.columns)

    if east and north:
        e, n = df[east], df[north]
        _note(reasons, (e.isna() | n.isna()) & not_qaqc, "missing easting or northing")
        swapped = (e > 1_000_000) & (n < 1_000_000)
        _note(reasons, swapped, "easting and northing look swapped")
        outside_utm = ~swapped & (
            ~e.between(*UTM_EASTING_RANGE) & e.notna()
            | ~n.between(*UTM_NORTHING_RANGE) & n.notna()
        )
        _note(reasons, outside_utm, "coordinates are not valid UTM values")
        if utm_zone == 15:
            box = MINNESOTA_UTM15N_BOUNDS
            outside = ~swapped & ~outside_utm & (
                ~e.between(*box["easting"]) & e.notna()
                | ~n.between(*box["northing"]) & n.notna()
            )
            _note(reasons, outside, "coordinates fall outside Minnesota (UTM 15N)")
        if hole:
            located = df[df[hole].notna() & e.notna() & n.notna()]
            spread = located.groupby(hole)[[east, north]].agg(lambda s: s.max() - s.min())
            moved = spread.index[(spread > HOLE_COORDINATE_TOLERANCE).any(axis=1)]
            _note(reasons, df[hole].isin(moved),
                  "same hole/outcrop ID has more than one location")

    if depth:
        d = df[depth]
        top = df[depth.replace("depth", "depth_from", 1)]
        bottom = df[depth.replace("depth", "depth_to", 1)]
        _note(reasons, d < 0, "negative depth")
        _note(reasons, top > bottom, "depth range is upside down (from > to)")
        if sample_type:
            kind = df[sample_type].str.lower().fillna("")
            _note(reasons, kind.str.contains("outcrop") & d.notna(), "outcrop sample has a depth")
            _note(reasons, kind.str.contains("drill") & d.isna(), "drill core sample has no depth")

    _add_flag(state, "xyz", reasons)
    return state


# --- step 7: unit checks -----------------------------------------------------------

def check_units(state: CleaningState) -> CleaningState:
    """Flag values and columns whose units look wrong or ambiguous.
    Nothing is converted."""
    df = state.df
    reasons: dict = {}
    analytes = [c for c in state.analyte_columns if c.unit]

    # Column-level notes.
    for info in analytes:
        if info.unit_assumed:
            state.log(None, info.name, "units", "no unit in the column header",
                      info.original, "assumed wt%")
    by_analyte: dict = {}
    for info in analytes:
        by_analyte.setdefault(info.analyte, []).append(info)
    for analyte, group in by_analyte.items():
        if len(group) > 1:
            state.log(None, group[0].name, "units", f"{analyte} is reported in more than one column",
                      ", ".join(c.original for c in group), "kept all")
    by_element: dict = {}
    for info in analytes:
        if info.kind in (ELEMENT, OXIDE):
            by_element.setdefault(info.element, []).append(info)
    pairs = []
    for element, group in by_element.items():
        element_columns = [c for c in group if c.kind == ELEMENT]
        oxide_columns = [c for c in group if c.kind == OXIDE]
        if element_columns and oxide_columns:
            state.log(None, element_columns[0].name, "units",
                      f"{element} is reported both as an element and as an oxide",
                      ", ".join(c.original for c in element_columns + oxide_columns), "kept all")
            pairs += [(e, o) for e in element_columns for o in oxide_columns]

    # Row-level checks.
    ceilings = {"pct": 100.0, "ppm": 1.0e6, "ppb": 1.0e9}
    labels = {"pct": "100 wt%", "ppm": "1,000,000 ppm", "ppb": "1,000,000,000 ppb"}
    for info in analytes:
        _note(reasons, df[info.name] > ceilings[info.unit],
              f"{info.name} is above {labels[info.unit]}")

    for element_column, oxide_column in pairs:
        if element_column.element == "Fe":
            continue  # iron oxides may be ferrous, ferric or total; not comparable
        measured = (state.qualifiers[element_column.name].isna()
                    & state.qualifiers[oxide_column.name].isna())
        as_oxide = (df[element_column.name]
                    * unit_factor(element_column.unit, oxide_column.unit)
                    * form_factor(element_column.analyte, oxide_column.analyte))
        reported = df[oxide_column.name]
        larger, smaller = np.maximum(as_oxide, reported), np.minimum(as_oxide, reported)
        floor = ELEMENT_OXIDE_MIN_PCT * unit_factor("pct", oxide_column.unit)
        disagree = measured & (larger >= floor) & (larger > ELEMENT_OXIDE_MAX_RATIO * smaller)
        _note(reasons, disagree,
              f"{element_column.name} and {oxide_column.name} differ by more than "
              f"{ELEMENT_OXIDE_MAX_RATIO:g} times (possible unit mix-up)")

    majors = [c.name for c in analytes if c.analyte in MAJOR_OXIDES and c.unit == "pct"]
    if majors:
        total = df[majors].sum(axis=1, min_count=1)
        _note(reasons, total > MAJOR_TOTAL_LIMIT,
              f"major oxides add up to more than {MAJOR_TOTAL_LIMIT:g} wt%")

    _add_flag(state, "units", reasons)
    return state


# --- step 8: duplicates ----------------------------------------------------------

def flag_duplicates(state: CleaningState) -> CleaningState:
    """Flag repeated samples.  Nothing is removed.

    Rows are grouped when they are identical, share a sample ID or share a lab
    ID.  Repeated QAQC standards are expected and are not flagged.
    """
    df = state.df
    parent = list(range(len(df)))

    def find(i):
        while parent[i] != i:
            parent[i] = parent[parent[i]]
            i = parent[i]
        return i

    reasons_by_position: dict = {}

    def link(keys: pd.Series, reason: str):
        keys = keys.dropna()
        for _, positions in keys.groupby(keys, sort=False).indices.items():
            if len(positions) < 2:
                continue
            members = [df.index.get_loc(keys.index[p]) for p in positions]
            for member in members:
                reasons_by_position.setdefault(member, []).append(reason)
                parent[find(member)] = find(members[0])

    not_qaqc = ~qaqc_rows(df, state.columns)
    for role, reason in (("sample_id", "same sample ID"), ("lab_id", "same lab ID")):
        name = state.role(role)
        if name:
            link(df.loc[not_qaqc, name].str.upper(), reason)

    data_columns = [c.name for c in state.columns]
    # "<10" and 5 both end up as 5, so the qualifiers are compared as well.
    everything = pd.concat([df[data_columns], state.qualifiers.add_suffix("_qualifier")], axis=1)
    link(pd.util.hash_pandas_object(everything, index=False), "identical row")

    flagged = sorted(reasons_by_position)
    roots = {}
    group = pd.Series(pd.NA, index=df.index, dtype="Int64")
    for position in flagged:
        number = roots.setdefault(find(position), len(roots) + 1)
        group.iloc[position] = number
    _add_flag(state, "duplicate",
              {df.index[p]: reasons_by_position[p] for p in flagged})
    df[DUPLICATE_GROUP] = group
    return state


# --- the whole pipeline ---------------------------------------------------------------

def clean(raw: pd.DataFrame, below_detection="half", zeros_are_missing=True,
          utm_zone=15) -> CleaningState:
    """Run every cleaning step on a raw combined table."""
    state = start(raw)
    tidy_text(state)
    parse_numbers(state, below_detection, zeros_are_missing)
    parse_depth(state)
    finish_types(state)
    check_xyz(state, utm_zone)
    check_units(state)
    flag_duplicates(state)
    return state
