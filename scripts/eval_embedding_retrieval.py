#!/usr/bin/env python
"""Head-to-head retrieval probe for local embedding models.

Compares embedding models on the retrieval path Sentinel actually uses:
chunked `file_summaries` documents embedded into a throwaway ChromaDB, then
scored against questions with known-correct source files.

Why a probe and not a benchmark: MTEB scores describe English/multilingual
averages over generic corpora. What matters here is whether *this* corpus's
questions retrieve *this* repo's right files, and at what embedding cost on
this machine. Both are measurable locally in minutes.

Read-only by design (Rule 1, Rule 2):
- The source DB is only SELECTed (project + file rows); nothing is committed.
- Every model gets its OWN throwaway ChromaDB under --out-dir. The live index
  at SENTINEL_CHROMA_PATH is never opened, so a probe cannot poison it (an
  embedding swap invalidates every existing vector — that is a deliberate,
  separate step, not an eval side-effect).
- Outputs land in `data/evals/...` which is git-ignored.

Metric: for each question, a list of EXPECTED source files (path substrings).
`hit@k` = did any retrieved chunk's file_path match at rank <= k; MRR rewards
ranking the right file higher. Sibling chunks of the same file count as one
match, because that is what a user experiences (the citation is the file).

Usage:
    .\\backend\\.venv\\Scripts\\python.exe scripts/eval_embedding_retrieval.py
    .\\backend\\.venv\\Scripts\\python.exe scripts/eval_embedding_retrieval.py ^
        --models bge-m3 nomic-embed-text --embedded-only
"""

import argparse
import datetime
import json
import re
import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
if str(ROOT / "backend") not in sys.path:
    sys.path.insert(0, str(ROOT / "backend"))

import chromadb  # noqa: E402
from app.core.config import settings  # noqa: E402
from app.db.connection import get_engine  # noqa: E402
from app.services.ollama_service import OllamaService  # noqa: E402
from app.services.rag_service import (  # noqa: E402
    _MAX_DOC_CHARS,  # noqa: E402
    _chunk_document,
    _is_doc_path,
    _read_local_file,
)

# Ground truth for THIS repo. Each question carries the source files whose
# content actually answers it, as path substrings (chunked docs and their
# siblings collapse to one file-level match). Edit freely — the probe reports
# any expected path it cannot find in the indexed file list, so stale entries
# are loud rather than silent.
QUESTIONS: list[dict] = [
    {
        "q": "What port does Sentinel serve on by default?",
        "expect": ["backend/app/core/config.py"],
    },
    {
        "q": "How are orphaned BuildLog rows cleaned up when Sentinel restarts?",
        "expect": ["backend/app/repositories/build.py", "backend/app/main.py"],
    },
    {
        "q": "Where do Pydantic response schemas live?",
        "expect": ["backend/app/schemas/"],
    },
    {
        "q": "What embedding model is used for the knowledge index?",
        "expect": ["backend/app/core/config.py"],
    },
    {
        "q": "How is the context window sized to the actual prompt?",
        "expect": ["backend/app/services/ollama_service.py"],
    },
    {
        "q": "How is the doc-first summary context selected and ranked?",
        "expect": ["backend/app/services/rag_service.py"],
    },
    {
        "q": "How does the scheduler register its background beats?",
        "expect": ["backend/app/services/job_scheduler.py"],
    },
    {
        "q": "How are markdown documents split into chunks for the vector index?",
        "expect": ["backend/app/services/rag_service.py"],
    },
    {
        "q": "Which projects are ignored when walking a project tree?",
        "expect": ["backend/app/core/config.py"],
    },
    {
        "q": "How does error triage build its deterministic evidence packet?",
        "expect": ["backend/app/services/triage_service.py"],
    },
    {
        "q": "Where are scripted testers registered by project slug?",
        "expect": ["backend/app/testers/__init__.py"],
    },
    {
        "q": "How does the packaged desktop shell find the repo dataset?",
        "expect": ["desktop/main.js"],
    },
    {
        "q": "What does run.py verify before starting the server?",
        "expect": ["run.py"],
    },
    {
        "q": "How are security findings gated on the indexed files?",
        "expect": ["backend/app/services/security_scanner.py"],
    },
    {
        "q": "How are build commands discovered from project manifests?",
        "expect": ["backend/app/utils/command_extractor.py"],
    },
    {
        "q": "Where is the RAG chat endpoint that answers from context?",
        "expect": ["backend/app/api/v1/rag.py"],
    },
    {
        "q": "What is the Tier 2 scripted-tester integration contract?",
        "expect": ["docs/tier2_plan.md"],
    },
    {
        "q": "How are stored architecture summaries reused instead of regenerated?",
        "expect": ["backend/app/services/rag_service.py"],
    },
    {
        "q": "How is portfolio health scoring weighted?",
        "expect": ["backend/app/services/portfolio_service.py"],
    },
    {
        "q": "What is the fastest path for a build to be marked skipped?",
        "expect": ["backend/app/services/build_runner.py"],
    },
]


