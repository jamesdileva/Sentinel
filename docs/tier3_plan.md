# Tier 3 — Error Triage (v1.17.12.0)

Reframed from the original "AI-assisted triage" seed (`later.md`): the
durable value is **deterministic error capture**, and the AI is an *optional*
single-call description layer on top. No AI is ever required to triage, and
the AI never proposes fixes, causes, or decisions (Rules 2 + 3).

## Design

### Deterministic core — `POST /api/v1/sessions/{id}/triage`

Zero AI (Rule 3). Builds an evidence packet from the session's own record:

| Field | Source | Notes |
|---|---|---|
| `status`, `actual_outcome` | session row | what the run reported |
| `error_lines` | session `log_slice` | lines matching ERROR/CRITICAL/Traceback/`error:`/`failed to`, quoted verbatim, capped 40 |
| `patterns` | log slice scan | known exception labels (ModuleNotFoundError, ConnectionRefusedError, ...) |
| `frames` | traceback `File "..." line N` parsing | resolved against the project path; frames outside the project are dropped (not the project's own code); each carries a source preview read from disk (3 lines before / 2 after) |
| `traceback_available` | any `File` frame parsed | |
| `note` | derived | "No traceback found — source mapping unavailable" or "frames found but none inside the project" |

The packet is stored in the new `TriageAnalysis` table (session FK, evidence
JSON, `summary`, `model`, `created_at`). The table is created by
`create_all` (no ALTER migration needed) and rows are cascade-deleted with
their session. One row per triage click — re-triaging appends history.

### Optional AI layer — `POST /api/v1/sessions/{id}/summarize`

One small local call (`llama3.1:8b`, `max_tokens` 150, `num_ctx` 4096 —
overridden down from the 32768 default so generation stays fast for a tiny
packet; `purpose="triage-summary"` lands in `ollama_query_log` for the
System page). The prompt asks for **one paragraph describing what the
evidence shows** and explicitly forbids fixes/root causes/next steps.
The response updates the latest triage row with `summary` + `model` +
timestamp (Rule 7 provenance). If the session was never triaged, summarize
creates the evidence row first. `503` when Ollama is unreachable — the
deterministic card still renders.

### API rules

- 400 on `running` sessions ("end it before triaging"); 404 on unknown ids.
- `passed` sessions are simply not offered the button (no failure to capture).

## Frontend

Sessions page, expanded detail of a `failed`/`investigate` session:

- **Triage failure** button → evidence card: verbatim error lines (red pre),
  pattern chips, `relative_path:line` frames with the culprit source line
  highlighted, the `note`, and a Re-triage button.
- **AI summary** button → the description + provenance line
  (`llama3.1:8b · <timestamp>`). Ollama-down shows the 503 detail as a toast.

## Tests

`backend/tests/test_triage.py` (+21): error-line extraction + cap, Windows
path frame parsing, source previews (absolute + relative frame paths, missing
file → empty preview), evidence notes (no traceback / unresolvable), API
triage 200/400/404, summarize provenance (summary + model + query log row),
summarize-without-prior-triage collapse, Ollama-down 503, cascade delete.

## Rules check

- **Rule 1**: everything local — evidence reads the local log + local repo
  files; the LLM is local Ollama.
- **Rule 2**: AI is interpretation-only, user-triggered, never autonomous;
  it writes no session fields except its own provenance-annotated summary.
- **Rule 3**: statuses, evidence, and source lines are 100% deterministic;
  the LLM output is never treated as fact (no fixes, no decisions).
- **Rule 7**: model + timestamp stored with every summary; evidence is
  reproducible byte-for-byte from the session's log slice.