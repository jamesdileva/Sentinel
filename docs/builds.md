# Project Builds — Recipe Reference (docs/builds.md)

Deterministic build/test/start/install recipes for every project Sentinel
indexes (v1.17.8.0). Commands are **discovered, never guessed**: the ordered
extractors in `backend/app/utils/command_extractor.py` read manifests
(package.json, pyproject.toml, requirements.txt, Makefile, Cargo.toml,
gradle/maven wrappers, dotnet, go.mod, CMakeLists.txt), then subdir
manifests (`renderer/`, `frontend/`, `backend/`, … prefixed `cd <dir> &&`),
then code-defined CLIs (argparse `gui`/`web` subcommands; `uvicorn main:app`
entry docstrings) and only then known spellings in README/docs. The first
confident hit per key wins.

- A project whose build command is unknown records a **skipped** build
  (`success=None`), never a fake pass (v1.17.7.5).
- If a stored command is stale/empty, the runner re-discovers at build time
  (v1.17.7.6), so new extractors take effect without re-indexing.
- Portfolio build points require a discovered command; the runtime fallback
  keeps the matrix honest too.
- All commands run with `cwd` = the project root via `run_command` (bounded
  timeout, captured output; PATH inherited — msys2 `mingw32-make`/`cmake`
  at `C:\msys64\mingw64\bin` are on PATH on the desktop).
- **build→open (v1.17.8.0)**: Run Build launches the `startup` command
  detached after a green build — or when no build is needed ("Build not
  needed — this project has no compile step."). The app keeps running (no
  command timeout) and appends to `data/logs/apps/<name>.log`, launched
  through the repo's own venv interpreter when it has one. A failed build
  never opens the app; only the user's click triggers a launch (Rule 2).

## Recipe table (all 21 projects)

| Project | Path | Language/Framework | install | build | test | startup |
|---------|------|--------------------|---------|-------|------|---------|
| AG | `Projects\AG` | python | — | — | `"C:\Users\j\Projects\AG\.venv_sf3d\Scripts\python.exe" -m pytest` | `python -m rigging_engine.main gui` |
| Airadio | `Projects\airadio` | javascript | `npm install` | `npm run build --workspace=apps/desktop` | — | `npm run dev --workspace=apps/desktop` |
| Algo Trader | `Projects\ALGO-TRADER` | C++ (CMake; indexer says typescript via `web/`) | — | `cmake --build build` | — | — |
| Card Game | `Projects\Card-Game` | javascript | — | — | — | — |
| CG | `Projects\CG` | javascript/electron + python | `cd renderer && npm install` | `cd renderer && npm run build` | `cd backend && "C:\Users\j\Projects\CG\venv\Scripts\python.exe" -m pytest` | `cd renderer && npm run start` |
| Cse455 (jamesdileva) | `Projects\jamesdileva\cse455` | gradle | — | `gradlew.bat build` | `gradlew.bat test` | — |
| Cse455 (juduncan) | `Projects\juduncan\cse455` | gradle | — | `gradlew.bat build` | `gradlew.bat test` | — |
| Demake Engine | `Projects\demake-engine` | python/fastapi | `pip install -r requirements.txt` | — | — | `cd backend && uvicorn main:app --reload` |
| Dinner Menu Generator | `Projects\dinner-menu-generator` | javascript/flask | `pip install -r requirements.txt` | `npm run build` | `pytest` | — |
| Finsight | `Projects\FinSight` | javascript/electron | `npm install` | — | `echo "Error: no test specified" && exit 1` *(package.json default)* | `electron .` |
| HFT-Order-Book | `Projects\HFT-Order-Book` | C++ (CMake) | — | `cmake --build build` | — | — |
| jamesdileva.github.io | `Projects\jamesdileva\jamesdileva.github.io` | html | — | — | — | — |
| jamesdileva.github.io-FinSight | `Projects\jamesdileva.github.io-FinSight` | html | — | — | — | — |
| Khd4 | `Projects\khd4` | dotnet | — | `dotnet build` | `dotnet test` | — |
| MLBattles | `Projects\MLBattles` | python | `pip install -r requirements.txt` | — | — | — |
| MM | `Projects\jamesdileva\MM` | unknown | — | — | — | — |
| Python Projects | `Projects\Python Projects` | python | — | — | — | — |
| Sentinel | `Projects\sentinel` | python | `cd frontend && npm install` | `cd frontend && npm run build` | `cd frontend && npm run test` | `cd frontend && npm run dev` |
| TV-Scheduler | `Projects\TV-Scheduler` | javascript/electron | `npm install` | `npm run build --prefix frontend` | `npm run test --prefix backend && npm run test --prefix frontend` | `concurrently "npm run backend" "npm run frontend" "wait-on http://localhost:5173 && npm run electron"` |
| utilitytool | `Projects\jamesdileva\utilitytool` | unknown | `npm install` | — | — | — |
| WorkFlow-Toolkit | `Projects\WorkFlow-Toolkit` | javascript/electron | `npm install` | `npm --prefix frontend run build` | `npm --prefix frontend run test` | `concurrently "npm --prefix frontend run dev" "cd backend && python -m uvicorn app.main:app --reload"` |

