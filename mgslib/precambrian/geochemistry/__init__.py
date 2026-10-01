"""Precambrian geochemistry: load, clean, query and (later) plot.

    from mgslib.precambrian.geochemistry import load_geochem
    data = load_geochem("my_file.xlsx")
"""

from .data import Analyte, GeochemData, load_geochem

__all__ = ["load_geochem", "GeochemData", "Analyte"]
