#!/usr/bin/env python
"""Head-to-head LLM eval on the real architecture-summary path.

Builds the shared prompt exactly like
`RagService.ingest_project_summary` does (docs-first
`_file_summary_context` + `project_summary.j2`), then runs each
`--models` entry once (or `--runs-per-model` times) through
`OllamaService.generate_with_metrics` with identical
`max_tokens` / `temperature` / `num_ctx` sizing.

Read-only by design (Rule 2, Rule 7):
- DB is only SELECTed (project + files + commits); the session is never
  committed.
- Generation goes through `OllamaService` directly, NOT
  `RagService._generate_with_metrics`, so nothing is written to
  `ollama_query_log`, `activity_event`, or `KnowledgeSummary`/Chroma.
- Outputs land in `--out-dir` (default: `data/evals/...`, git-ignored).

Usage:
    .\\backend\\.venv\\Scripts\\python.exe scripts/eval_summary_head_to_head.py
    .\\backend\\.venv\\Scripts\\python.exe scripts/eval_summary_head_to_head.py ^
        --project sentinel --models llama3.1:8b qwen2.5:7b-instruct
    # future reuse:
    .\\backend\\.venv\\Scripts\\python.exe scripts/eval_summary_head_to_head.py ^
        --project fin-sight --models llama3.1:8b mistral:7b --runs-per-model 2

Each run takes minutes on a 10k-token prefill; defaults are 1 run per
model so a two-model shootout is ~20 min.
"""

import argparse
import datetime
import json
import random
import re
import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
if str(ROOT / "backend") not in sys.path:
    sys.path.insert(0, str(ROOT / "backend"))

from app.core.config import settings  # noqa: E402
from app.db.connection import get_engine  # noqa: E402
from app.services.ollama_service import OllamaService  # noqa: E402
from app.services.rag_service import RagService  # noqa: E402


def _slug(model: str) -> str:
    return re.sub(r"[^A-Za-z0-9._-]+", "_", model)


def _find_project(session, needle: str):
    """Match by exact id first, then case-insensitive name substring."""
    from app.db.models import Project
    from sqlmodel import select

    by_id = session.get(Project, needle)
    if by_id is not None:
        return by_id
    rows = session.exec(select(Project)).all()
    lowered = needle.lower()
    for project in rows:
        if lowered in (project.name or "").lower():
            return project
    available = ", ".join(sorted(p.name for p in rows)[:40])
    raise SystemExit(f"Unknown project {needle!r}. Available include: {available}")


def _build_shared_prompt(project_name: str):
    """Return (project, prompt, prompt_meta). No DB writes."""
    from sqlmodel import Session

    with Session(get_engine()) as session:
        project = _find_project(session, project_name)
        rag = RagService(session)
        try:
            context = rag._file_summary_context(project)
        finally:
            rag.close()
        from app.services.rag_service import _PROJECT_SUMMARY_TEMPLATE

        prompt = _PROJECT_SUMMARY_TEMPLATE.format(
            project_name=project.name,
            language=project.language,
            framework=project.framework or "unknown",
            context=context or "No file content available.",
        )
        meta = {
            "project_id": project.id,
            "project_name": project.name,
            "language": project.language,
            "framework": project.framework,
            "prompt_chars": len(prompt),
            "context_chars": len(context),
        }
        # Detach values before the session closes.
        return meta, prompt


