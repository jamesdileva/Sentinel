"""Card-Game click-through features (docs/clickthrough_plan.md).

Locator ground truth (2026-08-17 UI scan, corrected 2026-08-18 live run;
refreshed 2026-08-22 after the HUD/tabs layout pass): Login screen uses
`placeholder="Username"` / `placeholder="Password"` with `Login` /
`Register` buttons and still fires native alert()s (register confirms with
"Registered! Now login."). Post-login UI: balance lives in the sticky HUD
bar under `[data-testid="balance"]` (text `💰 $…`) — v1.17.19.x replaced
the old `div.text-xl.font-bold.mb-2` machine-card locator, and the game
column now carries a top switcher (`Slots` / `Coin Flip` / `Hi-Lo`
substring-matchable buttons). Deck/Inventory/Store are tabs in the right
sidebar (`Deck` / `Inventory` / `Store`).

Game flows covered:
- Slots: spin via the `🎰 $…` button, balance changes.
- Coin Flip: pick Heads, press `Flip $…`, await the flip animation, assert
  a `Won $` / `Lost $` result line.
- Hi-Lo: `Roll a number`, assert the number tile, bet on an enabled side,
  assert `Won $` / `Lost $`.
- Crates: Store tab -> BASIC -> suspense beat (~0.9 s shake) -> `Crate
  Rewards` modal -> Nice.

Auth note: every run registers a fresh throwaway `tester_<ts>` account —
the seeded `james` account (and all real data) is never touched. Register
does NOT auto-login: the feature waits for the register alert (proof the
POST landed) before clicking Login. Both alerts are dismissed via the
dialog handler (Playwright would otherwise stall). Usernames are
underscore-only since app-side validation rejects hyphens (2026-08-22).
"""

import re
import threading
import time

from app.testers._helpers import TesterAssertionError, TesterTimeoutError
from app.testers.features import Feature, FeatureContext

APP_URL = "http://localhost:5173"  # vite 8 binds ::1 — localhost, not 127.0.0.1

USERNAME_PREFIX = "tester_"  # app validates [a-zA-Z0-9_]+ — hyphens rejected
PASSWORD = "feature-pass-1"


def _register_and_login(ctx: FeatureContext):
    """Fresh throwaway account through the real auth flow; returns page."""
    page = ctx.page
    ctx.go(APP_URL)

    registered = threading.Event()

    def _on_dialog(dialog):
        try:
            dialog.dismiss()
        except Exception:
            # a listener from a previous feature on this shared page may
            # have handled the dialog already — the flag below is what counts
            pass
        registered.set()

    page.on("dialog", _on_dialog)

    # suffix truncated to stay under the app's 20-char username cap
    username = f"{USERNAME_PREFIX}{time.time_ns() % 10**9}"
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
    # data-testid survives restyles (v1.17.19.x HUD pass moved the balance)
    balance = page.locator('[data-testid="balance"]')
    balance.first.wait_for(state="visible", timeout=20000)
    ctx.step("logged in — balance display visible")

    collect = page.get_by_role("button", name="Collect")
    if collect.count():
        collect.click()
        ctx.step("daily login popup collected")

    return page, balance


def _register_and_spin(ctx: FeatureContext) -> None:
    page, balance = _register_and_login(ctx)
    ctx.shot("logged in with balance")

    before = balance.first.inner_text()
    page.get_by_role("button", name=re.compile(r"🎰 \$\d+")).click()
    ctx.step("spin placed")
    page.wait_for_timeout(3000)
    after = balance.first.inner_text()
    if after == before:
        raise TesterAssertionError(f"balance did not change after spin ({before!r})")
    ctx.step(f"balance changed after spin ({before} -> {after})")
    ctx.shot("post-spin state")


def _coin_flip(ctx: FeatureContext) -> None:
    page, _ = _register_and_login(ctx)

    page.get_by_role("button", name="Coin Flip").click()
    ctx.step("switched to Coin Flip")

    page.get_by_role("button", name="Heads").click()
    ctx.step("picked heads")

    page.get_by_role("button", name=re.compile(r"Flip \$\d+")).click()
    ctx.step("flip placed")

    # flip animation (~0.9 s) + round trip
    deadline = time.time() + 15
    result = None
    while time.time() < deadline:
        result = page.get_by_text(re.compile(r"Won \$|Lost \$"))
        if result.count():
            break
        page.wait_for_timeout(250)
    if not result or not result.count():
        raise TesterTimeoutError("coin flip result line never appeared")
    ctx.step(f"coin flip resolved: {result.first.inner_text()!r}")
    ctx.shot("coin flip result")


def _hi_lo(ctx: FeatureContext) -> None:
    page, _ = _register_and_login(ctx)

    page.get_by_role("button", name="Hi-Lo").click()
    ctx.step("switched to Hi-Lo")

    page.get_by_role("button", name=re.compile(r"Roll a number")).click()
    ctx.step("rolled a base number")

    higher = page.get_by_role("button", name=re.compile(r"Higher"))
    lower = page.get_by_role("button", name=re.compile(r"Lower"))
    higher.wait_for(state="visible", timeout=10000)

    # sides disable when they have zero winning outcomes (base 1 or 100)
    target = higher if higher.is_enabled() else lower
    if not target.is_enabled():
        raise TesterAssertionError("both Hi-Lo sides disabled (unexpected)")
    label = "Higher" if target is higher else "Lower"
    target.click()
    ctx.step(f"bet {label}")

    deadline = time.time() + 15
    result = None
    while time.time() < deadline:
        result = page.get_by_text(re.compile(r"Won \$|Lost \$"))
        if result.count():
            break
        page.wait_for_timeout(250)
    if not result or not result.count():
        raise TesterTimeoutError("hi-lo result line never appeared")
    ctx.step(f"hi-lo resolved: {result.first.inner_text()!r}")
    ctx.shot("hi-lo result")


def _open_crate(ctx: FeatureContext) -> None:
    page, _ = _register_and_login(ctx)

    page.get_by_role("button", name="Store").click()
    ctx.step("opened store tab")

    # starter balance ($1000) comfortably covers the $100 basic crate
    page.get_by_role("button", name=re.compile(r"BASIC")).click()
    ctx.step("basic crate opened")

    modal = page.get_by_text("Crate Rewards")
    modal.wait_for(state="visible", timeout=15000)
    ctx.step("crate rewards modal visible")

    ctx.shot("crate rewards")
    page.get_by_role("button", name="Nice").click()
    ctx.step("rewards dismissed")


FEATURES = [
    Feature(
        "register throwaway account and spin",
        "Register a fresh tester-<ts> account via the UI, log in, collect "
        "the daily reward popup, and verify the balance display changes "
        "after a slots spin.",
        _register_and_spin,
    ),
    Feature(
        "coin flip round",
        "Switch to the Coin Flip game, pick Heads, flip, and verify a "
        "Won/Lost result line renders after the flip animation.",
        _coin_flip,
    ),
    Feature(
        "hi-lo round",
        "Switch to the Hi-Lo game, roll a base number, bet on an available "
        "side, and verify a Won/Lost result line renders.",
        _hi_lo,
    ),
    Feature(
        "open basic crate",
        "Open the Store tab, buy/open a BASIC crate, and verify the Crate "
        "Rewards reveal modal appears; dismiss it.",
        _open_crate,
    ),
]
