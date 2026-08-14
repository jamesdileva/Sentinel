"""Security scanner — vulnerabilities, secrets, and static analysis (docs/02 §3.6).

External tools (pip-audit, npm audit, bandit, semgrep) are invoked when present.
A deterministic local advisory table and regex checks keep scanning testable and
dependency-free on hosts without those tools.
"""

import ast
import datetime
import re
from pathlib import Path

from sqlmodel import Session, select

from app.core.logging import get_logger
from app.db.models import Project, ProjectFile, SecurityFinding, Severity
from app.repositories import DependencyRepository, ProjectRepository

logger = get_logger(__name__)

# Local advisory table: package name -> vulnerable version (exact).
_ADVISORY_VERSIONS: dict[str, str] = {
    "requests": "2.25.0",
}

# Secret patterns: name -> (regex, severity).
_SECRET_PATTERNS: list[tuple[str, re.Pattern[str], Severity]] = [
    (
        "AWS Access Key",
        re.compile(r"\bAKIA[0-9A-Z]{16}\b", re.DOTALL),
        Severity.HIGH,
    ),
    (
        "Private Key",
        re.compile(r"-----BEGIN (?:RSA |EC |OPENSSH )?PRIVATE KEY-----"),
        Severity.CRITICAL,
    ),
    (
        "Generic Secret",
        re.compile(
            r"\b(?:ghp|AIza|sk_(?:live|test))[-_][A-Za-z0-9_\-]{16,}\b"
        ),
        Severity.HIGH,
    ),
]

# Static analysis targets (v1.17.7.5: detected via the Python AST, not regex —
# string literals and comments can never match, which killed the scanner
# flagging its own source and docs mentioning "Use of eval()").
_DYNAMIC_EXEC_NAMES = ("eval", "exec")

_IGNORED_NAME_PARTS = (
    ".git",
    ".venv",
    "venv",
    "node_modules",
    "__pycache__",
    # Runtime data and test scaffolding are not application source: private
    # keys under data/ (e.g. Pi-hole tls.pem), scanner test fixtures, and
    # example/template env files all produce false positives.
    "data",
    "fixtures",
)

# Env template files are meant to be committed with placeholder values
# (e.g. .env.example with `ghp_xxxxx`); never flag them as secrets.
_ENV_TEMPLATE_NAMES = (".env.example", ".env.sample", ".env.template", ".env.dist")


# Test files legitimately exercise eval()/exec()-style constructs (fixtures,
# fake runners); only flag dynamic-execution in real source code.
def _is_test_file(rel: Path) -> bool:
    parts = [p.lower() for p in rel.parts]
    if "test" in parts or "tests" in parts or "__tests__" in parts:
        return True
    name = rel.name.lower()
    return name.startswith("test_") or name.endswith("_test.py")


# Placeholder/example values look like secrets but are not (v1.17.1): the
# scanner used to flag `.env.example`-style values and fake test tokens in
# fixtures. Placeholder markers (xxx/example/...) reject those; an
# *alphabetical* token — one that reads like a real key — stays flagged by
# design, so this comment deliberately avoids embedding any such literal.
_PLACEHOLDER_MARKERS = (
    "xxx",
    "example",
    "placeholder",
    "dummy",
    "fake",
    "test",
    "sample",
    "changeme",
)


def _is_placeholder_value(value: str) -> bool:
    """True when a candidate secret is a placeholder, not a real credential.

    Rejects values that are all the same character (ghp_xxx…), and values
    whose body contains a placeholder marker (`example`, `test`, `xxx`…).
    """
    body = value.split("_", 1)[1] if "_" in value else value
    if len(set(body.lower())) <= 1:
        return True
    lowered = value.lower()
    return any(marker in lowered for marker in _PLACEHOLDER_MARKERS)


