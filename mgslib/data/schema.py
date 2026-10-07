"""What each dataset table holds.  THE ONLY FILE THAT KNOWS DATASET COLUMN NAMES.

Everything else in ``mgslib.data`` works with *roles* (standard names such as
``relateid`` or ``primary_lithology``).  This file says which column of each
dataset table plays each role.

STATUS: the real column layouts were not available when this was written.
  - CWI names below come from the public CWI layout and are marked UNVERIFIED.
  - QDI names are unknown and are left as ``None`` (a role mapped to ``None``
    is simply skipped).
Check every line marked UNVERIFIED or TODO against the real tables.

How to make changes
-------------------
Fill in or correct a column
    Edit the ``columns`` map of the table: ``"role": "COLUMN_NAME_IN_DATASET"``.
    Names are matched without regard to upper/lower case.  A column that is
    not mapped still comes through, under its own name in lower case, and can
    be used with ``data.filter_by("that_name", ...)``.

Add a new role with its own named filter
    1. Map it here in every table that has it.
    2. If it holds numbers, add it to ``NUMERIC_ROLES``.
    3. Add a one-line ``filter_by_<role>`` method to ``GeoData`` in
       ``geo_data.py`` (copy ``filter_by_primary_lithology`` for a
       layer/sample column, ``filter_by_county`` for a borehole column).

Add a table or a dataset
    Add a ``Table`` to ``TABLES`` and, if useful, a preset in ``presets.py``.
    The server must return it under the key ``"<dataset>.<table>"``.

Add something ``by={...}`` can filter on
    Add it to ``BY_KEYS``.  The server has to understand it too.

Roles the code relies on
------------------------
Every table:    ``relateid`` (required; links layers and samples to boreholes)
Borehole table: ``county``, ``easting``, ``northing`` (UTM), plus anything else
Layer table:    ``depth_top``, ``depth_bottom``, ``primary_lithology``
Sample table:   ``sample_id``, ``depth`` (a single depth; it is copied into
                ``depth_top`` and ``depth_bottom`` so layers and samples share
                one depth filter), ``primary_lithology``

Open questions for when the layouts arrive
------------------------------------------
- How is relateid written in each dataset (text or number, zero padded)?  If
  the datasets differ, make them agree in ``standard_relateid`` below.
- QDI may hold borehole-level columns (location, county) in the same table as
  the samples.  If so it needs to feed both tables: the simplest way is to
  have the server return a second table (e.g. ``qdi.holes``) and add it here
  as a BOREHOLE table.
- Depth units (CWI is feet); record the unit if datasets differ.
"""

from __future__ import annotations

from dataclasses import dataclass, field

# Table kinds.
BOREHOLE = "borehole"   # one row per borehole
LAYER = "layer"         # a depth interval (top and bottom) within a borehole
SAMPLE = "sample"       # a sample taken at a single depth within a borehole


@dataclass(frozen=True)
class Table:
    """What one dataset table holds."""

    kind: str                 # one of the kinds above
    description: str = ""
    columns: dict = field(default_factory=dict)   # role -> column name in the dataset


TABLES = {
    ("cwi", "c5ix"): Table(
        kind=BOREHOLE,
        description="County Well Index: one row per well (location, depth, elevation)",
        columns={
            "relateid": "RELATEID",        # UNVERIFIED
            "county": "COUNTY_C",          # UNVERIFIED - a county code, not a name?
            "unique_number": "UNIQUE_NO",  # UNVERIFIED
            "name": "WELLNAME",            # UNVERIFIED
            "easting": "UTME",             # UNVERIFIED
            "northing": "UTMN",            # UNVERIFIED
            "elevation": "ELEVATION",      # UNVERIFIED
            "total_depth": "DEPTH_DRLL",   # UNVERIFIED
        },
    ),
    ("cwi", "c5st"): Table(
        kind=LAYER,
        description="County Well Index: stratigraphy layers (no layer ids, only depths)",
        columns={
            "relateid": "RELATEID",            # UNVERIFIED
            "depth_top": "DEPTH_TOP",          # UNVERIFIED
            "depth_bottom": "DEPTH_BOT",       # UNVERIFIED
            "primary_lithology": "LITH_PRIM",  # UNVERIFIED
            "secondary_lithology": "LITH_SEC",  # UNVERIFIED
            "minor_lithology": "LITH_MINOR",   # UNVERIFIED
            "strat": "STRAT",                  # UNVERIFIED
            "driller_description": "DRLLR_DESC",  # UNVERIFIED
            "color": "COLOR",                  # UNVERIFIED
            "hardness": "HARDNESS",            # UNVERIFIED
        },
    ),
    ("qdi", "qdi"): Table(
        kind=SAMPLE,
        description="Quaternary Data Index: samples, each taken at a single depth",
        columns={
            "relateid": "RELATEID",        # TODO: confirm
            "sample_id": None,             # TODO
            "depth": None,                 # TODO
            "primary_lithology": None,     # TODO (if QDI has one)
        },
    ),
}

# Roles that hold numbers; they are converted on loading so they can be compared.
NUMERIC_ROLES = ["depth", "depth_top", "depth_bottom", "easting", "northing",
                 "elevation", "total_depth"]

# What ``load_data(by={...})`` accepts.  TODO: extend to match the server.
BY_KEYS = {
    "county": 'a county name, e.g. {"county": "Ramsey"}',
    "relateid": 'one or more boreholes, e.g. {"relateid": ["2000012", "2000013"]}',
}


def standard_relateid(value):
    """A relateid as text, written the same way whichever dataset it came from."""
    if value is None or value != value:
        return None
    if isinstance(value, float) and value.is_integer():
        value = int(value)
    return str(value).strip() or None


def datasets() -> dict:
    """Every dataset and its tables: ``{"cwi": ["c5ix", "c5st"], "qdi": ["qdi"]}``."""
    found = {}
    for dataset, table in TABLES:
        found.setdefault(dataset, []).append(table)
    return found