def _slug(model: str) -> str:
    return re.sub(r"[^A-Za-z0-9._-]+", "_", model)


def _build_corpus(project_name: str, max_chunks: int, embedded_only: bool):
    """Rebuild the `file_summaries` documents exactly as ingest_files does.

    Returns (corpus, meta). `id` is `{file_row_id}#{chunk}` to mirror the live
    row ids; `file_path` is the repo-relative path used for ground truth.
    """
    from app.db.models import ProjectFile
    from sqlmodel import Session, select

    with Session(get_engine()) as session:
        project = _find_project(session, project_name)
        rows = session.exec(
            select(ProjectFile).where(ProjectFile.project_id == project.id)
        ).all()
        # Detach everything the caller needs before the session closes.
        records = [(r.id, r.path, r.absolute_path, bool(r.embedding_id)) for r in rows]
        meta = {
            "project_id": project.id,
            "project_name": project.name,
            "indexed_files": len(records),
        }
    if embedded_only:
        records = [r for r in records if r[3]]
        meta["filtered_to_embedded"] = len(records)

    # Deterministic order: path first so repeated probes index the same slice.
    records.sort(key=lambda r: r[1])
    corpus: list[dict] = []
    for row_id, rel_path, abs_path, _ in records:
        if _is_doc_path(rel_path):
            chunks = _chunk_document(_read_local_file(abs_path))
        else:
            chunks = [_read_local_file(abs_path)[:_MAX_DOC_CHARS]]
        for chunk_index, chunk_text in enumerate(chunks):
            if not chunk_text.strip():
                continue
            corpus.append(
                {
                    "id": f"{row_id}#{chunk_index}",
                    "file_path": rel_path,
                    "doc": f"{rel_path}\n\n{chunk_text}",
                }
            )
            if len(corpus) >= max_chunks:
                meta["truncated_to_max_chunks"] = True
                return corpus, meta
    return corpus, meta


def _find_project(session, needle: str):
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


def _check_ollama(models: list[str]) -> list[str]:
    probe = OllamaService()
    try:
        if not probe.is_available():
            raise SystemExit(
                f"Ollama is not reachable at {probe.host}. Start the Ollama app."
            )
        installed = probe.list_models()
    finally:
        probe.close()
    installed_normalized = {_normalize_tag(m) for m in installed}
    missing = [m for m in models if _normalize_tag(m) not in installed_normalized]
    if missing:
        raise SystemExit(
            f"Unknown embedding model tag(s): {missing}\n       installed: {installed}\n"
            "       `ollama pull <tag>` first, or fix --models."
        )
    return installed


def _normalize_tag(name: str) -> str:
    """`nomic-embed-text:latest` and `nomic-embed-text` are the same model
    (mirrors settings_service._validation_warnings, so the probe accepts what
    the app accepts)."""
    return name[: -len(":latest")] if name.endswith(":latest") else name


def _embed_corpus(model: str, corpus: list[dict], svc: OllamaService):
    """Embed every document; returns (vectors, docs/sec, tokens, duration_ns)."""
    vectors: list[list[float]] = []
    tokens = 0
    duration_ns = 0
    start = time.perf_counter()
    for index, item in enumerate(corpus, start=1):
        vector, metrics = svc.embed_with_metrics(item["doc"], model=model)
        vectors.append(vector)
        tokens += int(metrics.get("tokens") or 0)
        duration_ns += int(metrics.get("duration_ns") or 0)
        if index % 100 == 0 or index == len(corpus):
            elapsed = time.perf_counter() - start
            print(
                f"    embedded {index}/{len(corpus)} ({index / elapsed:.0f} docs/s)",
                flush=True,
            )
    wall = time.perf_counter() - start
    return vectors, (len(corpus) / wall if wall else 0.0), tokens, duration_ns


