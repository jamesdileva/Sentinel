"""Deterministic build/test/start command discovery.

Returns the command map described in docs/02 §3.5:
{"install", "startup", "build", "test", "deploy"}.

v1.17.7.5: ordered extractors — explicit manifests first (package.json,
pyproject.toml, requirements.txt, Makefile, Cargo.toml, gradle/maven
wrappers, dotnet, go.mod), then a README/docs scan that matches *known*
command spellings only (never arbitrary doc lines). The first confident hit
per key wins.
"""

import json
import os
import re
from pathlib import Path

_COMMAND_KEYS = ("install", "startup", "build", "test", "deploy")


def _read_json(path: Path) -> dict:
    try:
        return json.loads(path.read_text(encoding="utf-8", errors="replace"))
    except (json.JSONDecodeError, OSError, UnicodeDecodeError):
        return {}


def _read_text(path: Path) -> str:
    try:
        return path.read_text(encoding="utf-8", errors="replace")
    except OSError:
        return ""


def _from_package_json(root: Path) -> dict[str, str]:
    data = _read_json(root / "package.json")
    scripts: dict[str, str] = data.get("scripts", {}) or {}
    commands: dict[str, str] = {}
    if not scripts:
        return commands
    if (root / "pnpm-lock.yaml").exists():
        commands["install"] = "pnpm install"
    elif (root / "yarn.lock").exists():
        commands["install"] = "yarn install"
    elif (root / "bun.lockb").exists():
        commands["install"] = "bun install"
    else:
        commands["install"] = "npm install"
    commands["startup"] = scripts.get("dev") or scripts.get("start") or ""
    commands["build"] = scripts.get("build") or scripts.get("dist") or ""
    commands["test"] = scripts.get("test") or ""
    return commands


def _from_pyproject_toml(root: Path) -> dict[str, str]:
    text = _read_text(root / "pyproject.toml")
    commands: dict[str, str] = {}
    has_pytest = "[tool.pytest.ini_options]" in text or "pytest" in text
    if has_pytest:
        commands["test"] = "pytest"
    return commands


def _from_requirements(root: Path) -> dict[str, str]:
    if (root / "requirements.txt").exists():
        return {"install": "pip install -r requirements.txt"}
    return {}


def _from_makefile(root: Path) -> dict[str, str]:
    text = _read_text(root / "Makefile")
    if not text:
        return {}
    commands: dict[str, str] = {}
    if re.search(r"^build\s*:", text, re.MULTILINE):
        commands["build"] = "make build"
    elif re.search(r"^all\s*:", text, re.MULTILINE):
        commands["build"] = "make all"
    if re.search(r"^test\s*:", text, re.MULTILINE):
        commands["test"] = "make test"
    return commands


def _from_cargo(root: Path) -> dict[str, str]:
    if (root / "Cargo.toml").exists():
        return {"build": "cargo build", "test": "cargo test"}
    return {}


def _from_gradle(root: Path) -> dict[str, str]:
    wrapper = root / ("gradlew.bat" if os.name == "nt" else "gradlew")
    if wrapper.exists():
        name = wrapper.name
        return {"build": f"{name} build", "test": f"{name} test"}
    if (root / "build.gradle").exists() or (root / "build.gradle.kts").exists():
        return {"build": "gradle build", "test": "gradle test"}
    return {}


def _from_maven(root: Path) -> dict[str, str]:
    wrapper = root / ("mvnw.bat" if os.name == "nt" else "mvnw")
    if wrapper.exists():
        name = wrapper.name
        return {"build": f"{name} package", "test": f"{name} test"}
    if (root / "pom.xml").exists():
        return {"build": "mvn package", "test": "mvn test"}
    return {}


def _from_dotnet(root: Path) -> dict[str, str]:
    has_solution = bool(list(root.glob("*.sln")))
    has_project = bool(list(root.glob("*.csproj")) or list(root.glob("src/*.csproj")))
    if has_solution or has_project:
        return {"build": "dotnet build", "test": "dotnet test"}
    return {}


def _from_go(root: Path) -> dict[str, str]:
    if (root / "go.mod").exists():
        return {"build": "go build ./...", "test": "go test ./..."}
    return {}


def _from_cmake(root: Path) -> dict[str, str]:
    """CMake projects (v1.17.7.6): build via the canonical
    `cmake --build build`, which uses the cached generator (e.g.
    mingw32-make for algo-trader's `build/`) and re-runs configure
    automatically when CMakeLists.txt changes."""
    cmake_lists = root / "CMakeLists.txt"
    if not cmake_lists.exists():
        return {}
    commands: dict[str, str] = {}
    text = _read_text(cmake_lists)
    if re.search(r"enable_testing\s*\(|add_test\s*\(", text):
        commands["test"] = "ctest --test-dir build"
    commands["build"] = "cmake --build build"
    return commands


