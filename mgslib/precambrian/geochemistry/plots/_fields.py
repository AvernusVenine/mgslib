"""Published boundary lines for the classification diagrams.

Only boundaries whose coordinates or equations could be checked against a
source are here.  The pyrolite library supplies the fields for the TAS,
Jensen and QAP diagrams.
"""

from __future__ import annotations

import numpy as np

# --- AFM ------------------------------------------------------------------------
# Tholeiitic / calc-alkaline boundary of Irvine & Baragar (1971, fig. 2A), as
# (A, F, M) points tabulated by Rickwood (1989, Lithos 22, table 3).
AFM_IRVINE_BARAGAR = [
    (58.8, 36.2, 5.0), (47.6, 42.4, 10.0), (29.6, 52.6, 17.8), (25.4, 54.6, 20.0),
    (21.4, 54.6, 24.0), (19.4, 52.8, 27.8), (18.9, 51.1, 30.0), (16.6, 43.4, 40.0),
    (15.0, 35.0, 50.0),
]

# --- Frost granitoid classification ------------------------------------------------
# Ferroan / magnesian boundary for Fe* = FeOt/(FeOt+MgO): Frost & Frost (2008,
# J. Petrology 49), Fe* = 0.46 + 0.005 SiO2.
def fe_index_boundary(sio2):
    return 0.46 + 0.005 * np.asarray(sio2, dtype=float)


# MALI (Na2O + K2O - CaO) boundaries of Frost et al. (2001, J. Petrology 42).
# They cross MALI = 0 at 51, 56 and 61 wt% SiO2 (Peacock's alkali-lime index).
MALI_BOUNDARIES = {
    "alkalic / alkali-calcic": (-41.86, 1.112, -0.00572),
    "alkali-calcic / calc-alkalic": (-44.72, 1.094, -0.00527),
    "calc-alkalic / calcic": (-45.36, 1.0043, -0.00427),
}
MALI_FIELD_LABELS = ["alkalic", "alkali-calcic", "calc-alkalic", "calcic"]


def mali_boundary(coefficients, sio2):
    a, b, c = coefficients
    sio2 = np.asarray(sio2, dtype=float)
    return a + b * sio2 + c * sio2 ** 2


# --- Granite tectonic setting: Rb vs Y + Nb ------------------------------------------
# Pearce, Harris & Tindle (1984, J. Petrology 25).  Straight segments on
# log-log axes, as (Y+Nb, Rb) in ppm.
PEARCE_RB_YNB_LINES = [
    [(2, 80), (55, 300)],
    [(55, 300), (400, 2000)],
    [(55, 300), (51.5, 8)],
    [(51.5, 8), (50, 1)],
    [(51.5, 8), (2000, 400)],
]
PEARCE_RB_YNB_LABELS = {
    "syn-COLG": (8, 700), "WPG": (350, 200), "VAG": (8, 20), "ORG": (400, 6),
}


# --- Sedimentary provenance ------------------------------------------------------------
# Source-rock type from Al2O3/TiO2 (Hayashi et al. 1997, Geochim. Cosmochim. Acta 61):
# mafic 3-8, intermediate 8-21, felsic 21-70.
AL_TI_BANDS = {"Mafic": (3.0, 8.0), "Intermediate": (8.0, 21.0), "Felsic": (21.0, 70.0)}

# Source-rock type from TiO2/Zr, both as ppm (attributed to Hayashi et al. 1997):
# mafic above 200, intermediate 55-200, felsic below 55.
# NOT YET CHECKED AGAINST THE PAPER: these two values are from memory.
TI_ZR_RATIOS = {"mafic / intermediate": 200.0, "intermediate / felsic": 55.0}
TIO2_PERCENT_TO_PPM = 10_000.0

# Th/U of the upper continental crust (McLennan et al. 1993, GSA Special Paper 284).
TH_U_UPPER_CRUST = 3.8

# "Main trend" of K against Rb, K/Rb = 230 by weight (Shaw 1968), as drawn on the
# K2O-Rb diagram of Floyd & Leveridge (1987).
K_RB_MAIN_TREND = 230.0
K2O_PERCENT_TO_K_PPM = 8301.5


# --- Chemical sediments / iron formation -------------------------------------------------
# Sm/Yb against Y/Ho (plain ratios, not normalised) of Alexander et al. (2008, Geochim.
# Cosmochim. Acta 72, fig. 6b).  Digitised from the vector artwork of the published
# figure, calibrated on its log-scale tick marks (accurate to well under 1 %).
# Points are (Sm/Yb, Y/Ho).  The curve is two-component conservative mixing of
# shallow (<500 m) seawater (Alibo & Nozaki 1999) with >350 C vent fluid (Bau &
# Dulski 1999).
ALEXANDER_MIXING_LINE = [
    (0.61, 56.8), (0.727, 55.5), (0.844, 54.5), (0.956, 53.4), (1.07, 52.4), (1.17, 51.4),
    (1.27, 50.6), (1.37, 49.8), (1.47, 49.0), (1.56, 48.3), (1.64, 47.7), (2.41, 42.9),
    (2.98, 40.0), (3.44, 38.1), (3.79, 36.6), (4.1, 35.6), (4.35, 34.8), (4.58, 34.1),
    (4.77, 33.6), (4.92, 33.1), (5.83, 30.8), (6.22, 29.9), (6.47, 29.4), (6.6, 29.2),
    (6.73, 29.0), (6.81, 28.7), (6.9, 28.6),
]
ALEXANDER_MIXING_MARKS = {"1% hydrothermal fluid": (1.64, 47.7),
                          "5% hydrothermal fluid": (3.79, 36.6)}
