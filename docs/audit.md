# Sentinel Adversarial Audit — v1.17.18.0 (Part 3 of the batch plan)

A structured adversarial pass over the running system (2026-08-20). Scope:
data growth, process hygiene, backup/recovery, job concurrency, rule
compliance, and session edge cases. Fixes from Part 1 (portfolio screenshots
stub, tests-semantics gap) are already shipped in v1.17.18.0. All P1 fixes
applied in v1.17.18.1 (see below).

Priorities: **P0** = fix immediately, **P1** = fix in-batch, **P2** = track /
fix opportunistically.

**P0: none.** The pre-audit recon items that would have qualified (the
hardcoded portfolio screenshots stub, the tests-semantics gap that ignored
tester sessions) were fixed in Part 1 before this audit ran. The audit
itself found no immediate-critical issue.

---

## P1 — fixed in v1.17.18.1

### A1. No database backup/export path (P1)
The single `sentinel.db` (19.5 MB) + Chroma dir (205 MB) hold all session,
scan, RAG and sync state with **no snapshot path**. Sprint 14's plan
(`docs/03_Sprint_Plan.md` §963-1008) promised `scripts/backup.py` /
`scripts/restore.py` / `GET /api/v1/system/backup` — none were built; the
only "recovery" is a destructive Chroma `reset_all()`. `docs/01:1092`
claims log rotation that does not exist either.
**Fix:** `scripts/backup.py` — SQLite online backup (the `sqlite3` backup
API, safe under WAL), copy `data/chroma` + `data/screenshots` + `data/logs`
into `data/backups/sentinel-<date>.zip`, keep the last N (env knob), and a
CLI command. No beat (Rule 2 — user-initiated), docs row.

### A2. `data/logs/apps/*.log` unbounded growth (P1)
App logs are append-only forever (`build_runner.py:201` opens `"a"`; the
only truncation in the codebase is the per-run `sentinel.log` at
`logging.py:37`). Measured: Ag.log 148 KB/5,435 lines, Demake 174 KB — and
auto-launched apps keep appending while alive.
**Fix:** rotate per launch — cap each file at `max_file_size_kb`
(reuse the existing setting, e.g. 5120): on launch, if the log exceeds the
cap, rename to `<slug>.log.1` (keep one old) and start fresh; sessions
slice across files by re-reading both. Small, deterministic.

### A3. `data/screenshots/` unbounded growth (P1)
Every session end auto-captures ≥1 PNG + thumb (`app_sessions.py:204-211`);
deletion only via manual session delete. Measured: 41.7 MB / 387 files.
**Fix:** retention sweep in the backup script + a documented
`SENTINEL_SCREENSHOT_RETENTION_DAYS` (default off / 365) applied at
startup (delete shot files + rows older than N days — deterministic,
Rule 2: cleanup, never act).

### A4. No orphan-process sweep; cleanup gaps (P1)
- build→open launches are never reclaimed (`build_runner.py:53-55` by
  design); every desktop Run Build spawns a permanent extra instance.
- AG GUI is a documented leftover convention (`ag.py:17-21`) — killed only
  by the *next* AG run's window-title reclaim; a crashed backend leaves it
  until then.
- `tester_runner.py:126-128`: if `service.end()` raises, the packaged app
  kill is skipped.
- `command_runner.py:80-98`: `shell=True` + timeout kills only the direct
  cmd.exe child — grandchildren (npm/python trees) can orphan.
**Fix (bounded):** wrap the end-of-run kill in a `finally` in
`tester_runner.run` (kill regardless of `end()` outcome); add
`CREATE_NEW_PROCESS_GROUP` to `command_runner` + kill the tree on timeout.
The build→open and AG-GUI conventions stay (documented design — the user
wants the AG window to inspect); the audit just records them.

### A5. `SENTINEL_API_KEY` is a dead setting (P1-ish hygiene)
`config.py:122` defines it; **zero consumers** in the codebase. Either wire
it (auth for the loopback API — likely undesired) or remove it from
config + `.env.example` so nobody believes it does something. Recommend:
**remove** (Rule 1: loopback-only, no auth needed), documented in the
changelog.

---

## P2 — track / fix opportunistically

| # | Finding | Evidence |
|---|---------|----------|
| B1 | Sessions can stay stuck `running` after a crash — no startup recovery; `end()` is outside the try in `tester_runner` | `app_sessions.py:188-212`, `job_scheduler.py:186` (`shutdown(wait=False)`) |
| B2 | Job pool = 2 workers, no per-job timeout; a long AG tester (budget 900 s) queues the daily scan-all beat behind it | `job_scheduler.py:63-67,191-201` |
| B3 | Uncapped tables: `syncrun` (one per sync), `chatmessage`, `ollamaquerylog` — only `activityevent` has a ceiling (5000) | `activity_bus.py:31,77-82`, `sync_service.py:316` |
| B4 | `sentinel.log` grows for the whole process lifetime (bounded per restart only); docs 01:1092 promises daily rotation | `logging.py:37,85-90` |
| B5 | `data/redis/` is a stale tombstone of the removed Docker queue (93 KB, 4 files) — delete | repo `data/redis/` |
| B6 | Embedding/`list_models` on the settings probe runs a live Ollama call per page load (2 s timeout — acceptable, noted) | `settings_service.py` |

## Rule-compliance sweep — PASS (no findings)

- **Loopback (Rule 1):** feature nav refused for non-loopback hosts
  (`_context.py:30,107-124`, `LOOPBACK_PREFIXES` in feature_runner.py:68);
  Electron window targets must be file:// or loopback; media route has
  filename whitelist + resolve-inside-dir guard (`app_sessions.py:423-434`),
  SPA static mount checks `is_relative_to`; headless renders only tester
  constants.
- **AI provenance (Rule 7):** every generation records model + timestamp —
  RAG answers (`rag_service.py:653-674`), summaries, triage summaries,
  OllamaQueryLog.
- **Autonomy (Rule 2):** beats run only repo-sync (token-gated,
  deterministic) + scan-all + world tick; nothing auto-launches apps,
  runs testers, or builds.
- **Secrets:** `github_token` never appears in logs (env values redacted in
  `_helpers.py`); api_key is dead (see A5).

## High-value missing features (shortlist — pick what to build)

1. **DB backup + restore** (A1) — script + CLI + docs; protects the only
   copy of all state.
2. **Session diff / regression detection** — compare a project's latest two
   sessions: checkpoint counts, screenshot hashes, log-slice length;
   "regression since last run" signal on the Sessions page.
3. **Freshness signals** — portfolio card shows when each component's
   evidence was last updated (build log date, scan date, last session).
4. **Stale-`running` recovery at startup** — mark sessions left `running`
   across a restart as `failed` with a note (B1).
5. **Retention policy** — one env knob sweep for logs + screenshots (A2+A3).

## Verified mitigations already in place (credited)

per-run sentinel.log truncation; activityevent 5000-row cap; security
finding idempotence + resolve; startup project GC; electron-feature reclaim
loop with honest TesterEnvError; HFT/Airadio start+finally kills; session
delete removes files; incremental re-indexing; test-output caps.