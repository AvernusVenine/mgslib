"""Read data from its sources and put it together into a ``GeoData``."""

from __future__ import annotations

import pandas as pd

from .._util import as_list
from . import sources
from .geo_data import RECORD_COLUMNS, GeoData
from .schema import (BOREHOLE, BY_KEYS, MN_COUNTIES, NUMERIC_ROLES, SAMPLE, TABLES,
                     county_code, datasets, standard_relateid)


def load_data(include, by=None, refresh=False) -> GeoData:
    """Load borehole data from CWI and QDI.  The sources are only ever read.

    Parameters
    ----------
    include : which datasets and tables to load, as ``{dataset: [tables]}``.
        Use one of the ready-made choices (``INCLUDE_QUAT_DATA``,
        ``INCLUDE_CWI``, ``INCLUDE_QDI``, ``INCLUDE_ALL``) or write your own,
        e.g. ``{"cwi": ["c4st", "c4ix"], "qdi": ["texture"]}``.
    by : which part of the data to load, e.g. ``{"county": "Ramsey"}``.
        Give several values as a list: ``{"county": ["Ramsey", "Dakota"]}``.
    refresh : QDI is read once per session and then kept.  ``refresh=True``
        reads it again, to pick up changes made since.

    Example
    -------
        from mgslib.data import load_data, INCLUDE_QUAT_DATA

        data = load_data(include=INCLUDE_QUAT_DATA, by={"county": "Ramsey"})
        data.summary()
    """
    include = _check_include(include)
    by = _check_by(by)
    tables = {}
    if "cwi" in include:
        tables.update(sources.read_cwi(include["cwi"], by))
    if "qdi" in include:
        tables.update(_read_qdi(by, refresh))
    records, boreholes = assemble(tables)
    if "county_code" in boreholes.columns:
        boreholes["county_code"] = (boreholes["county_code"].astype("string").str.strip()
                                    .str.zfill(2).astype(object))
        boreholes.insert(boreholes.columns.get_loc("county_code"), "county",
                         boreholes["county_code"].map(MN_COUNTIES))
    return GeoData(records, boreholes, settings={"include": include, "by": by})


def _check_include(include) -> dict:
    available = datasets()
    example = 'e.g. include={"cwi": ["c4st", "c4ix"]} or include=INCLUDE_QUAT_DATA'
    if not isinstance(include, dict) or not include:
        raise ValueError(f"include must say which datasets and tables to load, {example}.")
    checked = {}
    for dataset, tables in include.items():
        name = str(dataset).strip().lower()
        if name not in available:
            raise ValueError(f"No dataset called '{dataset}'. "
                             f"Available: {', '.join(available)}.")
        tables = [str(t).strip().lower() for t in as_list([tables])]
        unknown = [t for t in tables if t not in available[name]]
        if unknown:
            raise ValueError(f"The {name} dataset has no table called {unknown}. "
                             f"Available: {', '.join(available[name])}.")
        if not tables:
            raise ValueError(f"Name at least one table of the {name} dataset, {example}.")
        checked[name] = tables
    return checked


def _check_by(by) -> dict:
    """``by`` with keys in lower case, county names turned into codes and relateids padded."""
    if by is None:
        return {}
    if not isinstance(by, dict):
        raise ValueError('by must look like {"county": "Ramsey"}.')
    checked = {}
    for key, values in by.items():
        name = str(key).strip().lower()
        if name not in BY_KEYS:
            options = "; ".join(f"{k} ({v})" for k, v in BY_KEYS.items())
            raise ValueError(f"Data cannot be loaded by '{key}'. Available: {options}.")
        values = as_list([values])
        if not values:
            raise ValueError(f"Give at least one {name} in by.")
        if name == "county":
            checked[name] = list(dict.fromkeys(county_code(v) for v in values))
        else:
            checked[name] = list(dict.fromkeys(standard_relateid(v) for v in values))
    return checked