`—` = no command discovered (project shows **skipped** builds / ✗ matrix
cells). The matrix build cell flips to ✓ only for rows with a build command.

## C++ / CMake projects (deep-dive)

Both CMake projects were configured once with the MinGW Makefiles generator
and build into a gitignored `build/` directory. Sentinel's build command is
`cmake --build build`, which reuses the cached generator (runs
`mingw32-make` under the hood) and re-runs configure automatically when
`CMakeLists.txt` changes — no manual steps between builds.

### Algo Trader (`Projects\ALGO-TRADER`)

- Toolchain: msys2 MinGW-w64 (`C:\msys64\mingw64\bin\g++.exe`, `cmake.exe`,
  `mingw32-make.exe`), C++17, links OpenSSL + sqlite3 + ws2_32/crypt32.
- Configure once (already done — `build/` exists):
  `cmake -S . -B build -G "MinGW Makefiles"` (from the repo root; cmake
  defaults to the msys2 generator once the cache exists).
- **Migration pitfall (desktop, v1.17.7.3)**: the pre-existing `build/`
  caches were created when the repos lived in the home dir
  (`c:/Users/j/algo-trader`), so `cmake --build build` fails with
  "CMakeCache.txt directory is different than the directory where
  CMakeCache.txt was created". Fix once: delete `build/` and re-run the
  configure command above (regenerates Makefiles; `trader.exe` rebuilds).
- Build: `cmake --build build` → produces `build\trader.exe` and
  `build\backtester.exe`.
- `CMakeLists.txt` declares **two targets**:
  - `trader` — the live trading app (`src/main.cpp` + `src/Database.cpp`),
    the actual "Algo Trader" project.
  - `backtester` — a **separate strategy-testing executable**
    (`src/backtester.cpp` + `src/Database.cpp`). It is a tool *within* the
    repo, **not** its own Sentinel project; a build builds both.
- No CTest tests defined → test command stays empty.
- Runtime data: `config/settings.json`, `data\algo_trader.db` (both
  gitignored); output trades land in `traderoutput\`.

### HFT-Order-Book (`Projects\HFT-Order-Book`)

- Same CMake layout (`build/` pre-configured, MinGW Makefiles, cpp-httplib
  vendored under `src\httplib.h`).
- Build: `cmake --build build`. No CTest tests defined.

## Notes for agents

- When adding a build recipe for a new repo, extend `command_extractor.py`
  (one extractor per manifest type, ordered before the README scan) and add
  parametrized tests in `backend/tests/test_indexer.py`.
- Keep this doc free of anything that looks like a credential — it is
  security-scanned like all indexed files.
- Re-run `scripts/build.py --dist` and restart the server before expecting
  live builds to pick up extractor changes.