def _check_ollama(models: list[str]) -> list[str]:
    probe = OllamaService()
    try:
        if not probe.is_available():
            raise SystemExit(
                f"Ollama is not reachable at {probe.host}. "
                "Start the Ollama app (see docs/desktop.md)."
            )
        installed = probe.list_models()
    finally:
        probe.close()
    missing = [m for m in models if m not in installed]
    if missing:
        # Eval burns ~10 min per trial on a 10k-token prefill — fail fast on
        # a bad tag instead of dying late (qwen3.5:9b probe, Oct 2026).
        raise SystemExit(
            f"Unknown model tag(s): {missing}\n"
            f"       installed: {installed}\n"
            "       `ollama pull <tag>` first, or fix --models."
        )
    return installed


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Head-to-head architecture-summary eval (read-only)."
    )
    parser.add_argument("--project", default="sentinel")
    parser.add_argument(
        "--models",
        nargs="+",
        default=["llama3.1:8b", "qwen2.5:7b-instruct"],
    )
    parser.add_argument("--runs-per-model", type=int, default=1)
    parser.add_argument("--max-tokens", type=int, default=None)
    parser.add_argument("--temperature", type=float, default=0.3)
    # Reasoning models (Qwen3+): the hidden thinking chain shares the
    # num_predict budget with the answer — with thinking on (default) a
    # 1250 cap can be eaten whole by thinking, leaving an empty response
    # (qwen3.5:9b probe, Oct 2026: eval_count=1250, response="").
    # --think off sends think:false for an answer-only, like-for-like run.
    parser.add_argument("--think", choices=["on", "off"], default="on")
    parser.add_argument("--cooldown-seconds", type=float, default=15.0)
    parser.add_argument("--seed", type=int, default=42)
    parser.add_argument("--no-shuffle", action="store_true")
    parser.add_argument("--out-dir", default=None)
    args = parser.parse_args()

    max_tokens = args.max_tokens or settings.ollama_summary_max_tokens
    stamp = datetime.datetime.now().strftime("%Y%m%d-%H%M%S")
    out_dir = (
        Path(args.out_dir)
        if args.out_dir
        else ROOT / "data" / "evals" / f"summary-hh-{stamp}"
    )
    out_dir.mkdir(parents=True, exist_ok=True)

    print(f"[eval] project={args.project} models={args.models}", flush=True)
    print(
        f"[eval] max_tokens={max_tokens} temperature={args.temperature} "
        f"runs_per_model={args.runs_per_model} out={out_dir}",
        flush=True,
    )
    print(
        f"[eval] live settings: model={settings.ollama_model} "
        f"num_ctx={settings.ollama_num_ctx} "
        f"dynamic_ctx={settings.ollama_dynamic_ctx} "
        f"keep_alive={settings.ollama_keep_alive} host={settings.ollama_host}",
        flush=True,
    )
    installed = _check_ollama(args.models)
    print(f"[eval] ollama models: {installed}", flush=True)

    meta, prompt = _build_shared_prompt(args.project)
    num_ctx = OllamaService._fit_num_ctx(prompt, max_tokens)
    print(
        f"[eval] prompt built: {meta['prompt_chars']} chars "
        f"(~{meta['prompt_chars'] // 3} est tokens), num_ctx={num_ctx}",
        flush=True,
    )
    (out_dir / "prompt.txt").write_text(prompt, encoding="utf-8")

    trials: list[tuple[str, int]] = [
        (model, run) for model in args.models for run in range(args.runs_per_model)
    ]
    if not args.no_shuffle:
        rng = random.Random(args.seed)
        rng.shuffle(trials)
        print(f"[eval] trial order (seed={args.seed}): {trials}", flush=True)

    results: list[dict] = []
    think_flag: bool | None = None if args.think == "on" else False
    print(f"[eval] think={args.think}", flush=True)
    try:
        for index, (model, run) in enumerate(trials):
            if index > 0 and args.cooldown_seconds > 0:
                print(f"[eval] cooling down {args.cooldown_seconds}s ...", flush=True)
                time.sleep(args.cooldown_seconds)
            label = f"{_slug(model)}_r{run}"
            print(
                f"[eval] ({index + 1}/{len(trials)}) generating {model} ...", flush=True
            )
            svc = OllamaService()
            wall_start = time.perf_counter()
            try:
                result = svc.generate_with_metrics(
                    prompt,
                    model=model,
                    max_tokens=max_tokens,
                    temperature=args.temperature,
                    purpose="eval-summary",
                    think=think_flag,
                )
            finally:
                svc.close()
            wall_s = time.perf_counter() - wall_start
            eval_count = int(result.get("eval_count") or 0)
            eval_ns = int(result.get("eval_duration_ns") or 0)
            tok_s = round(eval_count / (eval_ns / 1e9), 1) if eval_ns else None
            response_text = result.get("response", "")
            thinking_text = result.get("thinking", "")
            done_reason = result.get("done_reason", "")
            entry = {
                "model": model,
                "run": run,
                "label": label,
                "response": response_text,
                "response_chars": len(response_text),
                "response_tokens": eval_count,
                "tokens_per_second": tok_s,
                "eval_duration_ns": eval_ns,
                "total_duration_ns": int(result.get("total_duration_ns") or 0),
                "wall_seconds": round(wall_s, 1),
                "reported_model": result.get("model"),
                "num_ctx_sent": num_ctx,
                "max_tokens": max_tokens,
                "temperature": args.temperature,
                "think": args.think,
                "done_reason": done_reason,
                "prompt_eval_count": int(result.get("prompt_eval_count") or 0),
                "thinking_chars": len(thinking_text),
                "truncated_suspect": done_reason == "length"
                or (
                    len(response_text) > 0
                    and response_text.rstrip()[-1:] not in ".:!?)\"'"
                ),
            }
            results.append(entry)
            (out_dir / f"{label}.md").write_text(
                f"# {model} (run {run})\n\n"
                f"tok/s={tok_s} tokens={eval_count} done_reason={done_reason} "
                f"wall={entry['wall_seconds']}s num_ctx={num_ctx} think={args.think}\n\n"
                f"{entry['response']}\n",
                encoding="utf-8",
            )
            if thinking_text:
                (out_dir / f"{label}_thinking.md").write_text(
                    f"# {model} (run {run}) — hidden thinking chain\n\n"
                    f"{thinking_text}\n",
                    encoding="utf-8",
                )
            (out_dir / f"{label}.json").write_text(
                json.dumps(entry, indent=2), encoding="utf-8"
            )
            print(
                f"[eval] {model} done: {eval_count} tokens "
                f"(done_reason={done_reason}, thinking={entry['thinking_chars']} chars), "
                f"{tok_s} tok/s, {entry['wall_seconds']}s wall",
                flush=True,
            )
    finally:
        # Always persist partial results — an aborted run previously left
        # only bare .md files with no results.json (Oct 2026).
        (out_dir / "results.json").write_text(
            json.dumps(
                {
                    "generated_at": datetime.datetime.now(
                        datetime.timezone.utc
                    ).isoformat(),
                    "project": meta,
                    "params": {
                        "models": args.models,
                        "runs_per_model": args.runs_per_model,
                        "max_tokens": max_tokens,
                        "temperature": args.temperature,
                        "think": args.think,
                        "num_ctx_sent": num_ctx,
                        "seed": args.seed,
                        "shuffled": not args.no_shuffle,
                        "trial_order": [f"{m}#{r}" for m, r in trials],
                        "completed_trials": len(results),
                    },
                    "live_settings": {
                        "ollama_host": settings.ollama_host,
                        "ollama_model": settings.ollama_model,
                        "ollama_num_ctx": settings.ollama_num_ctx,
                        "ollama_dynamic_ctx": settings.ollama_dynamic_ctx,
                        "ollama_keep_alive": settings.ollama_keep_alive,
                        "ollama_summary_max_tokens": settings.ollama_summary_max_tokens,
                    },
                    "ollama_installed": installed,
                    "results": [
                        {k: v for k, v in r.items() if k != "response"} for r in results
                    ],
                },
                indent=2,
            ),
            encoding="utf-8",
        )

    # Blind A/B copies: shuffled labels so judging is not anchored on names.
    blind_order = [r["label"] for r in results]
    rng = random.Random(args.seed + 1)
    rng.shuffle(blind_order)
    mapping = {}
    for blind_idx, label in enumerate(blind_order):
        blind = chr(ord("A") + blind_idx)
        mapping[blind] = label
        src = (out_dir / f"{label}.md").read_text(encoding="utf-8")
        # v1.17.19.5 fix: the per-model file header carries the model name
        # ("# <model> (run N)"), so strip the whole first line — replacing
        # the slug alone left every blind file labeled.
        blind_body = "\n".join(src.splitlines()[1:]).lstrip("\n")
        (out_dir / f"BLIND_{blind}.md").write_text(
            f"# Candidate {blind}\n{blind_body}\n", encoding="utf-8"
        )
    (out_dir / "MAPPING.txt").write_text(
        "Blind mapping (read AFTER judging):\n"
        + "\n".join(f"{blind} = {label}" for blind, label in sorted(mapping.items()))
        + "\n",
        encoding="utf-8",
    )

    report = {
        "generated_at": datetime.datetime.now(datetime.timezone.utc).isoformat(),
        "project": meta,
        "params": {
            "models": args.models,
            "runs_per_model": args.runs_per_model,
            "max_tokens": max_tokens,
            "temperature": args.temperature,
            "think": args.think,
            "num_ctx_sent": num_ctx,
            "seed": args.seed,
            "shuffled": not args.no_shuffle,
            "trial_order": [f"{m}#{r}" for m, r in trials],
            "completed_trials": len(results),
        },
        "live_settings": {
            "ollama_host": settings.ollama_host,
            "ollama_model": settings.ollama_model,
            "ollama_num_ctx": settings.ollama_num_ctx,
            "ollama_dynamic_ctx": settings.ollama_dynamic_ctx,
            "ollama_keep_alive": settings.ollama_keep_alive,
            "ollama_summary_max_tokens": settings.ollama_summary_max_tokens,
        },
        "ollama_installed": installed,
        "blind_mapping": mapping,
        "results": [{k: v for k, v in r.items() if k != "response"} for r in results],
    }
    (out_dir / "results.json").write_text(
        json.dumps(report, indent=2), encoding="utf-8"
    )

    print("\n==== SUMMARY ====", flush=True)
    for r in results:
        print(
            f"{r['model']}: {r['response_tokens']} tokens, "
            f"{r['tokens_per_second']} tok/s, {r['wall_seconds']}s wall "
            f"-> {r['label']}.md",
            flush=True,
        )
    print(
        f"Blind files: {', '.join(f'BLIND_{b}.md' for b in sorted(mapping))}",
        flush=True,
    )
    print("Judge BLIND_A/B first, then read MAPPING.txt to reveal.", flush=True)
    print(f"[eval] done. out={out_dir}", flush=True)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
