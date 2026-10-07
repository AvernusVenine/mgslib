"""Boreholes with their layers and samples, and the plain-English ways to query them."""

from __future__ import annotations

from pathlib import Path

import pandas as pd

from .._util import as_list
from .schema import LAYER, SAMPLE

# Columns every layer and sample has, in the order they are shown.
RECORD_COLUMNS = ["relateid", "kind", "dataset", "table", "sample_id",
                  "depth_top", "depth_bottom"]


class GeoData:
    """Boreholes, and the layers and samples inside them.

    ``data.df`` is a plain pandas table with one row per layer or sample.
    Every row has the ``relateid`` of its borehole, a ``kind`` ("layer" or
    "sample") and its depths.  A sample is taken at a single depth, so its
    ``depth_top`` and ``depth_bottom`` are the same.

    ``data.boreholes`` is a second table with one row per borehole.  It always
    holds exactly the boreholes that the layers and samples belong to.

    Filters return a new, smaller ``GeoData`` so they can be chained and saved::

        hole = data.filter_by_relateid("2000012")
        sand = data.filter_by_primary_lithology("SAND").filter_by_depth(0, 50)

    Where a filter takes names, give one, several, or a list of them.

    ``data.layers`` and ``data.samples`` give just the layers or just the samples.
    """

    def __init__(self, records, boreholes, settings=None):
        self.df = records
        self.boreholes = boreholes
        self._settings = dict(settings or {})

    # --- plumbing -------------------------------------------------------------------

    def _new(self, records, boreholes) -> "GeoData":
        return GeoData(records, boreholes, self._settings)

    def _keep_records(self, mask) -> "GeoData":
        """Only the layers and samples where ``mask`` is True, and their boreholes."""
        mask = pd.Series(mask, index=self.df.index).fillna(False).astype(bool)
        records = self.df[mask.to_numpy()]
        boreholes = self.boreholes[self.boreholes["relateid"].isin(records["relateid"])]
        return self._new(records, boreholes)

    def _keep_boreholes(self, mask) -> "GeoData":
        """Only the boreholes where ``mask`` is True, with all their layers and samples."""
        mask = pd.Series(mask, index=self.boreholes.index).fillna(False).astype(bool)
        boreholes = self.boreholes[mask.to_numpy()]
        records = self.df[self.df["relateid"].isin(boreholes["relateid"])]
        return self._new(records, boreholes)

    def _of_kind(self, kind) -> "GeoData":
        part = self._keep_records(self.df["kind"] == kind)
        if len(part.df):
            always = [c for c in RECORD_COLUMNS if c != "sample_id"]
            empty = [c for c in part.df.columns
                     if c not in always and part.df[c].isna().all()]
            part.df = part.df.drop(columns=empty)
        return part

    @staticmethod
    def _column(table, name, what) -> pd.Series:
        if name not in table.columns:
            raise ValueError(f"This data has no {what} column.")
        return table[name]

    def __len__(self):
        return len(self.df)

    def __repr__(self):
        return f"{self._headline()}\n{self.df!r}"

    def _repr_html_(self):
        return f"<p>{self._headline()}</p>{self.df._repr_html_()}"

    def _headline(self):
        layers = int((self.df["kind"] == LAYER).sum())
        samples = int((self.df["kind"] == SAMPLE).sum())
        return (f"GeoData: {layers:,} layers and {samples:,} samples "
                f"in {len(self.boreholes):,} boreholes")

    def head(self, n=5) -> pd.DataFrame:
        """The first ``n`` layers and samples."""
        return self.df.head(n)

    @property
    def layers(self) -> "GeoData":
        """Just the layers (depth intervals), without columns that only samples use."""
        return self._of_kind(LAYER)

    @property
    def samples(self) -> "GeoData":
        """Just the samples (single depths), without columns that only layers use."""
        return self._of_kind(SAMPLE)

    # --- filters on boreholes ---------------------------------------------------------

    def filter_by_relateid(self, *relateids) -> "GeoData":
        """Keep the given borehole(s), with all their layers and samples.

        Zeros at the front do not matter: "2000012" and "0002000012" are the same.
        """
        values = as_list(relateids)
        if not values:
            raise ValueError("Give at least one relateid to keep.")
        keys = self.boreholes["relateid"].astype("string").str.lstrip("0")
        wanted = [str(v).strip().lstrip("0") for v in values]
        available = set(keys.dropna())
        unknown = [str(v) for v, key in zip(values, wanted) if key not in available]
        if unknown:
            raise ValueError(f"No borehole with relateid {unknown} in this data.")
        return self._keep_boreholes(keys.isin(wanted))

    def filter_by_county(self, *counties) -> "GeoData":
        """Keep boreholes in the given county or counties."""
        column = self._column(self.boreholes, "county", "county")
        return self._keep_boreholes(_matches(column, "county", counties))

    def filter_by_area(self, east_min, east_max, north_min, north_max) -> "GeoData":
        """Keep boreholes inside a rectangle of UTM coordinates."""
        east = self._column(self.boreholes, "easting", "easting")
        north = self._column(self.boreholes, "northing", "northing")
        return self._keep_boreholes(east.between(east_min, east_max)
                                    & north.between(north_min, north_max))

    # --- filters on layers and samples ------------------------------------------------

    def filter_by_primary_lithology(self, *lithologies) -> "GeoData":
        """Keep layers and samples of the given primary lithology, e.g. "SAND"."""
        column = self._column(self.df, "primary_lithology", "primary lithology")
        return self._keep_records(_matches(column, "primary lithology", lithologies))

    def filter_by_sample_id(self, *sample_ids) -> "GeoData":
        """Keep samples with the given sample ID(s).  Layers have no IDs and are dropped."""
        column = self._column(self.df, "sample_id", "sample ID")
        return self._keep_records(_matches(column, "sample ID", sample_ids))

    def filter_by_dataset(self, *datasets) -> "GeoData":
        """Keep layers and samples that came from the given dataset(s), e.g. "cwi"."""
        return self._keep_records(_matches(self.df["dataset"], "dataset", datasets))

    def filter_by_depth(self, top=None, bottom=None) -> "GeoData":
        """Keep what lies between the depths ``top`` and ``bottom``.

        A layer is kept if any part of it is inside the range; a sample is
        kept if its depth is.  Leave one end out for "everything below 50"
        (``filter_by_depth(top=50)``) or "everything above 50"
        (``filter_by_depth(bottom=50)``).
        """
        layer_top = pd.to_numeric(self.df["depth_top"], errors="coerce")
        layer_bottom = pd.to_numeric(self.df["depth_bottom"], errors="coerce")
        layer_top, layer_bottom = layer_top.fillna(layer_bottom), layer_bottom.fillna(layer_top)
        mask = layer_top.notna()
        # A layer that only touches the range at its edge is not inside it, but
        # a sample sitting exactly on the edge is.
        if top is not None:
            mask &= (layer_bottom > top) | (layer_top >= top)
        if bottom is not None:
            mask &= (layer_top < bottom) | (layer_bottom <= bottom)
        return self._keep_records(mask)

    def filter_by(self, column, *values) -> "GeoData":
        """Keep rows where any column has one of the given values.

        For columns with no filter of their own.  ``data.list_columns()``
        shows every column name::

            data.filter_by("strat", "QBAA", "QWTA")
        """
        name = str(column).strip().lower()
        if name == "relateid":
            return self.filter_by_relateid(*values)
        if name in self.df.columns:
            return self._keep_records(_matches(self.df[name], name, values))
        if name in self.boreholes.columns:
            return self._keep_boreholes(_matches(self.boreholes[name], name, values))
        raise ValueError(f"This data has no column called '{column}'. "
                         "See data.list_columns() for the names.")

    # --- information and export -------------------------------------------------------

    def list_columns(self) -> pd.DataFrame:
        """Every column, which table it is in, and how many rows have a value."""
        rows = []
        for found_in, table in (("layers and samples (data.df)", self.df),
                                ("boreholes (data.boreholes)", self.boreholes)):
            for name in table.columns:
                rows.append({"column": name, "found_in": found_in,
                             "n_filled": int(table[name].notna().sum())})
        return pd.DataFrame(rows)

    def summary(self) -> None:
        """Print a plain-English report of what is in the data."""
        print(self._summary_text())

    def _summary_text(self) -> str:
        lines = [self._headline()]
        for key, values in self._settings.get("by", {}).items():
            lines.append(f"  loaded by {key}: {', '.join(map(str, values))}")
        counts = self.df.groupby(["dataset", "table", "kind"], sort=False).size()
        for (dataset, table, kind), count in counts.items():
            lines.append(f"  {dataset} {table}: {count:,} {kind}s")
        depths = pd.concat([pd.to_numeric(self.df[c], errors="coerce")
                            for c in ("depth_top", "depth_bottom")]).dropna()
        if len(depths):
            lines.append(f"  depths from {depths.min():g} to {depths.max():g}")
        return "\n".join(lines)

    def to_csv(self, path) -> Path:
        """Save the layers and samples as a CSV file."""
        path = Path(path)
        self.df.to_csv(path, index=False)
        return path

    def to_excel(self, path) -> Path:
        """Save to an Excel file: one sheet of layers and samples, one of boreholes."""
        path = Path(path)
        with pd.ExcelWriter(path) as writer:
            self.df.to_excel(writer, sheet_name="Layers and samples", index=False)
            self.boreholes.to_excel(writer, sheet_name="Boreholes", index=False)
        return path


def _matches(column, what, values) -> pd.Series:
    """True for each row of ``column`` holding one of ``values`` (upper/lower case ignored)."""
    values = as_list(values)
    if not values:
        raise ValueError(f"Give at least one {what} to keep.")
    if pd.api.types.is_numeric_dtype(column) and not pd.api.types.is_bool_dtype(column):
        return column.isin(pd.to_numeric(pd.Series(values), errors="coerce").dropna())
    lowered = column.astype("string").str.strip().str.lower()
    wanted = [str(v).strip().lower() for v in values]
    available = set(lowered.dropna())
    unknown = [str(v) for v, low in zip(values, wanted) if low not in available]
    if unknown:
        options = sorted(column.dropna().astype(str).unique())
        shown = ", ".join(options[:25]) + (", ..." if len(options) > 25 else "")
        raise ValueError(f"No {what} called {unknown}. Available: {shown}")
    return lowered.isin(wanted)
