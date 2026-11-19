"""What each dataset table holds.  THE ONLY FILE THAT KNOWS DATASET COLUMN NAMES.

Everything else in ``mgslib.data`` works with *roles* (standard names such as
``relateid`` or ``primary_lithology``).  This file says which column of each
dataset table plays each role.

The column names below were checked against the real sources on 2026-10-22:
  - CWI: the ``c4*`` tables of ``cwidata.mdb``
  - QDI: the "Texture Data" layer (view ``mgs_qdi.qdi.vw_qdtx``) and the
    "QDI Locations" layer (table ``mgs_qdi.qdi.qdix``)
Where the sources are is set in ``sources.py``.

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

Add a CWI table
    Add a ``Table`` to ``TABLES`` under ``("cwi", "<table name in cwidata.mdb>")``
    and, if useful, a preset in ``presets.py``.  ``sources.py`` reads any CWI
    table listed here.

Add something ``by={...}`` can filter on
    Add it to ``BY_KEYS`` and teach ``sources.read_cwi`` and
    ``loader._read_qdi`` to apply it.

Roles the code relies on
------------------------
Every table:    ``relateid`` (required; links layers and samples to boreholes)
Borehole table: ``county_code``, ``easting``, ``northing`` (UTM zone 15N), plus anything else
Layer table:    ``depth_top``, ``depth_bottom``, ``primary_lithology``
Sample table:   ``sample_id``, ``depth`` (a single depth; it is copied into
                ``depth_top`` and ``depth_bottom`` so layers and samples share
                one depth filter)

Depths and elevations are in feet in both datasets.  A few QDI rows say
``depth_unit = "m"``; they are left as they are and counted by ``summary()``.
"""

from __future__ import annotations

from dataclasses import dataclass, field

import pandas as pd

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
    # Loaded whenever its dataset is, and never asked for by name.
    automatic: bool = False


TABLES = {
    ("cwi", "c4ix"): Table(
        kind=BOREHOLE,
        description="County Well Index: one row per well (location, depth, elevation)",
        columns={
            "relateid": "RELATEID",
            "county_code": "COUNTY_C",
            "unique_number": "UNIQUE_NO",
            "name": "WELLNAME",
            "easting": "UTME",
            "northing": "UTMN",
            "elevation": "ELEVATION",
            "total_depth": "DEPTH_DRLL",
            "depth_to_bedrock": "DEPTH2BDRK",
        },
    ),
    ("cwi", "c4st"): Table(
        kind=LAYER,
        description="County Well Index: stratigraphy layers (no layer ids, only depths)",
        columns={
            "relateid": "RELATEID",
            "depth_top": "DEPTH_TOP",
            "depth_bottom": "DEPTH_BOT",
            "primary_lithology": "LITH_PRIM",
            "secondary_lithology": "LITH_SEC",
            "minor_lithology": "LITH_MINOR",
            "strat": "STRAT",
            "driller_description": "DRLLR_DESC",
            "color": "COLOR",
            "hardness": "HARDNESS",
        },
    ),
    ("cwi", "c4c1"): Table(
        kind=BOREHOLE,
        description="County Well Index: how each well was built (drill method, casing, pump)",
        columns={
            "relateid": "RELATEID",
            "drill_method": "DRILL_METH",
            "driller": "DRLLR_NAME",
        },
    ),
    ("qdi", "texture"): Table(
        kind=SAMPLE,
        description="Quaternary Data Index: texture and grain-count samples, each at one depth",
        columns={
            "relateid": "relateid",
            "sample_id": "sample_num",
            "depth": "sampledepth",
            "strat": "stratunit",
            "strat_formation": "stratformation",
            "strat_member": "stratmember",
        },
    ),
    ("qdi", "locations"): Table(
        kind=BOREHOLE,
        description="Quaternary Data Index: one row per borehole (location, depth, elevation)",
        columns={
            "relateid": "relateid",
            "county_code": "county_c",
            "unique_number": "unique_no",
            "name": "wellname",
            "easting": "utme",
            "northing": "utmn",
            "elevation": "elevation",
            "total_depth": "depth_drll",
            "depth_to_bedrock": "depth2bdrk",
        },
        automatic=True,
    ),
}

