"""Deterministic experience/skill system (docs/02 §11.3).

Settlements that survive destructive events (floods, droughts, plagues, war)
earn experience. Experience maps to a skill level (1-5) that scales
production and rebuild speed — the "they build back stronger" behavior. The
formula is a plain tier table so the behavior is deterministic, transparent,
and fully testable; a real ML model can be swapped in behind the same helpers
later (docs/01 §5 rule 2: deterministic where practical).
"""

TIERS = [
    (0, 1),
    (50, 2),
    (150, 3),
    (300, 4),
    (500, 5),
]

_DISASTER_BASE_EXP = 20
_DISASTER_EXP_PER_SEVERITY = 5


def skill_level(experience: int) -> int:
    """Map cumulative experience to a skill level (1-5, monotonic)."""
    level = TIERS[0][1]
    for threshold, tier in TIERS:
        if experience >= threshold:
            level = tier
    return level


def production_bonus(level: int) -> float:
    """Food/yield multiplier: +5% per level beyond the first, capped at +45%
    (level 10). The cap keeps world population bounded over very long runs."""
    return 1.0 + 0.05 * min(max(0, level - 1), 9)


def rebuild_speed(level: int) -> float:
    """Construction progress multiplier: +10% per level beyond the first,
    capped at +90% (level 10)."""
    return 1.0 + 0.10 * min(max(0, level - 1), 9)


def grant_survival_experience(severity: int) -> int:
    """Experience earned for surviving a disaster: more for worse disasters."""
    return _DISASTER_BASE_EXP + _DISASTER_EXP_PER_SEVERITY * max(0, severity - 1)