def _score(questions: list[dict], hits_by_question: dict[str, list[dict]]) -> dict:
    """hit@1/3/5 + MRR over files that actually matched an expectation."""
    totals = {"hit@1": 0, "hit@3": 0, "hit@5": 0, "mrr": 0.0}
    per_question: list[dict] = []
    for entry in questions:
        hits = hits_by_question[entry["q"]]
        expected = tuple(e.replace("\\", "/").lower() for e in entry["expect"])
        first_rank = None
        for rank, hit in enumerate(hits, start=1):
            path = (hit.get("file_path") or "").replace("\\", "/").lower()
            if any(token in path for token in expected):
                first_rank = rank
                break
        row = {
            "question": entry["q"],
            "first_relevant_rank": first_rank,
            "top_paths": [h.get("file_path") for h in hits[:5]],
        }
        per_question.append(row)
        if first_rank is not None:
            totals["mrr"] += 1.0 / first_rank
            if first_rank <= 1:
                totals["hit@1"] += 1
            if first_rank <= 3:
                totals["hit@3"] += 1
            if first_rank <= 5:
                totals["hit@5"] += 1
    count = len(questions) or 1
    return {
        "n": len(questions),
        "hit@1": round(totals["hit@1"] / count, 4),
        "hit@3": round(totals["hit@3"] / count, 4),
        "hit@5": round(totals["hit@5"] / count, 4),
        "mrr": round(totals["mrr"] / count, 4),
        "per_question": per_question,
    }


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Read-only embedding-model retrieval probe."
    )
    parser.add_argument("--project", default="sentinel")
    parser.add_argument(
        "--models",
        nargs="+",
        default=[
            "nomic-embed-text",
            "bge-m3",
            "qwen3-embedding:0.6b",
            "embeddinggemma",
        ],
    )
    parser.add_argument(
        "--max-chunks",
        type=int,
        default=300,
        help="document cap per model (the corpus is sliced deterministically)",
    )
    parser.add_argument(
        "--embedded-only",
        action="store_true",
        help="only files the live index has already embedded",
    )
    parser.add_argument("--top-k", type=int, default=5)
    parser.add_argument("--out-dir", default=None)
    args = parser.parse_args()

    stamp = datetime.datetime.now().strftime("%Y%m%d-%H%M%S")
    out_dir = (
        Path(args.out_dir)
        if args.out_dir
        else ROOT / "data" / "evals" / f"embedding-probe-{stamp}"
    )
    out_dir.mkdir(parents=True, exist_ok=True)

    print(f"[probe] project={args.project} models={args.models}", flush=True)
    print(f"[probe] live chroma (never opened): {settings.chroma_path}", flush=True)
    installed = _check_ollama(args.models)
    print(f"[probe] installed embedding models: {installed}", flush=True)

    corpus, meta = _build_corpus(args.project, args.max_chunks, args.embedded_only)
    meta["corpus_chunks"] = len(corpus)
    (out_dir / "corpus_meta.json").write_text(
        json.dumps(meta, indent=2), encoding="utf-8"
    )
    print(
        f"[probe] corpus: {len(corpus)} chunks from "
        f"{meta.get('filtered_to_embedded', meta['indexed_files'])} files",
        flush=True,
    )

    # Ground-truth sanity: an expectation that matches no indexed path would
    # silently count as a miss for every model.
    known_paths = {c["file_path"].replace("\\", "/").lower() for c in corpus}
    for entry in QUESTIONS:
        for token in entry["expect"]:
            flat = token.replace("\\", "/").lower().rstrip("/")
            if not any(flat in path for path in known_paths):
                print(
                    f"[warn] no indexed file matches expectation {token!r} "
                    f"(question: {entry['q'][:60]}...) — it will score 0 everywhere",
                    flush=True,
                )

    svc = OllamaService()
    results: list[dict] = []
    try:
        for model in args.models:
            model_dir = out_dir / f"chroma-{_slug(model)}"
            print(f"[probe] === {model} ===", flush=True)
            vectors, docs_per_s, tokens, duration_ns = _embed_corpus(model, corpus, svc)
            dim = len(vectors[0]) if vectors else 0
            print(
                f"[probe] {model}: {len(vectors)} vectors, dim={dim}, "
                f"{docs_per_s:.1f} docs/s",
                flush=True,
            )
            client = chromadb.PersistentClient(path=str(model_dir))
            collection = client.create_collection(
                "probe", metadata={"hnsw:space": "cosine"}
            )
            collection.add(
                ids=[c["id"] for c in corpus],
                embeddings=vectors,
                documents=[c["doc"] for c in corpus],
                metadatas=[{"file_path": c["file_path"]} for c in corpus],
            )
            hits_by_question: dict[str, list[dict]] = {}
            for entry in QUESTIONS:
                query_vector, _ = svc.embed_with_metrics(entry["q"], model=model)
                raw = collection.query(
                    query_embeddings=[query_vector], n_results=args.top_k
                )
                metadatas = (raw.get("metadatas") or [[]])[0]
                distances = (raw.get("distances") or [[]])[0]
                hits_by_question[entry["q"]] = [
                    {
                        "id": (raw["ids"][0][i] if raw.get("ids") else ""),
                        "file_path": (metadatas[i] or {}).get("file_path"),
                        "distance": distances[i] if i < len(distances) else None,
                    }
                    for i in range(len(metadatas))
                ]
            score = _score(QUESTIONS, hits_by_question)
            results.append(
                {
                    "model": model,
                    "dimensions": dim,
                    "chunks": len(vectors),
                    "docs_per_second": round(docs_per_s, 2),
                    "embed_tokens": tokens,
                    "embed_duration_ns": duration_ns,
                    **{k: v for k, v in score.items() if k != "per_question"},
                    "per_question": score["per_question"],
                }
            )
            print(
                f"[probe] {model}: hit@1={score['hit@1']} hit@3={score['hit@3']} "
                f"hit@5={score['hit@5']} mrr={score['mrr']}",
                flush=True,
            )
    finally:
        svc.close()

    results.sort(key=lambda r: (-r["hit@5"], -r["mrr"]))
    report = {
        "generated_at": datetime.datetime.now(datetime.timezone.utc).isoformat(),
        "project": meta,
        "params": {
            "models": args.models,
            "max_chunks": args.max_chunks,
            "top_k": args.top_k,
            "embedded_only": args.embedded_only,
            "metric": "file-level hit@k over EXPECTED path substrings; MRR ranks",
        },
        "questions": QUESTIONS,
        "results": results,
    }
    (out_dir / "results.json").write_text(
        json.dumps(report, indent=2), encoding="utf-8"
    )

    lines = [
        "# Embedding retrieval probe",
        "",
        f"Project **{meta['project_name']}** · {meta['corpus_chunks']} chunks · "
        f"questions: {len(QUESTIONS)} · top_k: {args.top_k}",
        "",
        "Metric: file-level hit@k against the project's own source files",
        "(MRR rewards ranking the right file higher). Cost is docs/s on this",
        "machine — the other half of the decision.",
        "",
        "| Model | dim | hit@1 | hit@3 | hit@5 | MRR | docs/s |",
        "|---|---|---|---|---|---|---|",
    ]
    for r in results:
        lines.append(
            f"| {r['model']} | {r['dimensions']} | {r['hit@1']:.2f} | "
            f"{r['hit@3']:.2f} | {r['hit@5']:.2f} | {r['mrr']:.2f} | "
            f"{r['docs_per_second']:.1f} |"
        )
    lines += [
        "",
        "## Per-question first-relevant rank (5 = miss)",
        "",
        "| Question | " + " | ".join(r["model"] for r in results) + " |",
        "|---|" + "---|" * len(results),
    ]
    for i, entry in enumerate(QUESTIONS):
        cells = []
        for r in results:
            rank = r["per_question"][i]["first_relevant_rank"]
            cells.append(str(rank) if rank is not None else "5")
        lines.append(f"| {entry['q'][:60]} | " + " | ".join(cells) + " |")
    lines.append("")
    (out_dir / "REPORT.md").write_text("\n".join(lines), encoding="utf-8")

    print("\n==== SUMMARY (sorted by hit@5, then MRR) ====", flush=True)
    for r in results:
        print(
            f"{r['model']}: hit@1={r['hit@1']:.2f} hit@3={r['hit@3']:.2f} "
            f"hit@5={r['hit@5']:.2f} mrr={r['mrr']:.2f} dim={r['dimensions']} "
            f"{r['docs_per_second']:.1f} docs/s",
            flush=True,
        )
    print(f"[probe] done. out={out_dir}", flush=True)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
