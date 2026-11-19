# MGSlib

In-house Python tools for the Minnesota Geological Survey.

## Installing

```
pip install git+https://github.com/AvernusVenine/mgslib.git
```

To update to the newest version later, add `--upgrade`:

```
pip install --upgrade git+https://github.com/AvernusVenine/mgslib.git
```

This needs Git installed. Without it, download the code from
[github.com/AvernusVenine/mgslib](https://github.com/AvernusVenine/mgslib) (Code → Download ZIP),
unzip it, and run `pip install path\to\mgslib`.

## Sections

Each part of MGSlib has its own guide, kept in a `README.md` next to its code:

| Section | What it does | Guide |
|---|---|---|
| `mgslib.precambrian.geochemistry` | Load, clean, filter and plot Precambrian geochemistry tables | [Precambrian geochemistry](mgslib/precambrian/geochemistry/README.md) |
| `mgslib.data` | Load and filter borehole data from CWI and QDI (read only) | [Borehole data](mgslib/data/README.md) |

When a new section is added, it gets a `README.md` in its own package folder and a row in
this table.
