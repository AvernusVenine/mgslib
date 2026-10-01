"""Precambrian geochemistry: load, clean, query and (later) plot.

    from mgslib.precambrian.geochemistry import load_geochem
    data = load_geochem("my_file.xlsx")
"""

import matplotlib.colors as _colors

# pyrolite names matplotlib.colors.Norm in its type hints, but that class only
# exists from matplotlib 3.11.  On older matplotlib (e.g. Google Colab) importing
# pyrolite fails without this stand-in.  It is only ever used as a type hint.
if not hasattr(_colors, "Norm"):
    _colors.Norm = _colors.Normalize

from .data import Analyte, GeochemData, load_geochem  # noqa: E402

__all__ = ["load_geochem", "GeochemData", "Analyte"]
