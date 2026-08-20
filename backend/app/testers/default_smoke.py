"""Default smoke tester — applies to any launchable app without a custom
tester (docs/tier2_plan.md Phase B).

Deterministic contract: run the app's discovered `test` command first
(front of the run — its output lands in the app log, v1.17.17.1), then
launch the app's startup command, let it settle, verify no crash
signatures appeared in the run's log lines, and capture a screenshot.
Status: passed, or investigate (launch failure) / failed (crash signature
in the log or a red test command).
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
    test_cmd = (commands or {}).get("test")
    if test_cmd:
        ctx.cli(test_cmd, timeout_s=600, expect_exit=0)
    ctx.launch(startup)
    ctx.wait(20)
    ctx.screenshot("app window after launch")
    for pattern in CRASH_PATTERNS:
        if ctx.log_contains(pattern):
            raise TesterAssertionError(f"app log contains crash signature {pattern!r}")


TESTER = Tester(
    name="Default smoke",
    description=(
        "Run the app's discovered test command (output goes to the app "
        "log), then launch the startup command, wait 20s, scan the run's "
        "log lines for crash signatures (Traceback / FATAL ERROR / Cannot "
        "find module), and capture a screenshot. Status is passed unless a "
        "signature, a red test command, or a launch failure appears."
    ),
    run=run,
    project_slug=None,
    kind="default-smoke",
)
