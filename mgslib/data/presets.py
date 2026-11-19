"""Ready-made choices for ``load_data(include=...)``.

Each one is an ordinary dictionary of ``{dataset: [tables]}``, so
``load_data(include=INCLUDE_CWI, ...)`` and
``load_data(include={"cwi": ["c4ix", "c4st"]}, ...)`` are the same thing.
"""

from .schema import datasets

# County Well Index: the wells and their stratigraphy layers.
INCLUDE_CWI = {"cwi": ["c4ix", "c4st"]}

# Quaternary Data Index: the texture and grain-count samples.
INCLUDE_QDI = {"qdi": ["texture"]}

# Everything used for Quaternary work: CWI wells and layers, plus QDI samples.
INCLUDE_QUAT_DATA = {"cwi": ["c4ix", "c4st"], "qdi": ["texture"]}

# Every table of every dataset.
INCLUDE_ALL = datasets()
