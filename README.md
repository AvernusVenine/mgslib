# MGSlib

In-house Python tools for the Minnesota Geological Survey. The first module loads and cleans
Precambrian geochemistry tables so they are ready to query and plot.

## Install

From the project folder:

```
pip install -e .
```

## Quick start

```python
from mgslib.precambrian.geochemistry import load_geochem

data = load_geochem("data.xlsx")
data.summary()
```

`load_geochem` reads an Excel or CSV file, stacks every sheet into one table and cleans it.
`data.summary()` prints what it found. `data.df` is the plain table if you want to look at it
directly.

## What the cleaning does

| Problem | What happens |
|---|---|
| Several sheets | Stacked into one table; `source_sheet` and `source_row` say where each row came from |
| Stray spaces, line breaks, odd characters, blank cells | Tidied; blanks become true nulls |
| Numbers typed badly (`1857 .00`) | Repaired if possible, otherwise set to null and logged |
| Below detection (`<0.05`) | Replaced with half the limit; the limit and the `<` are remembered |
| Above the upper limit (`>25`) | Replaced with 1.2 times the limit (30); the limit and the `>` are remembered |
| `0`, `NR`, `-9000` | Set to null |
| Depth ranges (`135-140`) | Midpoint goes in `depth_ft` (137.5); the ends are kept in `depth_from_ft` and `depth_to_ft` |
| Duplicates | Flagged in `flag_duplicate`; nothing is removed |
| Bad coordinates or depths | Flagged in `flag_xyz`, with the reason in `xyz_issue` |
| Unit problems | Flagged in `flag_units`, with the reason in `unit_issue`; nothing is converted |

Options, if you need something different:

```python
data = load_geochem("file.xlsx", sheets="Sheet1")           # just one sheet
data = load_geochem("file.xlsx", below_detection="limit")   # or "sqrt2", "null"
data = load_geochem("file.xlsx", zeros_are_missing=False)
```

## Filtering

Every filter gives back a new, separate table and leaves the one you filtered untouched. Save
the results under their own names and keep working with all of them:

```python
data = load_geochem("data.xlsx")

sediments = data.filter_by_rock_type("Sedimentary")
iron_formation = sediments.filter_by_rock_name("iron formation")

len(data)             # still every row
len(sediments)        # just the sedimentary rocks
iron_formation["Fe2O3t"].wt_percent()
```

The filters:

```python
data.filter_by_rock_type("Sedimentary")
data.filter_by_reference("Smith 2020")
data.filter_by_unit_name("Virginia Formation")
data.filter_by_rock_name("iron formation")       # rock name contains these words
data.filter_by_hole("DH-01")
data.filter_by_depth(100, 500)
data.filter_by_area(420000, 430000, 5140000, 5160000)

data.filter_above("SiO2", 50)
data.filter_below("Cu", 100)
data.filter_between("MgO", 2, 8)
data.filter_above("Ti", 5000, unit="ppm")        # Ti is stored in wt%; compare in ppm

sediments = (data.remove_duplicates()
                 .only_primary_samples()
                 .filter_by_rock_type("Sedimentary")
                 .filter_above("SiO2", 50))
```

## Getting an analyte in any unit

Values stay in the unit they came in. Ask for another unit and it is calculated on the spot:

```python
data["Ti"].ppm()                # Ti in ppm
data["Ti"].ppb()                # Ti in ppb
data["Ti"].wt_percent()         # Ti in wt%
data["Ti"].oxide_wt_percent()   # as TiO2 wt%
data["Ti"].unit                 # "wt%" - the unit it was stored in
```

`.ppm()`, `.ppb()` and `.wt_percent()` always give you the thing you named, so
`data["TiO2"].wt_percent()` is TiO2 wt% and `data["Ti"].wt_percent()` is Ti wt%.

If a sample has Ti but no TiO2 (or the other way round), the missing one is worked out from the
other. `data["Ti"].source()` shows which column each value came from.

Use these directly in a plot:

```python
import matplotlib.pyplot as plt

plt.scatter(data["Zr"].ppm(), data["Ti"].ppm())
```

### Iron