def _read_qdi(by, refresh) -> dict:
    """The QDI samples and their boreholes, narrowed to ``by``."""
    tables = sources.read_qdi(refresh)
    samples, holes = tables["qdi.texture"], tables["qdi.locations"]
    # The texture view repeats each borehole's location; it comes from qdix instead.
    samples = samples.drop(columns=["x", "y", "elevation"], errors="ignore")
    sample_ids = samples["relateid"].map(standard_relateid)
    hole_ids = holes["relateid"].map(standard_relateid)
    if "county" in by:
        codes = holes["county_c"].astype("string").str.strip().str.zfill(2)
        keep = codes.isin(by["county"])
        holes = holes[keep.fillna(False).to_numpy()]
        samples = samples[sample_ids.isin(hole_ids[holes.index]).to_numpy()]
    if "relateid" in by:
        samples = samples[sample_ids[samples.index].isin(by["relateid"]).to_numpy()]
    # qdix also lists boreholes with no texture samples; keep only those that have some.
    holes = holes[hole_ids[holes.index].isin(sample_ids[samples.index]).to_numpy()]
    return {"qdi.texture": samples, "qdi.locations": holes}


def _standardise(frame, table) -> pd.DataFrame:
    """Rename a dataset table's columns to their roles; the rest go to lower case."""
    frame = frame.copy()
    frame.columns = [str(c).strip().lower() for c in frame.columns]
    roles = {column.lower(): role for role, column in table.columns.items() if column}
    roles = {column: role for column, role in roles.items() if column in frame.columns}
    # A dataset column that already has the name of a role steps aside for it.
    taken = set(roles.values())
    frame = frame.rename(columns={c: f"{c}_original" for c in frame.columns
                                  if c in taken and c not in roles})
    frame = frame.rename(columns=roles)
    for role in NUMERIC_ROLES:
        if role in frame.columns:
            frame[role] = pd.to_numeric(frame[role], errors="coerce")
    return frame


def assemble(tables) -> tuple:
    """Turn the dataset tables into (layers and samples, boreholes)."""
    records, boreholes = [], []
    for key, frame in tables.items():
        dataset, _, name = str(key).partition(".")
        table = TABLES.get((dataset, name))
        if table is None:
            raise ValueError(f"mgslib does not know a table called '{key}'.")
        frame = _standardise(frame, table)
        if "relateid" not in frame.columns:
            raise ValueError(f"The {key} table has no relateid column, so it cannot be "
                             "linked to boreholes. mgslib may need updating.")
        frame["relateid"] = frame["relateid"].map(standard_relateid).astype(object)
        if table.kind == BOREHOLE:
            boreholes.append(frame)
            continue
        if table.kind == SAMPLE and "depth" in frame.columns:
            frame["depth_top"] = frame["depth_bottom"] = frame.pop("depth")
        frame["kind"], frame["dataset"], frame["table"] = table.kind, dataset, name
        records.append(frame)

    records = _stack(records, RECORD_COLUMNS)
    boreholes = _stack(boreholes, ["relateid"])
    boreholes = boreholes.groupby("relateid", sort=False, as_index=False).first()
    # Every borehole that has a layer or sample gets a row, even with no other details.
    known = set(boreholes["relateid"])
    extra = [r for r in records["relateid"].dropna().unique() if r not in known]
    if extra:
        boreholes = pd.concat([boreholes, pd.DataFrame({"relateid": extra})],
                              ignore_index=True)
    return records, boreholes


def _stack(frames, first_columns) -> pd.DataFrame:
    """Stack tables into one, with ``first_columns`` always present and in front."""
    frames = [f for f in frames if len(f)]
    table = pd.concat(frames, ignore_index=True, sort=False) if frames else pd.DataFrame()
    for column in first_columns:
        if column not in table.columns:
            table[column] = pd.Series(pd.NA, index=table.index, dtype=object)
    rest = [c for c in table.columns if c not in first_columns]
    return table[first_columns + rest]
