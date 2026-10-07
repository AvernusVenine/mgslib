"""Small helpers shared by every part of mgslib."""

from __future__ import annotations


def as_list(values) -> list:
    """Flatten filter arguments, so ``f("a", "b")`` and ``f(["a", "b"])`` mean the same."""
    flat = []
    for value in values:
        if isinstance(value, (str, bytes)) or not hasattr(value, "__iter__"):
            flat.append(value)
        else:
            flat.extend(value)
    return flat