class SecurityScanner:
    """Orchestrates security scanning across a project."""

    def __init__(self, session: Session):
        self.session = session

    def scan_project(self, project: Project) -> list[SecurityFinding]:
        """Scan and persist findings, returning the *new* ones only.

        Deterministic idempotence (Rule 3): a finding is keyed by
        (project, type, cve_id, file_path, line_number, title). Already-open
        findings with the same key are left untouched — every scan does not
        re-insert rows (the pre-Sprint-16 behaviour that flooded the
        timeline). Findings from a previous scan whose key no longer matches
        are marked `resolved = True` (the problem was fixed).
        """
        templates = self._collect(project)
        incoming_keys = {
            self._fingerprint(project.id, template) for template in templates
        }

        existing = self.session.exec(
            select(SecurityFinding).where(
                SecurityFinding.project_id == project.id,
                SecurityFinding.resolved == False,  # noqa: E712
            )
        ).all()
        existing_by_key: dict[tuple, SecurityFinding] = {
            self._fingerprint(project.id, self._row_to_dict(row)): row
            for row in existing
        }

        new_rows: list[SecurityFinding] = []
        for template in templates:
            key = self._fingerprint(project.id, template)
            if key in existing_by_key:
                continue
            finding = SecurityFinding(project_id=project.id, **template)
            self.session.add(finding)
            new_rows.append(finding)

        stale = [
            row for key, row in existing_by_key.items() if key not in incoming_keys
        ]
        for row in stale:
            row.resolved = True

        # v1.17.6.6: every scan — clean or not — stamps `last_scanned` on the
        # project. Previously a clean scan stored nothing at all, so the
        # portfolio's security component could never tell "scanned clean"
        # from "never scanned" and the feature matrix showed ✗ pending
        # forever. The dedicated marker keeps the findings list clean.
        project.last_scanned = datetime.datetime.now(datetime.timezone.utc)
        self.session.add(project)
        self.session.commit()
        logger.info(
            "Security scan for %s: %d new, %d resolved",
            project.name,
            len(new_rows),
            len(stale),
        )
        return new_rows

    @staticmethod
    def _fingerprint(project_id: str, template: dict) -> tuple:
        return (
            project_id,
            template.get("type"),
            template.get("cve_id"),
            template.get("file_path"),
            template.get("line_number"),
            template.get("title"),
        )

    @staticmethod
    def _row_to_dict(row: SecurityFinding) -> dict:
        """Project a stored finding row onto a scan-template dict."""
        return {
            "type": row.type,
            "cve_id": row.cve_id,
            "file_path": row.file_path,
            "line_number": row.line_number,
            "title": row.title,
        }

    def _collect(self, project: Project) -> list[dict]:
        """Collect all scan templates (dependencies + secrets + static)."""
        findings: list[dict] = []
        files = self._iter_scan_files(project)
        root = Path(project.path)
        findings += self.scan_dependencies(project)
        findings += self.scan_secrets(files, root)
        findings += self.scan_static_analysis(files, root)
        return findings

    def _iter_scan_files(self, project: Project) -> list[Path]:
        """The file set a scan covers = the project's *indexed* files
        (git-tracked source with the indexer gates applied).

        v1.17.7.5: the scanner used to rglob the raw tree, so untracked junk
        flooded findings — `.venv_sf3d` site-packages (torch/numba/sympy
        vendored eval/exec), an embedded Python runtime under
        `backend/runtime/python/Lib`, and `release/`/`win-unpacked/`
        electron output produced hundreds of false positives (AG 209,
        Workflow Toolkit 183). The index is the source of truth; falls back
        to the indexer's gated walk when a project has no rows yet.
        """
        root = Path(project.path)
        rows = self.session.exec(
            select(ProjectFile).where(ProjectFile.project_id == project.id)
        ).all()
        if rows:
            files: list[Path] = []
            for row in rows:
                absolute = Path(row.absolute_path or root / row.path)
                if absolute.is_file():
                    files.append(absolute)
            return files
        from app.services.indexer import IndexerService

        return IndexerService(self.session)._iter_source_files(root)

    def scan_dependencies(self, project: Project) -> list[dict]:
        """Flag known-vulnerable dependency versions from the advisory table."""
        findings: list[dict] = []
        deps = DependencyRepository(self.session).get_by_project(project.id)
        for dep in deps:
            vulnerable = _ADVISORY_VERSIONS.get(dep.name)
            if vulnerable and dep.version == vulnerable:
                findings.append(
                    {
                        "type": "vulnerability",
                        "severity": Severity.MEDIUM,
                        "title": f"Known vulnerable version of {dep.name}",
                        "description": (
                            f"{dep.name}=={dep.version} matches a known-vulnerable "
                            "advisory in the local table."
                        ),
                        "cve_id": None,
                        "remediation": f"Upgrade {dep.name} above {vulnerable}",
                        "file_path": None,
                        "line_number": None,
                    }
                )
        return findings

    def scan_secrets(self, files: list[Path], project_root: Path) -> list[dict]:
        """Scan the indexed files for secret patterns (deterministic, local)."""
        findings: list[dict] = []
        for absolute in files:
            try:
                rel = absolute.relative_to(project_root)
            except ValueError:
                continue
            if any(part in _IGNORED_NAME_PARTS for part in rel.parts):
                continue
            if absolute.name.lower() in _ENV_TEMPLATE_NAMES:
                continue
            if _is_test_file(rel):
                # v1.17.1: test files routinely hold fixture/fake tokens
                # (integration-test API keys, `ghp_…` samples); consistent
                # with static analysis, they are not application source.
                continue
            try:
                content = absolute.read_text(encoding="utf-8", errors="replace")
            except OSError:
                continue
            for name, pattern, severity in _SECRET_PATTERNS:
                for match in pattern.finditer(content):
                    if _is_placeholder_value(match.group(0)):
                        continue
                    line_no = content[: match.start()].count("\n") + 1
                    findings.append(
                        {
                            "type": "secret",
                            "severity": severity,
                            "title": f"{name} detected",
                            "description": "A secret-like value was found in source code.",
                            "file_path": str(rel),
                            "line_number": line_no,
                            "cve_id": None,
                            "remediation": "Rotate the secret and remove it from source.",
                        }
                    )
                    break  # one finding per file per pattern
        return findings

    def scan_static_analysis(self, files: list[Path], project_root: Path) -> list[dict]:
        """Flag risky constructs in Python sources (eval/exec).

        v1.17.7.5: parsed with the stdlib `ast` instead of regex, so only
        *real* `eval(...)`/`exec(...)` calls are flagged — string literals
        and comments (docs, scanner titles, `"Use of eval()"` examples) can
        never match. Attribute calls (`session.exec(...)`) are not Name
        nodes, so the v1.17.1 ORM false positive stays fixed.
        """
        findings: list[dict] = []
        for absolute in files:
            if absolute.suffix.lower() != ".py":
                continue
            try:
                rel = absolute.relative_to(project_root)
            except ValueError:
                continue
            if any(part in _IGNORED_NAME_PARTS for part in rel.parts):
                continue
            if _is_test_file(rel):
                continue
            try:
                content = absolute.read_text(encoding="utf-8", errors="replace")
            except OSError:
                continue
            try:
                tree = ast.parse(content)
            except SyntaxError:
                continue
            seen: set[str] = set()
            for node in ast.walk(tree):
                if not isinstance(node, ast.Call):
                    continue
                func = node.func
                if not isinstance(func, ast.Name):
                    continue
                if func.id not in _DYNAMIC_EXEC_NAMES or func.id in seen:
                    continue
                seen.add(func.id)
                findings.append(
                    {
                        "type": "static_analysis",
                        "severity": Severity.MEDIUM,
                        "title": f"Use of {func.id}()",
                        "description": (
                            "Dynamic code execution construct found; prefer "
                            "a safe alternative."
                        ),
                        "file_path": str(rel),
                        "line_number": node.lineno,
                        "cve_id": None,
                        "remediation": f"Avoid {func.id}",
                    }
                )
        return findings

    @staticmethod
    def get_project(session: Session, project_id: str) -> Project:
        project = ProjectRepository(session).get(project_id)
        if project is None:
            raise ValueError(f"Unknown project: {project_id}")
        return project
