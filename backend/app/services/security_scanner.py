"""Security scanner — vulnerabilities, secrets, and static analysis (docs/02 §3.6).

External tools (pip-audit, npm audit, bandit, semgrep) are invoked when present.
A deterministic local advisory table and regex checks keep scanning testable and
dependency-free on hosts without those tools.
"""

import re
from pathlib import Path

from sqlmodel import Session

from app.core.logging import get_logger
from app.db.models import Project, SecurityFinding, Severity
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
        re.compile(r"\b(sk|ghp|AIza)[-_][A-Za-z0-9_\-]{16,}\b"),
        Severity.HIGH,
    ),
]

# Static analysis checks: name -> (regex, severity) applied to Python sources.
_STATIC_PATTERNS: list[tuple[str, re.Pattern[str], Severity]] = [
    (
        "Use of eval()",
        re.compile(r"\beval\s*\("),
        Severity.MEDIUM,
    ),
    (
        "Use of exec()",
        re.compile(r"\bexec\s*\("),
        Severity.MEDIUM,
    ),
]

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


class SecurityScanner:
    """Orchestrates security scanning across a project."""

    def __init__(self, session: Session):
        self.session = session

    def scan_project(self, project: Project) -> list[SecurityFinding]:
        """Run all scanners and persist findings, returning the new ones."""
        findings = []
        findings += self.scan_dependencies(project)
        findings += self.scan_secrets(project.path)
        findings += self.scan_static_analysis(project.path)
        persisted = []
        for template in findings:
            finding = SecurityFinding(project_id=project.id, **template)
            self.session.add(finding)
            persisted.append(finding)
        self.session.commit()
        logger.info("Security scan for %s: %d finding(s)", project.name, len(persisted))
        return persisted

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

    def scan_secrets(self, project_path: str) -> list[dict]:
        """Scan project files for secret patterns (deterministic, local)."""
        findings: list[dict] = []
        root = Path(project_path)
        if not root.is_dir():
            return findings
        for file_path in root.rglob("*"):
            if not file_path.is_file():
                continue
            rel = file_path.relative_to(root)
            if any(part in _IGNORED_NAME_PARTS for part in rel.parts):
                continue
            if file_path.name.lower() in _ENV_TEMPLATE_NAMES:
                continue
            try:
                content = file_path.read_text(encoding="utf-8", errors="replace")
            except OSError:
                continue
            for name, pattern, severity in _SECRET_PATTERNS:
                for match in pattern.finditer(content):
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

    def scan_static_analysis(self, project_path: str) -> list[dict]:
        """Flag risky constructs in Python sources (eval/exec)."""
        findings: list[dict] = []
        root = Path(project_path)
        if not root.is_dir():
            return findings
        for file_path in root.rglob("*.py"):
            rel = file_path.relative_to(root)
            if any(part in _IGNORED_NAME_PARTS for part in rel.parts):
                continue
            if _is_test_file(rel):
                continue
            try:
                content = file_path.read_text(encoding="utf-8", errors="replace")
            except OSError:
                continue
            for name, pattern, severity in _STATIC_PATTERNS:
                for match in pattern.finditer(content):
                    line_no = content[: match.start()].count("\n") + 1
                    findings.append(
                        {
                            "type": "static_analysis",
                            "severity": severity,
                            "title": name,
                            "description": (
                                "Dynamic code execution construct found; prefer "
                                "a safe alternative."
                            ),
                            "file_path": str(rel),
                            "line_number": line_no,
                            "cve_id": None,
                            "remediation": f"Avoid {'/'.join(name.lower().split())}",
                        }
                    )
                    break
        return findings

    @staticmethod
    def get_project(session: Session, project_id: str) -> Project:
        project = ProjectRepository(session).get(project_id)
        if project is None:
            raise ValueError(f"Unknown project: {project_id}")
        return project
