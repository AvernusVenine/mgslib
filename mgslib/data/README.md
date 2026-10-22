# Borehole data

`mgslib.data` loads borehole data from the County Well Index (CWI) and the Quaternary Data
Index (QDI), and lets you filter it in plain English.

## Where the data comes from

| Dataset | Location |
|---|---|
| CWI | `T:\db_prod\cwi\data\cwidata.mdb` |
| QDI samples | `L:\gdrs\data\pub\edu_umn_mngs\geos_quaternary_data_index\Texture Data.lyr` |
| QDI boreholes | `L:\gdrs\data\pub\edu_umn_mngs\geos_quaternary_data_index\QDI Locations.lyr` |

Both are **only ever read**. mgslib never writes to them, saves them or changes them in any
way. What you load is a copy in your own Python session; filtering it or saving it to a file
leaves the sources untouched.

What you need:

- the `T:` drive connected (for CWI) and the `L:` drive connected (for QDI)
- ArcGIS Pro installed, for QDI. mgslib reads the QDI layers with ArcGIS Pro's Python in the
  background; you keep using your usual Python.
- the 64-bit Microsoft Access driver, for CWI (installed on MGS machines)

## Quick start

```python
from mgslib.data import load_data, INCLUDE_QUAT_DATA

data = load_data(include=INCLUDE_QUAT_DATA, by={"county": "Ramsey"})
data.summary()
```

`include` is one of these ready-made choices:

| Name | What it loads |
|---|---|
| `INCLUDE_QUAT_DATA` | CWI wells and stratigraphy layers, plus QDI samples |
| `INCLUDE_CWI` | CWI wells (`c4ix`) and stratigraphy layers (`c4st`) |
| `INCLUDE_QDI` | QDI texture and grain-count samples, with their boreholes |
| `INCLUDE_ALL` | Every table mgslib knows, including how each CWI well was built (`c4c1`) |

Each is only a short name for a dictionary of datasets and tables, so you can also write your
own: `include={"cwi": ["c4ix", "c4st", "c4c1"], "qdi": ["texture"]}`.

`by` says which part of the data to load. Give a county by name or by its CWI code, and several
values as a list:

```python
load_data(INCLUDE_CWI, by={"county": "Ramsey"})
load_data(INCLUDE_CWI, by={"county": ["Ramsey", "Dakota"]})
load_data(INCLUDE_QUAT_DATA, by={"relateid": ["0000206747", "2000012"]})
```

### Speed

- QDI is read through ArcGIS Pro, which takes a minute or two. It is read once per Python
  session and then kept, so later loads are quick. Use `load_data(..., refresh=True)` to read
  it again and pick up changes made since.
- CWI holds about 600,000 wells and 2.8 million layers. Leaving out `by` loads all of them,
  which takes a few minutes; loading by county takes well under a minute.

## What you get back

Boreholes contain layers (CWI: a top and a bottom depth) and samples (QDI: a single depth).
The data comes back as two tables that stay in step:

- `data.df` has one row per layer or sample. Every row has the `relateid` of its borehole, a
  `kind` (`"layer"` or `"sample"`) and `depth_top` / `depth_bottom`. For a sample the two
  depths are the same.
- `data.boreholes` has one row per borehole, and always holds exactly the boreholes that the
  layers and samples in `data.df` belong to. It has the location (`easting`, `northing`, UTM
  zone 15N), `elevation`, `county` and `county_code`.

`data.layers` and `data.samples` give just the layers or just the samples.

Some things to know:

- Depths and elevations are in feet.
- A few QDI samples record their depth unit as metres. They are left as they are, and
  `data.summary()` says how many there are.
- A few boreholes have no county recorded. They are left out when you load or filter by
  county; `data.summary()` says how many there are.
- About 500 QDI samples have no `relateid`, so they belong to no borehole. They are kept in
  `data.df`, and are dropped by any filter on boreholes.
- Depths are shown exactly as stored, so placeholders such as `-99` are still there. Use
  `filter_by_depth` to leave them out.
- Relateids are written with 10 characters, so `"2000012"` and `"0002000012"` are the same
  borehole.

## Filtering

Every filter gives back a new, separate object and leaves the original untouched:

```python
hole = data.filter_by_relateid("2000012")      # one borehole, with all its layers and samples
hole.layers
hole.samples
hole.boreholes

sand = data.filter_by_primary_lithology("SAND")   # every sand layer, in any borehole
sand.boreholes                                    # the boreholes those layers are in
shallow_sand = sand.filter_by_depth(0, 50)
```

The filters:

```python
data.filter_by_relateid("2000012")             # zeros at the front do not matter
data.filter_by_county("Ramsey")                # or the code, "62"
data.filter_by_area(480000, 500000, 4970000, 4990000)

data.filter_by_strat("QBAA", "QWTA")           # CWI strat or QDI stratunit
data.filter_by_primary_lithology("SAND", "GRAVEL")
data.filter_by_depth(0, 50)                    # layers partly inside the range are kept
data.filter_by_depth(top=100)                  # everything below 100
data.filter_by_sample_id("S1")
data.filter_by_dataset("qdi")

data.filter_by("deposittype", "T")             # any other column, by name
data.list_columns()                            # every column name
```

Filtering by something about a borehole (relateid, county, area) keeps those boreholes with
everything in them. Filtering by something about a layer or sample (strat, lithology, depth)
keeps only the matching layers and samples; each still carries its `relateid`.

## Saving

```python
data.to_excel("ramsey.xlsx")    # one sheet of layers and samples, one of boreholes
data.to_csv("ramsey.csv")       # the layers and samples
```
