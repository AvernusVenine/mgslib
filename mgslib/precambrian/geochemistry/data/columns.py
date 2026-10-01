"""Work out what each column header means: metadata, or an analyte and its unit."""

from __future__ import annotations

import re
from dataclasses import dataclass, replace

from .units import ELEMENT_SYMBOLS, UNIT_ALIASES, parse_oxide

# Column kinds.
METADATA = "metadata"
ELEMENT = "element"
OXIDE = "oxide"
IRON_TOTAL = "iron_total"
OTHER = "other"
DERIVED = "derived"


@dataclass(frozen=True)
class ColumnInfo:
    """What one column of the table holds."""

    original: str            # header as written in the file
    name: str                # standard name used in the cleaned table
    kind: str                # one of the kinds above
    role: str | None = None  # for key metadata columns: "sample_id", "easting", ...
    analyte: str | None = None   # "Ti", "TiO2", "LOI", ...
    element: str | None = None   # "Ti" for both Ti and TiO2
    unit: str | None = None      # "pct", "ppm", "ppb"
    unit_assumed: bool = False   # True when the header gave no unit
    numeric: bool = False

    @property
    def is_analyte(self) -> bool:
        return self.kind != METADATA


# Headers (lower-cased, letters and digits only, text in brackets removed)
# that identify the key metadata columns.
ROLE_ALIASES = {
    "sample_id": ["sampleid", "sample", "samplenumber", "sampleno", "samplename"],
    "lab_id": ["labid", "labnumber", "labno"],
    "analytical_type": ["analyticaltype", "qaqctype"],
    "sample_type": ["sampletype"],
    "hole_id": ["outcropordhid", "holeid", "dhid", "drillholeid", "bhid", "drillhole", "outcropid"],
    "analytical_lab": ["analyticallab", "lab", "laboratory"],
    "method_description": ["methoddescription", "method"],
    "analysis_date": ["analysisdate", "dateanalyzed", "date"],
    "reference": ["reference"],
    "rock_type": ["rocktype"],
    "rock_name": ["rockname"],
    "lithology": ["simplelithology", "lithology", "lith"],
    "sample_description": ["sampledescription", "description"],
    "unit_name": ["unitname", "formation"],
    "basin_terrane": ["basinterrane", "basin", "terrane"],
    "notes": ["notes", "note", "comments", "comment"],
}
_ROLE_BY_KEY = {key: role for role, keys in ROLE_ALIASES.items() for key in keys}

_IRON_TOTAL_NAMES = {
    "feot": "FeOt", "feo*": "FeOt", "feotot": "FeOt", "feototal": "FeOt", "tfeo": "FeOt",
    "fe2o3t": "Fe2O3t", "fe2o3*": "Fe2O3t", "fe2o3tot": "Fe2O3t",
    "fe2o3total": "Fe2O3t", "tfe2o3": "Fe2O3t",
}

_UNIT_WORDS = "|".join(re.escape(u) for u in sorted(UNIT_ALIASES, key=len, reverse=True))
_BRACKET = re.compile(r"^(.*?)\s*\((.*)\)\s*$")
_SUFFIX_UNIT = re.compile(rf"^(.+?)[\s_]+({_UNIT_WORDS})$", re.IGNORECASE)
# "C (%)" exported through software that replaces " (%)" with four underscores.
_MANGLED_PERCENT = re.compile(r"^([A-Za-z0-9]+)____$")
_DEPTH_UNIT = re.compile(r"\(\s*(ft|feet|m|meters|metres)\s*\)", re.IGNORECASE)
_NUMBER_LIKE = re.compile(r"^\s*[<>]?\s*-?\d+(\.\d+)?\s*$")


def _key(text: str) -> str:
    return re.sub(r"[^0-9a-z]", "", text.lower())


def _slug(text: str) -> str:
    text = text.replace("+", " plus ")
    return re.sub(r"[^0-9a-zA-Z]+", "_", text).strip("_")


