"""Normalised multi-element (spider) diagrams."""

from __future__ import annotations

import numpy as np
import pandas as pd

from .. import chemistry as chem
from ._figure import GRID, INK_SECONDARY, NothingToPlot, finish, groups, new_axes


def _ree_pattern(data, reference, citation, name, color_by, title, ax, save, show):
    """REE divided by a reference composition, one line per sample."""
    measured = pd.DataFrame({element: chem.trace(data, element) for element in chem.REE})
    normalised = (measured / reference).where(lambda t: t > 0)
    normalised = normalised[normalised.notna().sum(axis=1) >= 3]
    if normalised.empty:
        raise NothingToPlot("Nothing to plot for the REE diagram: no sample has at least three "
                            "rare-earth elements.")

    ax, created = new_axes(ax, figsize=(8.0, 5.5), legend=color_by is not None)
    positions = np.arange(len(chem.REE))
    width = 0.6 if len(normalised) > 60 else 1.2
    for label, colour, rows in groups(data, normalised.index, color_by):
        for number, (_, values) in enumerate(normalised.loc[rows].iterrows()):
            present = values.notna().to_numpy()
            ax.plot(positions[present], values.to_numpy()[present], color=colour, linewidth=width,
                    alpha=0.7, label=label if number == 0 else None, zorder=3)
    ax.set_yscale("log")
    ax.set_xticks(positions, chem.REE)
    ax.set_xlim(-0.4, len(chem.REE) - 0.6)
    ax.set_ylabel(f"Sample / {name}", color=INK_SECONDARY)
    ax.grid(True, which="minor", axis="y", color=GRID, linewidth=0.3)
    heading = f"{name[0].upper()}{name[1:]}-normalised REE ({citation})"
    return finish(ax, data, len(normalised), title or heading, color_by, created, save, show)


def Chondrite_REE(data, color_by=None, title=None, ax=None, save=None, show=True,
                  reference="MS95"):
    """Chondrite-normalised rare-earth element diagram: one line per sample.

    reference : the chondrite values to divide by - "MS95" (McDonough & Sun
        1995, the default), "SM89" (Sun & McDonough 1989) or "PON" (Palme &
        O'Neill 2014).

    Samples need at least three REE to be drawn.  Where an element was not
    analysed the line runs straight between its neighbours.
    """
    values, citation = chem.reference_values(chem.CHONDRITES, reference, "chondrite")
    return _ree_pattern(data, values, citation, "chondrite", color_by, title, ax, save, show)


def Primitive_Mantle_REE(data, color_by=None, title=None, ax=None, save=None, show=True,
                         reference="SM89"):
    """Primitive-mantle-normalised rare-earth element diagram: one line per sample.

    reference : the primitive-mantle values to divide by - "SM89" (Sun &
        McDonough 1989, the default), "MS95" (McDonough & Sun 1995) or "PON"
        (Palme & O'Neill 2014).

    Samples need at least three REE to be drawn.  Where an element was not
    analysed the line runs straight between its neighbours.
    """
    values, citation = chem.reference_values(chem.PRIMITIVE_MANTLES, reference, "primitive mantle")
    return _ree_pattern(data, values, citation, "primitive mantle", color_by, title, ax, save, show)
