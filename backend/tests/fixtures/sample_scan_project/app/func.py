"""Risky construct used by the static-analysis scanner fixture."""


def compute(expr: str):
    code = eval(expr)
    return code
