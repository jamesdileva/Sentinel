"""Card-Game click-through features (docs/clickthrough_plan.md).

Locator ground truth (2026-08-17, UI scan): Login screen
(`placeholder="Username"` / `placeholder="Password"`, `Login` /
`Register` buttons), SlotMachine shows the balance as
`💵 ${balance.toLocaleString()}` in a `div.font-bold.mb-2`, the spin
button reads `🎰 ${bet * multiplier}` ("🎰 $100" at default x1), and the
`Daily Login` popup (with a `Collect` button) overlays after login.

Auth note: every run registers a fresh throwaway `tester-<ts>` account —
the seeded `james` account (and all real data) is never touched. Both
`handleRegister` and `handleLogin` fire native `alert()`s (Playwright
would otherwise fail on unexpected dialogs), and register does NOT
auto-login: the feature waits for the register alert (proof the POST
landed) before clicking Login.
"""

import threading
import time

from app.testers._helpers import TesterTimeoutError
from app.testers.features import Feature, FeatureContext

APP_URL = "http://localhost:5173"  # vite 8 binds ::1 — localhost, not 127.0.0.1

USERNAME_PREFIX = "tester-"
PASSWORD = "feature-pass-1"


def _register_and_spin(ctx: FeatureContext) -> None:
    page = ctx.page
    ctx.go(APP_URL)

    # Native alerts fire on register and login — dismiss everything, and
    # flag the register alert (it only fires after the POST resolves).
    registered = threading.Event()

    def _on_dialog(dialog):
        dialog.dismiss()
        registered.set()

    page.on("dialog", _on_dialog)

    username = f"{USERNAME_PREFIX}{time.time_ns()}"
    page.get_by_placeholder("Username").fill(username)
    page.get_by_placeholder("Password").fill(PASSWORD)
    page.get_by_role("button", name="Register").click()
    ctx.step("submitted registration form")

    deadline = time.time() + 15
    while not registered.is_set() and time.time() < deadline:
        page.wait_for_timeout(250)
    if not registered.is_set():
        raise TesterTimeoutError("register alert never fired — POST did not land")
    ctx.step("registration completed (alert confirmed)")

    page.get_by_role("button", name="Login").click()
    balance = page.locator("div.font-bold.mb-2", has_text="💵")
    balance.first.wait_for(state="visible", timeout=20000)
    ctx.step("logged in — balance display visible")

    collect = page.get_by_role("button", name="Collect")
    if collect.count():
        collect.click()
        ctx.step("daily login popup collected")
    ctx.shot("logged in with balance")

    before = balance.first.inner_text()
    page.get_by_role("button", name="🎰 $100", exact=True).click()
    ctx.step("spin $100 placed")
    page.wait_for_timeout(3000)
    after = balance.first.inner_text()
    if after == before:
        raise TesterTimeoutError(f"balance did not change after spin ({before!r})")
    ctx.step(f"balance changed after spin ({before} -> {after})")
    ctx.shot("post-spin state")


FEATURES = [
    Feature(
        "register throwaway account and spin",
        "Register a fresh tester-<ts> account via the UI, log in, collect "
        "the daily reward popup, and verify the balance display changes "
        "after a $100 spin.",
        _register_and_spin,
    ),
]
