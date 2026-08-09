"""Deterministic settlement name generation.

Names are built from syllable pools chosen by a seeded RNG, so a given
world seed always produces the same names.
"""

import random

_SYLLABLES = [
    "ak",
    "bel",
    "cor",
    "dun",
    "el",
    "far",
    "gal",
    "hol",
    "ir",
    "jak",
    "kel",
    "lor",
    "mar",
    "niv",
    "or",
    "pel",
    "quor",
    "run",
    "sar",
    "thul",
    "var",
    "wyn",
    "zen",
    "br",
    "ka",
    "mi",
    "nu",
    "fa",
    "ty",
    "os",
]

_SUFFIXES = ["Vale", "Hill", "Reach", "Landing", "Ford", "Town", "Haven", "Peak"]


def settlement_name(rng: random.Random) -> str:
    """Generate a settlement name like "Marniv Vale" or "Kel Harbor"."""
    parts = "".join(rng.choice(_SYLLABLES) for _ in range(rng.randint(1, 2)))
    return parts.capitalize() + " " + rng.choice(_SUFFIXES)
