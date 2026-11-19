"""Where the data lives, and the only code that touches it.  READ ONLY.

CWI is an Access database and QDI is a pair of ArcGIS layers on the QDI
database.  Both are only ever read:

  - CWI is opened through the Access ODBC driver in read-only mode (both in
    the connection string and on the connection itself), and only the
    SELECT statements built below are run.  Table and column names come from
    ``schema.py``; values from ``by`` are sent as parameters, never pasted
    into the SQL.
  - QDI is read by ``_qdi_reader.py``, run with ArcGIS Pro's Python, which
    only uses a SearchCursor and never saves the layer files.

Each location can be pointed somewhere else (a copy, for testing) with an
environment variable: MGSLIB_CWI_PATH, MGSLIB_QDI_FOLDER, MGSLIB_ARCGIS_PYTHON.
"""

from __future__ import annotations

import os
import subprocess
import tempfile
from pathlib import Path

import pandas as pd

from .schema import TABLES

CWI_PATH = r"T:\db_prod\cwi\data\cwidata.mdb"
QDI_FOLDER = r"L:\gdrs\data\pub\edu_umn_mngs\geos_quaternary_data_index"
# QDI table -> its layer file in QDI_FOLDER.
QDI_LAYERS = {"texture": "Texture Data.lyr",        # view mgs_qdi.qdi.vw_qdtx
              "locations": "QDI Locations.lyr"}     # table mgs_qdi.qdi.qdix
ARCGIS_PYTHON = r"C:\Program Files\ArcGIS\Pro\bin\Python\envs\arcgispro-py3\python.exe"

ACCESS_DRIVER = "Microsoft Access Driver (*.mdb, *.accdb)"
QDI_TIMEOUT_SECONDS = 900
CHUNK = 500     # values per IN (...) list

_qdi_cache = None


def _existing(path, what, hint) -> Path:
    path = Path(path)
    if not path.exists():
        raise FileNotFoundError(f"Cannot find {what} at {path}. {hint}")
    return path


def cwi_path() -> Path:
    return _existing(os.environ.get("MGSLIB_CWI_PATH") or CWI_PATH, "the CWI database",
                     "Check that the T: drive is connected.")


def qdi_layer(table) -> Path:
    folder = os.environ.get("MGSLIB_QDI_FOLDER") or QDI_FOLDER
    return _existing(Path(folder) / QDI_LAYERS[table], "the QDI layer file",
                     "Check that the L: drive is connected.")


def arcgis_python() -> Path:
    return _existing(os.environ.get("MGSLIB_ARCGIS_PYTHON") or ARCGIS_PYTHON,
                     "ArcGIS Pro's Python",
                     "Loading QDI data needs ArcGIS Pro installed on this computer.")


# --- CWI ------------------------------------------------------------------------------

def _connect_cwi():
    import pyodbc
    path = cwi_path()
    try:
        return pyodbc.connect(f"Driver={{{ACCESS_DRIVER}}};Dbq={path};ReadOnly=1;Exclusive=0;",
                              readonly=True, autocommit=True)
    except pyodbc.InterfaceError:
        raise ConnectionError(
            f"Could not open the CWI database at {path}. This needs the 64-bit "
            f'"{ACCESS_DRIVER}" from Microsoft (part of the Access Database Engine).') from None


def _select(connection, sql, params=()) -> pd.DataFrame:
    cursor = connection.cursor()
    try:
        cursor.execute(sql, list(params))
        columns = [d[0] for d in cursor.description]
        rows = [tuple(r) for r in cursor.fetchall()]
    finally:
        cursor.close()
    return pd.DataFrame(rows, columns=columns)


def _chunks(values):
    values = list(values)
    for start in range(0, len(values), CHUNK):
        yield values[start:start + CHUNK]


def read_cwi(tables, by) -> dict:
    """Read CWI tables.  Returns ``{"cwi.c4ix": DataFrame, ...}``.

    ``by`` must already be checked: ``{"county": ["62"], "relateid": ["0002000012"]}``.
    """
    if not by:
        print("Loading all of CWI for the whole state; this may take a few minutes.")
    connection = _connect_cwi()
    try:
        return {f"cwi.{name}": _read_cwi_table(connection, name, by) for name in tables}
    finally:
        connection.close()


def _read_cwi_table(connection, name, by) -> pd.DataFrame:
    if ("cwi", name) not in TABLES:
        raise ValueError(f"mgslib does not know a CWI table called '{name}'.")
    # Every CWI table has RELATEID; only c4ix has the county, so other tables join to it.
    sql = f"SELECT t.* FROM [{name}] AS t"
    where, params = [], []
    if "county" in by:
        if name != "c4ix":
            sql += " INNER JOIN [c4ix] AS ix ON t.RELATEID = ix.RELATEID"
        column = "t.COUNTY_C" if name == "c4ix" else "ix.COUNTY_C"
        where.append(f"{column} IN ({', '.join('?' * len(by['county']))})")
        params += by["county"]
    if "relateid" not in by:
        return _select(connection, _where(sql, where), params)
    parts = [_select(connection,
                     _where(sql, where + [f"t.RELATEID IN ({', '.join('?' * len(ids))})"]),
                     params + ids)
             for ids in _chunks(by["relateid"])]
    return pd.concat(parts, ignore_index=True)


def _where(sql, conditions) -> str:
    return f"{sql} WHERE {' AND '.join(conditions)}" if conditions else sql


# --- QDI ------------------------------------------------------------------------------

def read_qdi(refresh=False) -> dict:
    """Every row of the QDI layers: ``{"qdi.texture": DataFrame, "qdi.locations": DataFrame}``.

    Read once per Python session and then kept; ``refresh=True`` reads them again.
    """
    global _qdi_cache
    if _qdi_cache is None or refresh:
        _qdi_cache = _read_qdi_layers()
    return {name: frame.copy() for name, frame in _qdi_cache.items()}


def _read_qdi_layers() -> dict:
    python = arcgis_python()
    layers = {table: qdi_layer(table) for table in QDI_LAYERS}
    reader = Path(__file__).with_name("_qdi_reader.py")
    print("Reading QDI through ArcGIS Pro; this takes a minute or two.")
    with tempfile.TemporaryDirectory(prefix="mgslib_qdi_") as folder:
        outputs = {table: Path(folder) / f"{table}.csv" for table in layers}
        arguments = [str(p) for table in layers for p in (layers[table], outputs[table])]
        try:
            # -I: ignore the user's site packages and environment variables.
            result = subprocess.run([str(python), "-I", str(reader), *arguments],
                                    capture_output=True, text=True,
                                    timeout=QDI_TIMEOUT_SECONDS,
                                    creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0))
        except subprocess.TimeoutExpired:
            raise ConnectionError("Reading QDI took too long. Check that you are on the "
                                  "MGS network and try again.") from None
        if result.returncode != 0 or not all(p.exists() for p in outputs.values()):
            detail = "\n".join(result.stderr.strip().splitlines()[-5:])
            raise ConnectionError(f"Could not read QDI through ArcGIS Pro:\n{detail}")
        text = {"relateid": "string", "sample_num": "string", "county_c": "string",
                "unique_no": "string"}
        return {f"qdi.{table}": pd.read_csv(path, dtype=text, low_memory=False)
                for table, path in outputs.items()}
