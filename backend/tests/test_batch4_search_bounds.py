"""Audit Batch 4 — hybrid lexical+semantic search, endpoint bounds, and the
refresh endpoint contract. Pure functions where possible (Rule 3)."""

from app.services.rag_service import (
    RagResult,
    _lexical_bonus,
    _lexical_tokens,
    _rerank_lexical,
)


def _hit(distance: float, content: str, file_path: str | None = "src/app.py"):
    return RagResult(
        content=content,
        source="file_summaries",
        project_id="p1",
        file_path=file_path,
        distance=distance,
    )


# --- lexical tokenisation --------------------------------------------------


def test_lexical_tokens_normalise_identifier_forms():
    """`BuildRunner`, `build_runner` and `buildrunner` must all reduce to the
    same token set — the forms a developer alternates between when asking and
    when writing code. Paths split on `/` so a question about either segment
    matches the endpoint that owns it (the audit's point)."""
    asked = _lexical_tokens("Where is BuildRunner defined?")
    assert "buildrunner" in asked
    assert asked == _lexical_tokens("build_runner is defined where")
    assert _lexical_tokens("BuildRunner") == _lexical_tokens("build_runner")
    assert "buildrunner" in _lexical_tokens("BuildRunner")
    assert _lexical_tokens("/observatory/galaxy") == {"observatory", "galaxy"}
    assert _lexical_tokens("SENTINEL_OLLAMA_HOST") == {
        "sentinel",
        "ollama",
        "host",
        "sentinelollamahost",
    }
    # Pure noise (words under three characters) never becomes a token.
    assert _lexical_tokens("is it a or an of") == set()


def test_path_tokens_do_not_fuse_the_extension():
    assert _lexical_tokens("src/build_runner.py") == {
        "src",
        "build",
        "runner",
        "buildrunner",
    }


def test_lexical_bonus_is_bounded_and_zero_without_evidence():
    zero = _lexical_bonus(set(), "anything at all", "src/app.py")
    assert zero == 0.0
    plain = _lexical_bonus({"buildrunner"}, "nothing relevant here", "x.py")
    assert plain == 0.0
    full = _lexical_bonus({"buildrunner"}, "class BuildRunner:", "src/build_runner.py")
    assert 0.0 < full <= 0.05 + 0.03 + 0.02


def test_rerank_promotes_the_exact_identifier_without_changing_distance():
    """The audit's hybrid score: the chunk mentioning the exact term outranks
    a semantically nearer one, but its reported distance stays the vector
    truth (the relevance floor still judges raw evidence)."""
    hits = [
        (0.10, _hit(0.10, "unrelated plumbing code", "src/util.py")),
        (0.12, _hit(0.12, "class BuildRunner: runs builds", "src/build_runner.py")),
    ]
    ordered = _rerank_lexical("where is BuildRunner", hits)
    assert ordered[0][1].content.startswith("class BuildRunner")
    assert ordered[0][0] == 0.12  # raw distance untouched
    assert ordered[1][0] == 0.10


def test_rerank_is_stable_on_ties():
    hits = [
        (0.10, _hit(0.10, "plain code", "a.py")),
        (0.10, _hit(0.10, "other code", "b.py")),
    ]
    ordered = _rerank_lexical("zzz-nothing-matches", hits)
    assert [r.file_path for _, r in ordered] == ["a.py", "b.py"]


# --- endpoint bounds (B4) --------------------------------------------------


def test_timeline_rejects_an_absurd_window(client):
    response = client.get("/api/v1/observatory/timeline", params={"days": 99999})
    assert response.status_code == 422


def test_timeline_rejects_a_negative_offset(client):
    response = client.get("/api/v1/observatory/timeline", params={"offset": -1})
    assert response.status_code == 422


def test_timeline_accepts_the_documented_maximum(client):
    response = client.get("/api/v1/observatory/timeline", params={"days": 3650})
    assert response.status_code == 200


def test_chat_history_rejects_an_absurd_limit(client, tmp_db):
    response = client.get("/api/v1/rag/chat/__all__", params={"limit": 99999})
    assert response.status_code == 422


def test_best_candidates_rejects_an_impossible_score_floor(client):
    response = client.get(
        "/api/v1/portfolio/best-candidates", params={"min_score": 500}
    )
    assert response.status_code == 422