# Roles that hold numbers; they are converted on loading so they can be compared.
NUMERIC_ROLES = ["depth", "depth_top", "depth_bottom", "easting", "northing",
                 "elevation", "total_depth", "depth_to_bedrock"]

# What ``load_data(by={...})`` accepts.
BY_KEYS = {
    "county": 'a county name or code, e.g. {"county": "Ramsey"}',
    "relateid": 'one or more boreholes, e.g. {"relateid": ["2000012", "2000013"]}',
}

# CWI's two-digit county codes (COUNTY_C).
MN_COUNTIES = {
    "01": "Aitkin", "02": "Anoka", "03": "Becker", "04": "Beltrami", "05": "Benton",
    "06": "Big Stone", "07": "Blue Earth", "08": "Brown", "09": "Carlton", "10": "Carver",
    "11": "Cass", "12": "Chippewa", "13": "Chisago", "14": "Clay", "15": "Clearwater",
    "16": "Cook", "17": "Cottonwood", "18": "Crow Wing", "19": "Dakota", "20": "Dodge",
    "21": "Douglas", "22": "Faribault", "23": "Fillmore", "24": "Freeborn", "25": "Goodhue",
    "26": "Grant", "27": "Hennepin", "28": "Houston", "29": "Hubbard", "30": "Isanti",
    "31": "Itasca", "32": "Jackson", "33": "Kanabec", "34": "Kandiyohi", "35": "Kittson",
    "36": "Koochiching", "37": "Lac qui Parle", "38": "Lake", "39": "Lake of the Woods",
    "40": "Le Sueur", "41": "Lincoln", "42": "Lyon", "43": "McLeod", "44": "Mahnomen",
    "45": "Marshall", "46": "Martin", "47": "Meeker", "48": "Mille Lacs", "49": "Morrison",
    "50": "Mower", "51": "Murray", "52": "Nicollet", "53": "Nobles", "54": "Norman",
    "55": "Olmsted", "56": "Otter Tail", "57": "Pennington", "58": "Pine", "59": "Pipestone",
    "60": "Polk", "61": "Pope", "62": "Ramsey", "63": "Red Lake", "64": "Redwood",
    "65": "Renville", "66": "Rice", "67": "Rock", "68": "Roseau", "69": "St. Louis",
    "70": "Scott", "71": "Sherburne", "72": "Sibley", "73": "Stearns", "74": "Steele",
    "75": "Stevens", "76": "Swift", "77": "Todd", "78": "Traverse", "79": "Wabasha",
    "80": "Wadena", "81": "Waseca", "82": "Washington", "83": "Watonwan", "84": "Wilkin",
    "85": "Winona", "86": "Wright", "87": "Yellow Medicine",
}


def _county_key(name) -> str:
    key = str(name).strip().lower().replace(".", "").removesuffix(" county")
    return key.replace("saint ", "st ")


_COUNTY_BY_NAME = {_county_key(name): code for code, name in MN_COUNTIES.items()}


def county_code(value) -> str:
    """The CWI county code for a county name or code: "Ramsey", "62" and 62 all give "62"."""
    text = str(value).strip()
    if text.isdigit() and text.zfill(2) in MN_COUNTIES:
        return text.zfill(2)
    code = _COUNTY_BY_NAME.get(_county_key(text))
    if code is None:
        raise ValueError(f"No Minnesota county called '{value}'. "
                         f"Available: {', '.join(MN_COUNTIES.values())}.")
    return code


def standard_relateid(value):
    """A relateid as text, written the same way whichever dataset it came from.

    All-digit ids are padded with zeros to 10 characters, as CWI writes them,
    so "2000012", 2000012 and "0002000012" are the same borehole.
    """
    if value is None or pd.isna(value):
        return None
    if isinstance(value, float) and value.is_integer():
        value = int(value)
    text = str(value).strip()
    if text.isdigit():
        text = text.zfill(10)
    return text or None


def datasets() -> dict:
    """Every dataset and the tables that can be asked for: ``{"cwi": ["c4ix", ...], ...}``."""
    found = {}
    for (dataset, name), table in TABLES.items():
        if not table.automatic:
            found.setdefault(dataset, []).append(name)
    return found
