"""Default smoke tester — applies to any launchable app without a custom
tester (docs/tier2_plan.md Phase B).

Deterministic contract: launch the app's startup command, let it settle,
verify no crash signatures appeared in the run's log lines, and capture a
screenshot. Status: passed, or investigate (launch failure) / failed
(crash signature in the log).
"""

from app.testers import Tester
from app.testers._helpers import (
    TesterAssertionError,
    TesterContext,
    TesterEnvError,
)

CRASH_PATTERNS = ("Traceback", "FATAL ERROR", "Cannot find module")


def run(ctx: TesterContext) -> None:
    commands = ctx.project.stack.get("commands") if ctx.project.stack else None
    startup = (commands or {}).get("startup") or ""
    if not startup:
        raise TesterEnvError("No startup command — not launchable")
    ctx.launch(startup)
    ctx.wait(20)
    ctx.screenshot("app window after launch")
    for pattern in CRASH_PATTERNS:
        if ctx.log_contains(pattern):
            raise TesterAssertionError(f"app log contains crash signature {pattern!r}")


TESTER = Tester(
    name="Default smoke",
    description=(
        "Launch the app's startup command, wait 20s, scan the run's log lines "
        "for crash signatures (Traceback / FATAL ERROR / Cannot find module), "
        "and capture a screenshot. Status is passed unless a signature or a "
        "launch failure appears."
    ),
    run=run,
    project_slug=None,
    kind="default-smoke",
)
