"""Unit and oxide conversion factors.

Units are stored as short codes: ``"pct"`` (weight percent), ``"ppm"`` and
``"ppb"``.  A "form" is what the number measures: an element symbol
(``"Ti"``) or an oxide formula (``"TiO2"``).
"""

from __future__ import annotations

import re

from periodictable import elements

ELEMENT_SYMBOLS = frozenset(el.symbol for el in elements if el.number > 0)

# How many ppm one unit of each code is worth.
UNIT_TO_PPM = {"pct": 1.0e4, "ppm": 1.0, "ppb": 1.0e-3}

UNIT_LABELS = {"pct": "wt%", "ppm": "ppm", "ppb": "ppb"}

# Text found in column headers -> unit code.
UNIT_ALIASES = {
    "%": "pct",
    "wt%": "pct",
    "wt.%": "pct",
    "wt %": "pct",
    "pct": "pct",
    "percent": "pct",
    "ppm": "ppm",
    "g/t": "ppm",
    "ug/g": "ppm",
    "mg/kg": "ppm",
    "ppb": "ppb",
}

# The oxide an element is conventionally reported as.  Used when the data
# itself has no oxide column for that element.
STANDARD_OXIDES = {
    "Si": "SiO2", "Ti": "TiO2", "Al": "Al2O3", "Fe": "Fe2O3", "Mn": "MnO",
    "Mg": "MgO", "Ca": "CaO", "Na": "Na2O", "K": "K2O", "P": "P2O5",
    "Cr": "Cr2O3", "Ba": "BaO", "Sr": "SrO", "V": "V2O5", "Ni": "NiO",
    "Zr": "ZrO2", "S": "SO3", "C": "CO2", "H": "H2O", "Rb": "Rb2O",
    "Cs": "Cs2O", "Li": "Li2O", "Zn": "ZnO", "Cu": "CuO", "Co": "CoO",
    "Nb": "Nb2O5", "Ta": "Ta2O5", "U": "U3O8", "Th": "ThO2", "Y": "Y2O3",
    "La": "La2O3", "Ce": "CeO2", "Hf": "HfO2", "Sc": "Sc2O3", "Be": "BeO",
    "B": "B2O3", "W": "WO3", "Sn": "SnO2", "Mo": "MoO3", "Pb": "PbO",
    "Ga": "Ga2O3",
}

_OXYGEN_MASS = elements.symbol("O").mass
_OXIDE_PATTERN = re.compile(r"^([A-Z][a-z]?)(\d*)O(\d*)$")


def parse_oxide(formula: str):
    """Split a simple oxide formula into (element, n_element, n_oxygen).

    Returns None if the text is not a simple oxide such as ``"Al2O3"``.
    """
    match = _OXIDE_PATTERN.match(formula)
    if not match:
        return None
    element, n_element, n_oxygen = match.groups()
    if element not in ELEMENT_SYMBOLS or element == "O":
        return None
    return element, int(n_element or 1), int(n_oxygen or 1)


def element_of(form: str) -> str:
    """The element a form refers to: ``"TiO2"`` -> ``"Ti"``, ``"Ti"`` -> ``"Ti"``."""
    if form in ELEMENT_SYMBOLS:
        return form
    parsed = parse_oxide(form)
    if parsed is None:
        raise ValueError(f"'{form}' is not an element or a simple oxide.")
    return parsed[0]


def oxide_factor(formula: str) -> float:
    """Multiply an element weight by this to get the weight of its oxide."""
    parsed = parse_oxide(formula)
    if parsed is None:
        raise ValueError(f"'{formula}' is not a simple oxide.")
    element, n_element, n_oxygen = parsed
    element_mass = elements.symbol(element).mass * n_element
    return (element_mass + _OXYGEN_MASS * n_oxygen) / element_mass


def form_factor(from_form: str, to_form: str) -> float:
    """Multiply a value reported as ``from_form`` by this to express it as ``to_form``.

    Both forms must refer to the same element, e.g. ``"Ti"`` -> ``"TiO2"`` or
    ``"Fe2O3"`` -> ``"FeO"``.
    """
    if from_form == to_form:
        return 1.0
    if element_of(from_form) != element_of(to_form):
        raise ValueError(f"Cannot convert {from_form} to {to_form}: different elements.")
    to_element = 1.0 if from_form in ELEMENT_SYMBOLS else 1.0 / oxide_factor(from_form)
    from_element = 1.0 if to_form in ELEMENT_SYMBOLS else oxide_factor(to_form)
    return to_element * from_element


def unit_factor(from_unit: str, to_unit: str) -> float:
    """Multiply a value in ``from_unit`` by this to express it in ``to_unit``."""
    return UNIT_TO_PPM[from_unit] / UNIT_TO_PPM[to_unit]