Iron can be asked for in any form, whichever iron columns a sample has:

```python
data["FeOt"].wt_percent()       # total iron as FeO
data["Fe2O3t"].wt_percent()     # total iron as Fe2O3
data["Fe"].wt_percent()         # total iron as the element
data["FeO"].wt_percent()        # ferrous iron only
data["Fe2O3"].wt_percent()      # ferric iron only
```

Total iron is worked out row by row: FeO + Fe2O3 if both were measured; otherwise a total-iron
column; otherwise Fe2O3 on its own (taken as total); otherwise Fe; otherwise FeO on its own
(taken as total). `data["FeO"]` and `data["Fe2O3"]` only have values where both were measured,
because a total cannot be split without assuming an oxidation ratio.

## Detection limits

```python
data.detection_limits()                 # every analyte: its limits and how many values were below/above
data.detection_limits("Te")             # one analyte, by sheet and lab
data.elements_below_detection()         # which analytes have values below detection
data.elements_above_upper_limit()

data.filter_below_detection("Te")       # rows where Te was below detection
data.filter_above_upper_limit("Mn")     # rows where Mn was over the upper limit
data.filter_measured("Te", "Au")        # rows with a real measurement for both

data["Te"].detection_limit              # [0.05]
data["Te"].is_below_detection()         # True/False for each row
```

To keep only the samples that are accurate enough for an analyte, use
`filter_by_detection_limit`. It keeps a sample if the analyte was measured above detection, or
if it was below detection but the lab's detection limit was the number you give or smaller:

```python
data.filter_by_detection_limit("Ag", 1)                 # measured, or below a limit of 1 ppm or better
data.filter_by_detection_limit("Ag")                    # measured above detection only
data.filter_by_detection_limit("Ti", 100, unit="ppm")   # limit given in ppm rather than the stored wt%
```

Samples with no value for that analyte are dropped.

A name such as `"Fe"` or `"Ti"` draws on every column for that element. To ask about one
column only, use its full name from `data.list_columns()`, for example
`data.filter_above_upper_limit("Fe_pct")` for the samples where the Fe (%) column read `>25`.

## Looking at what was flagged

```python
data.show_duplicates()
data.show_xyz_errors()
data.show_unit_conflicts()
data.show_issues()                      # the full log; data.show_issues("formatting") narrows it

data.remove_duplicates()                # keep one copy of each duplicated sample
data.remove_flagged("xyz")              # drop rows with a location problem
data.only_flagged("units")              # look at only the rows with a unit problem
```

`remove_duplicates()` keeps the copy that still has the lab's `<` and `>` values, and fills in
its blank descriptive fields (rock type, reference, ...) from the copies it removes.

## Other useful things

```python
data.list_analytes()            # every name that works in data[...]
data.list_columns()             # every column, its original header and its unit
data.select("SiO2", "Ti", "Zr") # descriptive columns plus just these analytes
data.to_excel("cleaned.xlsx")   # the table, the detection-limit record and the issue log
data.to_csv("cleaned.csv")
```

## Plots

Every plot takes a data object and works out the rest: it finds the analytes, converts the
units, calculates any ratios or norms, and draws the diagram. Filter first, then plot.

```python
from mgslib.precambrian.geochemistry.plots import TAS, Harker, Chondrite_REE

data = load_geochem("data.xlsx").remove_duplicates()
granites = data.filter_by_lithology("Felsic Intrusive")

TAS(granites)
Harker(granites, color_by="unit_name")
Chondrite_REE(granites, save="granite_ree.png")
```

