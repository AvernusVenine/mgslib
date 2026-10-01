"""Read an Excel or CSV file into one combined, uncleaned table."""

from __future__ import annotations

from pathlib import Path

import pandas as pd

SOURCE_SHEET = "source_sheet"
SOURCE_ROW = "source_row"

EXCEL_SUFFIXES = {".xlsx", ".xlsm", ".xls", ".xlsb", ".ods"}
CSV_SUFFIXES = {".csv", ".txt", ".tsv"}


def _is_empty(value) -> bool:
    return value is None or (isinstance(value, str) and value.strip() == "") or value != value


def _tidy(value):
    """Blank cells become None; whole-number floats become ints (18435.0 -> 18435)."""
    if _is_empty(value):
        return None
    if isinstance(value, float) and value.is_integer():
        return int(value)
    return value


def _table_from_rows(rows, sheet_name: str) -> pd.DataFrame | None:
    """Build a table from a list of rows whose first row is the header.

    Row numbers match the spreadsheet (header is row 1), so a problem can be
    traced back to its cell.
    """
    if not rows:
        return None
    header = [None if _is_empty(h) else str(h).strip() for h in rows[0]]
    width = len(header)
    records, row_numbers = [], []
    for number, row in enumerate(rows[1:], start=2):
        row = [_tidy(v) for v in list(row)[:width]]
        row += [None] * (width - len(row))
        if any(v is not None for v in row):
            records.append(row)
            row_numbers.append(number)
    if not records:
        return None

    names, seen = [], {}
    for position, name in enumerate(header):
        has_data = any(record[position] is not None for record in records)
        if name is None:
            name = f"unnamed_{position + 1}" if has_data else None
        elif name in seen:
            seen[name] += 1
            name = f"{name} ({seen[name]})"
        else:
            seen[name] = 1
        names.append(name)

    keep = [i for i, name in enumerate(names) if name is not None]
    table = pd.DataFrame(
        [[record[i] for i in keep] for record in records],
        columns=[names[i] for i in keep],
        dtype=object,
    )
    table[SOURCE_SHEET] = sheet_name
    table[SOURCE_ROW] = row_numbers
    return table


def _read_excel(path: Path, sheets) -> list[pd.DataFrame]:
    try:
        from python_calamine import CalamineWorkbook
    except ImportError:  # slower, but always available with pandas + openpyxl
        return _read_excel_with_pandas(path, sheets)

    workbook = CalamineWorkbook.from_path(str(path))
    names = _choose_sheets(workbook.sheet_names, sheets)
    tables = []
    for name in names:
        rows = workbook.get_sheet_by_name(name).to_python(skip_empty_area=False)
        tables.append(_table_from_rows(rows, name))
    return [t for t in tables if t is not None]


def _read_excel_with_pandas(path: Path, sheets) -> list[pd.DataFrame]:
    workbook = pd.ExcelFile(path)
    tables = []
    for name in _choose_sheets(workbook.sheet_names, sheets):
        frame = workbook.parse(name, header=None, dtype=object)
        tables.append(_table_from_rows(frame.values.tolist(), name))
    return [t for t in tables if t is not None]


def _choose_sheets(available, sheets) -> list[str]:
    if sheets is None:
        return list(available)
    if isinstance(sheets, str):
        sheets = [sheets]
    missing = [s for s in sheets if s not in available]
    if missing:
        raise ValueError(
            f"Sheet(s) {missing} not found. This file has: {list(available)}"
        )
    return list(sheets)


def _read_csv(path: Path) -> list[pd.DataFrame]:
    separator = "\t" if path.suffix.lower() == ".tsv" else ","
    for encoding in ("utf-8-sig", "cp1252"):
        try:
            frame = pd.read_csv(path, header=None, dtype=object, sep=separator,
                                keep_default_na=False, encoding=encoding)
            break
        except UnicodeDecodeError:
            continue
    table = _table_from_rows(frame.values.tolist(), path.stem)
    return [] if table is None else [table]


def read_tables(path, sheets=None) -> pd.DataFrame:
    """Read every table in the file and stack them into one.

    Empty sheets, empty rows and empty columns are dropped.  Two columns are
    added: ``source_sheet`` and ``source_row`` (the row number in that sheet).
    """
    path = Path(path)
    if not path.exists():
        raise FileNotFoundError(f"Could not find the file: {path}")
    suffix = path.suffix.lower()
    if suffix in EXCEL_SUFFIXES:
        tables = _read_excel(path, sheets)
    elif suffix in CSV_SUFFIXES:
        tables = _read_csv(path)
    else:
        raise ValueError(
            f"'{path.name}' is not a supported file type. Use an Excel (.xlsx) or CSV (.csv) file."
        )
    if not tables:
        raise ValueError(f"No data found in {path.name}.")

    combined = pd.concat(tables, ignore_index=True, sort=False)
    data_columns = [c for c in combined.columns if c not in (SOURCE_SHEET, SOURCE_ROW)]
    combined = combined[data_columns + [SOURCE_SHEET, SOURCE_ROW]]
    return combined.astype(object).where(combined.notna(), None)