ALEXANDER_FIELDS = {
    "Seawater": [
        (0.85, 56.6), (0.839, 58.2), (0.812, 59.8), (0.771, 61.2), (0.722, 62.4), (0.668, 63.2),
        (0.546, 63.2), (0.508, 62.2), (0.476, 61.0), (0.455, 59.6), (0.443, 58.0), (0.438, 56.2),
        (0.443, 54.5), (0.458, 53.0), (0.483, 51.8), (0.515, 51.0), (0.557, 50.4), (0.681, 50.4),
        (0.732, 51.2), (0.781, 52.2), (0.818, 53.4), (0.839, 54.9), (0.85, 56.6)],
    "Hydrogenetic\nFe-Mn crusts": [
        (1.74, 21.5), (1.72, 22.7), (1.65, 24.0), (1.57, 25.2), (1.46, 26.2), (1.34, 26.8),
        (1.12, 26.9), (1.03, 26.4), (0.956, 25.5), (0.901, 24.3), (0.867, 23.1), (0.85, 20.5),
        (0.872, 19.3), (0.913, 18.4), (0.974, 17.6), (1.05, 17.1), (1.15, 16.8), (1.31, 16.9),
        (1.43, 17.2), (1.54, 17.8), (1.63, 18.6), (1.7, 19.6), (1.74, 20.8), (1.74, 21.5)],
    "High-T\nhydrothermal fluids": [
        (9.25, 29.1), (9.07, 29.9), (8.78, 30.6), (8.28, 31.2), (7.76, 31.6), (7.18, 31.8),
        (6.14, 31.8), (5.68, 31.4), (5.36, 31.1), (5.08, 30.5), (4.92, 29.8), (4.86, 28.6),
        (4.96, 28.0), (5.15, 27.4), (5.43, 26.9), (5.79, 26.5), (6.26, 26.3), (7.61, 26.5),
        (8.18, 26.8), (8.67, 27.2), (9.02, 27.9), (9.25, 28.5), (9.25, 29.1)],
}
ALEXANDER_LABELS = {"Seawater": (0.33, 57.0), "Hydrogenetic\nFe-Mn crusts": (1.25, 14.0),
                    "High-T\nhydrothermal fluids": (7.0, 22.5)}
Y_HO_CHONDRITE = 28.0   # chondritic Y/Ho, marked on the Alexander et al. axis

# Eu/Eu* = 1 is no anomaly (Al2O3 against Eu/Eu*, after Lawrence et al. 2006).
EU_ANOMALY_NONE = 1.0

# Al2O3 against SiO2 (wt%) of Toth (1980) and Wonder et al. (1988, Econ. Geol. 83).
# NOT CHECKED AGAINST THE ORIGINAL: the 1988 paper was not available.  The lines
# are digitised from raster reproductions: an example figure supplied by MGS
# (example_data/Wonder_Diagram_Example.png; slopes 9.9, 2.9 and 2.0) and Yalcin &
# Kara (2026, Carpathian J. Earth Environ. Sci. 21, fig. 4a; slopes 10.0 and 1.97,
# no deep-sea sediment line).  All pass through the origin; round slopes are used:
#   SiO2 = 10 x Al2O3   hydrothermal (above) / hydrogenous and detrital input (below)
#   SiO2 =  3 x Al2O3   hydrogenous and detrital input / deep-sea sediment
#   SiO2 =  2 x Al2O3   deep-sea sediment / deep-sea pelagic sediment (below)
WONDER_SIO2_AL2O3_SLOPES = {"hydrothermal / hydrogenous": 10.0,
                            "hydrogenous / deep-sea sediment": 3.0,
                            "deep-sea sediment / pelagic sediment": 2.0}
WONDER_SIO2_AL2O3_LABELS = {"Hydrothermal": (3.0, 85), "Hydrogenous and\ndetrital input": (14.0, 72),
                            "Deep-sea sediment": (16.5, 41), "Deep-sea pelagic\nsediment": (16.0, 12)}


# --- Ternary fields ----------------------------------------------------------------
# All ternary points below are (top, left, right) and add up to 100.

