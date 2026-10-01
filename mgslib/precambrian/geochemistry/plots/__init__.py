"""Geochemical plots.  Each takes a GeochemData object and does the rest.

    from mgslib.precambrian.geochemistry.plots import TAS, Harker
    TAS(data)
    Harker(data, color_by="lithology")
"""

from .bivariate import (ASI, MALI, TAS, Al_Ti_Provenance, Fe_Index, Granite_Tectonic, Harker,
                        K_Rb_Provenance, Mafic_Oxides, Magnetic_Susceptibility,
                        Sediment_Recycling, Sediment_Tectonic, Shand_Index, Th_U_Weathering,
                        Ti_Zr_Provenance)
from .spider import Chondrite_REE, Primitive_Mantle_REE
from .ternary import (AFM_Ternary, Jensen_Ternary, Laurent_Granitoid_Ternary,
                      Laurent_Source_Ternary, Normative_Feldspar_Ternary, QAP_Ternary)

__all__ = [
    "Chondrite_REE", "Primitive_Mantle_REE", "Harker", "AFM_Ternary", "Jensen_Ternary",
    "Normative_Feldspar_Ternary", "QAP_Ternary", "Shand_Index", "MALI", "ASI", "Fe_Index", "TAS",
    "Granite_Tectonic", "Magnetic_Susceptibility", "Mafic_Oxides", "Laurent_Granitoid_Ternary",
    "Laurent_Source_Ternary", "Sediment_Tectonic", "Sediment_Recycling", "Th_U_Weathering",
    "Al_Ti_Provenance", "Ti_Zr_Provenance", "K_Rb_Provenance",
]