| Plot | What it shows | Fields drawn |
|---|---|---|
| `Chondrite_REE` | Chondrite-normalised REE, one line per sample | none |
| `Primitive_Mantle_REE` | Primitive-mantle-normalised REE, one line per sample (Sun & McDonough 1989 by default) | none |
| `Harker` | Grid of panels against SiO2 (or any X you choose) | none |
| `TAS` | Na2O + K2O against SiO2, volatile-free | Le Bas et al. 1986; `rock_type="plutonic"` for Middlemost 1994 |
| `AFM_Ternary` | Na2O + K2O, FeOt, MgO | Irvine & Baragar 1971 |
| `Jensen_Ternary` | Al, Fe(total) + Ti, Mg as cation % | Jensen 1976 |
| `Normative_Feldspar_Ternary` | An, Ab, Or from the CIPW norm | tonalite, trondhjemite, granodiorite, quartz monzonite, granite (O'Connor 1965) |
| `QAP_Ternary` | Modal Q, A, P; from the CIPW norm if the file has no modal columns | Streckeisen 1974 |
| `Shand_Index` | A/NK against A/CNK (molar) | metaluminous, peraluminous, peralkaline |
| `MALI` | Na2O + K2O - CaO against SiO2 | Frost et al. 2001 |
| `ASI` | Aluminium saturation index against SiO2 | line at 1 |
| `Fe_Index` | FeOt / (FeOt + MgO) against SiO2 | ferroan / magnesian, Frost & Frost 2008 |
| `Granite_Tectonic` | Rb against Y + Nb | Pearce et al. 1984 |
| `Magnetic_Susceptibility` | Magnetic susceptibility against SiO2 | none |
| `Mafic_Oxides` | FeOt + MgO + MnO + TiO2 against SiO2 | none |
| `Laurent_Granitoid_Ternary` | Na2O/K2O, 2 x A/CNK, 2 x FMSB (Laurent et al. 2014) | TTG, sanukitoids, biotite and two-mica granites, and the dashed hybrid box |
| `Laurent_Source_Ternary` | 3 x CaO, Al2O3/(FeOt+MgO), 5 x K2O/Na2O (Laurent et al. 2014) | tonalite, metasediment, low-K mafic and high-K mafic sources |
| `Sediment_Tectonic` | K2O/Na2O against SiO2 (Roser & Korsch 1986) | none (boundaries could not be sourced reliably) |
| `Sediment_Recycling` | Th/Sc against Zr/Sc (McLennan et al. 1993) | none |
| `Th_U_Weathering` | Th/U against Th (McLennan et al. 1993) | upper-crust line at Th/U = 3.8 |
| `Al_Ti_Provenance` | Al2O3/TiO2 against Al2O3 (Hayashi et al. 1997) | mafic 3-8, intermediate 8-21, felsic 21-70 |
| `Ti_Zr_Provenance` | TiO2 against Zr (Hayashi et al. 1997) | TiO2/Zr = 200 and 55 (values not yet checked against the paper) |
| `K_Rb_Provenance` | Rb against K2O (Floyd & Leveridge 1987) | K/Rb = 230 trend line only |

Options that work on every plot:

```python
TAS(data, color_by="lithology")      # colour by any descriptive column, with a legend
TAS(data, title="My granites")
TAS(data, save="tas.png")            # also write the figure to a file
TAS(data, show_fields=False)         # points only, no classification fields
TAS(data, show=False)                # do not open a window (useful with save=)
```

Things to know:

- A sample is left off a plot if it is missing anything that plot needs. The corner of each
  figure says how many were plotted, for example `n = 412 of 530 samples`.
- With `color_by`, a group keeps the same colour on every plot made from the same data. If
  there are more than eight groups, the smallest are combined as "Other".
- If the data still has duplicate rows, the plot prints a reminder to use
  `data.remove_duplicates()`.
- Values the lab reported as below detection are plotted at the value they were given
  during cleaning (half the detection limit by default).

Choosing what goes on the Harker diagrams:

```python
Harker(data)                                          # the 14 default panels against SiO2
Harker(data, x="MgO", y=["Ni", "Cr", "Na2O+K2O", "La/Yb", "Mg#"])
```

Each entry can be an analyte, a sum (`"Na2O+K2O"`), a ratio (`"La/Yb"`) or one of `"Mg#"`,
`"Fe#"`, `"ASI"`, `"MALI"`, `"A/CNK"`, `"A/NK"`. Oxides are plotted in wt% and elements in ppm.

To build your own multi-panel figure, pass each plot an axes:

```python
import matplotlib.pyplot as plt

figure, (left, right) = plt.subplots(1, 2, figsize=(12, 5))
MALI(data, ax=left)
Fe_Index(data, ax=right)
plt.show()
```