def _metadata(header: str) -> ColumnInfo | None:
    """Recognise a key metadata column, or return None."""
    base = header.split("(")[0]
    key = _key(base)
    if key.startswith("easting") or key in ("utme", "utmeasting"):
        return ColumnInfo(header, "easting", METADATA, role="easting", numeric=True)
    if key.startswith("northing") or key in ("utmn", "utmnorthing"):
        return ColumnInfo(header, "northing", METADATA, role="northing", numeric=True)
    if "depth" in key:
        unit = _DEPTH_UNIT.search(header)
        name = "depth"
        if unit:
            name = "depth_ft" if unit.group(1).lower() in ("ft", "feet") else "depth_m"
        return ColumnInfo(header, name, METADATA, role="depth", numeric=True)
    if key.startswith("magneticsusceptibility") or key.startswith("magsus"):
        return ColumnInfo(header, _slug(header).lower(), METADATA, numeric=True)
    role = _ROLE_BY_KEY.get(key)
    if role:
        return ColumnInfo(header, role, METADATA, role=role)
    return None


def _split_unit(header: str):
    """Return (analyte text, unit code or None, unit_was_given)."""
    text = header.strip()
    bracket = _BRACKET.match(text)
    if bracket and bracket.group(2).strip().lower() in UNIT_ALIASES:
        return bracket.group(1).strip(), UNIT_ALIASES[bracket.group(2).strip().lower()], True
    mangled = _MANGLED_PERCENT.match(text)
    if mangled:
        return mangled.group(1), "pct", False
    suffix = _SUFFIX_UNIT.match(text)
    if suffix:
        return suffix.group(1).strip("_ "), UNIT_ALIASES[suffix.group(2).lower()], True
    return text.rstrip("_ "), None, False


def _analyte(header: str) -> ColumnInfo | None:
    """Recognise an analyte column, or return None."""
    bracket = _BRACKET.match(header.strip())
    if bracket and "derived" in bracket.group(2).lower():
        name = _slug(bracket.group(1)) + "_derived"
        return ColumnInfo(header, name, DERIVED, analyte=name, numeric=True)

    token, unit, unit_given = _split_unit(header)
    assumed = not unit_given
    unit = unit or "pct"

    def column(kind, analyte, element=None):
        return ColumnInfo(header, f"{analyte}_{unit}", kind, analyte=analyte,
                          element=element, unit=unit, unit_assumed=assumed, numeric=True)

    if token.lower() in _IRON_TOTAL_NAMES:
        return column(IRON_TOTAL, _IRON_TOTAL_NAMES[token.lower()], "Fe")
    if token in ELEMENT_SYMBOLS:
        return column(ELEMENT, token, token)
    oxide = parse_oxide(token)
    if oxide:
        return column(OXIDE, token, oxide[0])
    if token.upper() == "LOI":
        return column(OTHER, "LOI")
    if unit_given and token.capitalize() in ELEMENT_SYMBOLS:
        symbol = token.capitalize()
        return column(ELEMENT, symbol, symbol)
    # An oxide with a short suffix, e.g. "Fe2O3c".
    for cut in (1, 2, 3):
        if parse_oxide(token[:-cut]):
            return column(OTHER, token)
    if unit_given and re.fullmatch(r"[A-Za-z0-9+*-]+", token):
        return column(OTHER, token)
    return None


def _mostly_numbers(values) -> bool:
    values = [v for v in values if v is not None and str(v).strip() != ""]
    if not values:
        return True
    numeric = sum(
        1 for v in values
        if isinstance(v, (int, float)) or _NUMBER_LIKE.match(str(v))
    )
    return numeric / len(values) >= 0.8


def build_columns(headers, table=None) -> list[ColumnInfo]:
    """Describe every column.  ``table`` (a DataFrame) is used to decide whether
    an unrecognised column holds numbers or text."""
    columns: list[ColumnInfo] = []
    used: dict[str, int] = {}
    for header in headers:
        header = str(header)
        numeric = table is not None and _mostly_numbers(table[header].tolist())
        info = _metadata(header) or _analyte(header)
        # A header with no unit only counts as an analyte if the column holds
        # numbers ("No", "As" or "In" could equally be ordinary words).
        if info is not None and info.unit_assumed and table is not None and not numeric:
            info = None
        if info is None:
            info = ColumnInfo(header, _slug(header).lower() or "unnamed", METADATA, numeric=numeric)
        count = used.get(info.name, 0) + 1
        used[info.name] = count
        if count > 1:
            info = replace(info, name=f"{info.name}_{count}",
                           role=None if info.kind == METADATA else info.role)
        columns.append(info)
    return columns


def column_for_role(columns, role: str) -> str | None:
    """Standard name of the column playing ``role``, or None if the file has none."""
    for info in columns:
        if info.role == role:
            return info.name
    return None