# Normative feldspar classification of O'Connor (1965): top An, left Ab, right Or.
# Coordinates from the OConnorPlut template of GCDkit 6.3 (the version it uses
# with a CIPW norm).  Each line is (points, dashed).
FELDSPAR_LINES = [
    ([(0, 70, 30), (17.5, 52.5, 30)], False),
    ([(20, 60, 20), (44, 36, 20)], False),
    ([(16.25, 48.75, 35), (35.75, 29.25, 35)], True),
    ([(12.5, 37.5, 50), (27.5, 22.5, 50)], True),
    ([(25, 75, 0), (12.5, 37.5, 50)], False),
    ([(12.5, 37.5, 50), (2.5, 7.5, 90)], True),
    ([(2.5, 7.5, 90), (5.5, 4.5, 90)], True),
]
FELDSPAR_FIELDS = {
    "Trondhjemite": [(0, 100, 0), (0, 70, 30), (17.5, 52.5, 30), (25, 75, 0)],
    "Granite": [(0, 70, 30), (0, 0, 100), (17.5, 52.5, 30)],
    "Quartz\nmonzonite": [(16.25, 48.75, 35), (12.5, 37.5, 50), (27.5, 22.5, 50), (35.75, 29.25, 35)],
    "Granodiorite": [(20, 60, 20), (16.25, 48.75, 35), (35.75, 29.25, 35), (44, 36, 20)],
    "Tonalite": [(25, 75, 0), (20, 60, 20), (44, 36, 20), (55, 45, 0)],
}
FELDSPAR_LABELS = {
    "Trondhjemite": (9, 79, 12), "Granite": (6, 49, 45), "Quartz\nmonzonite": (24, 33, 43),
    "Granodiorite": (30, 43, 27), "Tonalite": (38, 53, 9),
}

# Granitoid source diagram of Laurent et al. (2014, Lithos 205):
# top 3 CaO, left Al2O3/(FeOt+MgO), right 5 K2O/Na2O.  Straight boundaries,
# coordinates from the LaurentSource template of GCDkit 6.3.
LAURENT_SOURCE_LINES = [
    [(35, 65, 0), (35, 25, 40)],
    [(0, 60, 40), (60, 0, 40)],
    [(35, 45, 20), (60, 20, 20), (100, 0, 0)],
]
LAURENT_SOURCE_FIELDS = {
    "Tonalites": [(0, 100, 0), (0, 60, 40), (35, 25, 40), (35, 65, 0)],
    "Metasediments": [(0, 60, 40), (0, 0, 100), (60, 0, 40)],
    "Low-K\nmafic rocks": [(35, 65, 0), (35, 45, 20), (60, 20, 20), (100, 0, 0)],
    "High-K\nmafic rocks": [(35, 45, 20), (35, 25, 40), (60, 0, 40), (100, 0, 0), (60, 20, 20)],
}
LAURENT_SOURCE_LABELS = {
    "Tonalites": (16, 64, 20), "Metasediments": (16, 22, 62),
    "Low-K\nmafic rocks": (52, 40, 8), "High-K\nmafic rocks": (50, 20, 30),
}

# Late-Archean granitoid classification of Laurent et al. (2014, Lithos 205):
# top Na2O/K2O, left 2 A/CNK, right 2 FMSB.  Read from the paper's own figure,
# where the boundaries are straight lines that fall on round values on all
# three panels and the inset key:
#   sanukitoids                      2 FMSB above 30 %
#   TTG                              2 FMSB below 30 %, Na2O/K2O above 40 %
#   biotite and two-mica granites    2 FMSB below 30 %, Na2O/K2O below 40 %
#   hybrid granitoids (dashed box)   Na2O/K2O 20-50 %, 2 FMSB 15-40 %
LAURENT_GRANITOID_LINES = [
    ([(0, 70, 30), (70, 0, 30)], False),
    ([(40, 60, 0), (40, 30, 30)], False),
    ([(50, 35, 15), (50, 10, 40), (20, 40, 40), (20, 65, 15), (50, 35, 15)], True),
]
LAURENT_GRANITOID_FIELDS = {
    "TTG": [(100, 0, 0), (40, 60, 0), (40, 30, 30), (70, 0, 30)],
    "Biotite and\ntwo-mica granites": [(40, 60, 0), (0, 100, 0), (0, 70, 30), (40, 30, 30)],
    "Sanukitoids": [(70, 0, 30), (0, 70, 30), (0, 0, 100)],
    "Hybrid": [(50, 35, 15), (50, 10, 40), (20, 40, 40), (20, 65, 15)],
}
LAURENT_GRANITOID_LABELS = {
    "TTG": (68, 22, 10), "Biotite and\ntwo-mica granites": (9, 79, 12),
    "Sanukitoids": (12, 20, 68), "Hybrid": (33, 32, 35),
}


def _xy(point):
    """Ternary (top, left, right) to flat x, y."""
    top, left, right = point
    total = top + left + right
    return (right + top / 2.0) / total, top / total


def fields_containing(fields: dict, top, left, right) -> list:
    """Names of the fields a composition falls in (there may be none, or
    more than one where fields overlap)."""
    x, y = _xy((top, left, right))
    found = []
    for name, outline in fields.items():
        inside = False
        corners = [_xy(p) for p in outline]
        for (x1, y1), (x2, y2) in zip(corners, corners[1:] + corners[:1]):
            if (y1 > y) != (y2 > y) and x < x1 + (y - y1) * (x2 - x1) / (y2 - y1):
                inside = not inside
        if inside:
            found.append(name.replace("\n", " "))
    return found
