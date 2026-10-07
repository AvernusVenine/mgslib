"""Ask the server for data and put it together into a ``GeoData``."""

from __future__ import annotations

import pandas as pd

from .._util import as_list
from . import client
from .geo_data import RECORD_COLUMNS, GeoData
from .schema import (BOREHOLE, BY_KEYS, NUMERIC_ROLES, SAMPLE, TABLES, datasets,
                     standard_relateid)


def load_data(include, by=None) -> GeoData:
    """Load borehole data from the MGS data server.

    Parameters
    ----------
    include : which datasets and tables to load, as ``{dataset: [tables]}``.
        Use one of the ready-made choices (``INCLUDE_QUAT_DATA``,
        ``INCLUDE_CWI``, ``INCLUDE_QDI``, ``INCLUDE_ALL``) or write your own,
        e.g. ``{"cwi": ["c5st", "c5ix"], "qdi": ["qdi"]}``.
    by : which part of the data to load, e.g. ``{"county": "Ramsey"}``.
        Give several values as a list: ``{"county": ["Ramsey", "Dakota"]}``.

    Example
    -------
        from mgslib.data import load_data, INCLUDE_QUAT_DATA

        data = load_data(include=INCLUDE_QUAT_DATA, by={"county": "Ramsey"})
        data.summary()
    """
    include = _check_include(include)
    by = _check_by(by)
    records, boreholes = assemble(client.fetch(include, by))
    return GeoData(records, boreholes, settings={"include": include, "by": by})


def _check_include(include) -> dict:
    available = datasets()
    example = 'e.g. include={"cwi": ["c5st", "c5ix"]} or include=INCLUDE_QUAT_DATA'
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
        checked[name] = [str(v).strip() for v in as_list([values])]
    return checked


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
    """Turn the server's tables into (layers and samples, boreholes)."""
    records, boreholes = [], []
    for key, frame in tables.items():
        dataset, _, name = str(key).partition(".")
        table = TABLES.get((dataset, name))
        if table is None:
            raise ValueError(f"The server sent a table called '{key}' that mgslib does not "
                             "know about. mgslib may need updating.")
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