# --- README/docs discovery ---------------------------------------------------
#
# Many repos document their build command only in prose. We scan the docs for
# *known* command spellings (exact, word-bounded) and never invent commands —
# a sentence like "run make build first" is the only acceptable source.

_README_CANDIDATES = (
    "README.md",
    "readme.md",
    "README.MD",
    "README.txt",
    "README",
    "BUILDING.md",
    "docs/BUILDING.md",
    "docs/README.md",
    # v1.17.7.7: AGENTS.md is a common repo-convention doc. Unlike READMEs it
    # is prose-heavy and references commands mid-sentence, so only commands
    # inside fenced code blocks are accepted from it (see _from_readme).
    "AGENTS.md",
    "docs/AGENTS.md",
)

# Fenced code block body (```bash ... ```), for AGENTS.md scanning.
_FENCED_BLOCK = re.compile(r"^```.*?\n(.*?)^```", re.MULTILINE | re.DOTALL)

# Longest/specific spellings first so `./gradlew build` wins over
# `gradlew build` and `npm run build` over `npm build`.
_README_BUILD_COMMANDS = (
    "./gradlew.bat build",
    "./gradlew build",
    "gradlew build",
    "npm run build",
    "pnpm build",
    "yarn build",
    "npm build",
    "make build",
    "make all",
    "cargo build",
    "dotnet build",
    "mvn package",
    "./mvnw package",
    "mvnw package",
    "go build ./...",
    "python -m build",
    "pip install -e .",
    "npm run dist",
)

_README_TEST_COMMANDS = (
    "./gradlew test",
    "gradlew test",
    "npm run test",
    "npm test",
    "pnpm test",
    "yarn test",
    "pytest",
    "make test",
    "cargo test",
    "go test ./...",
    "dotnet test",
)

_README_INSTALL_COMMANDS = (
    "pip install -r requirements.txt",
    "pip install -e .",
    "pnpm install",
    "yarn install",
    "npm install",
    "poetry install",
    "uv sync",
)


def _find_known_command(text: str, whitelist: tuple[str, ...]) -> str:
    """First whitelisted command found as a standalone phrase."""
    for command in whitelist:
        pattern = re.compile(r"(?<![\w./-])" + re.escape(command) + r"(?![\w:-])")
        if pattern.search(text):
            return command
    return ""


def _from_readme(root: Path) -> dict[str, str]:
    commands: dict[str, str] = {}
    text = ""
    candidate = ""
    for candidate in _README_CANDIDATES:
        text = _read_text(root / candidate)
        if text:
            break
    if not text:
        return commands
    if "agents.md" in candidate.lower():
        # v1.17.7.7: AGENTS.md prose mentions commands mid-sentence
        # (Sentinel's own file says "`pytest` in `backend/`") — a whitelist
        # scan of the whole file would mint wrong commands. Only commands
        # written as fenced code blocks are real instructions.
        text = "\n".join(block for block in _FENCED_BLOCK.findall(text))
    if "build" not in commands:
        commands["build"] = _find_known_command(text, _README_BUILD_COMMANDS)
    if "test" not in commands:
        commands["test"] = _find_known_command(text, _README_TEST_COMMANDS)
    if "install" not in commands:
        commands["install"] = _find_known_command(text, _README_INSTALL_COMMANDS)
    return commands


def _from_pytest_convention(root: Path) -> dict[str, str]:
    """v1.17.7.7: a repo with a root-level `tests/` directory and at least
    one root-level Python file is a pytest project by convention — a
    deterministic signal, not prose guessing (Rule 3). Manifest-driven
    extractors run first and win; this only fills the `test` gap."""
    if not (root / "tests").is_dir():
        return {}
    if not any(entry.is_file() and entry.suffix == ".py" for entry in root.iterdir()):
        return {}
    return {"test": "pytest"}


# Ordered by confidence: explicit manifests beat Makefile beats docs prose.
_EXTRACTORS = (
    _from_package_json,
    _from_pyproject_toml,
    _from_requirements,
    _from_makefile,
    _from_cargo,
    _from_gradle,
    _from_maven,
    _from_dotnet,
    _from_go,
    _from_cmake,
    _from_readme,
    _from_pytest_convention,
)


def extract_build_commands(path: str | Path) -> dict[str, str]:
    """Discover install/startup/build/test commands for a project.

    Deterministic: ordered extractors, first confident hit per key wins.
    """
    root = Path(path)
    commands: dict[str, str] = {}
    for extractor in _EXTRACTORS:
        for key, value in extractor(root).items():
            # Empty results never claim a key — an earlier extractor that
            # found nothing must not block a later, confident one.
            if value:
                commands.setdefault(key, value)

    if "install" not in commands:
        if (root / "pyproject.toml").exists():
            commands["install"] = "pip install -e ."
    return {key: commands.get(key, "") for key in _COMMAND_KEYS}
