"""Borehole data from CWI and QDI: load it, then filter it.  The sources are only ever read.

    from mgslib.data import load_data, INCLUDE_QUAT_DATA
    data = load_data(include=INCLUDE_QUAT_DATA, by={"county": "Ramsey"})

See README.md in this folder.
"""

from .geo_data import GeoData
from .loader import load_data
from .presets import INCLUDE_ALL, INCLUDE_CWI, INCLUDE_QDI, INCLUDE_QUAT_DATA

__all__ = ["load_data", "GeoData",
           "INCLUDE_ALL", "INCLUDE_CWI", "INCLUDE_QDI", "INCLUDE_QUAT_DATA"]
