"""Ready-made choices for ``load_data(include=...)``.

Each one is an ordinary dictionary of ``{dataset: [tables]}``, so
``load_data(include=INCLUDE_CWI, ...)`` and
``load_data(include={"cwi": ["c5ix", "c5st"]}, ...)`` are the same thing.
"""

from .schema import datasets

# County Well Index: the wells and their stratigraphy layers.
INCLUDE_CWI = {"cwi": ["c5ix", "c5st"]}

# Quaternary Data Index: the samples.
INCLUDE_QDI = {"qdi": ["qdi"]}

# Everything used for Quaternary work: CWI wells and layers, plus QDI samples.
INCLUDE_QUAT_DATA = {"cwi": ["c5st", "c5ix"], "qdi": ["qdi"]}

# Every table of every dataset.
INCLUDE_ALL = datasets()
