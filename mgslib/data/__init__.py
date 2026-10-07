"""Borehole data from the MGS data server: load it, then filter it.

    from mgslib.data import load_data, INCLUDE_QUAT_DATA
    data = load_data(include=INCLUDE_QUAT_DATA, by={"county": "Ramsey"})
"""

from .client import set_server
from .geo_data import GeoData
from .loader import load_data
from .presets import INCLUDE_ALL, INCLUDE_CWI, INCLUDE_QDI, INCLUDE_QUAT_DATA

__all__ = ["load_data", "GeoData", "set_server",
           "INCLUDE_ALL", "INCLUDE_CWI", "INCLUDE_QDI", "INCLUDE_QUAT_DATA"]
