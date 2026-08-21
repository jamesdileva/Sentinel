"""WorkFlow-Toolkit tester — deep E2E over the FastAPI backend covering all
four workflow templates plus the repo's own pytest suite.

Verified ground truth (2026-08-15/16):
- Backend: `cd backend && python -m uvicorn app.main:app` on :8000 (default;
  the same port CG and Demake use, so a tester run while another 8000-bound
  app is up reports investigate honestly). No venv — the repo ships a bundled
  runtime at `backend/runtime/python/python.exe`; the tester prefers it and
  falls back to PATH `python`.
- v1.17.12.1: Sentinel's own run.py sets PYTHONPATH=<sentinel>/backend, and
  the tester child inherits it — uvicorn then imports *Sentinel's* `app`
  package (sqlmodel ModuleNotFoundError) instead of the WFT app. The launch
  env overlay therefore forces PYTHONPATH="" so `app.main` resolves inside
  the WFT checkout.
- No auth and no UI needed — every step below is plain REST (verified against
  backend/app/api/{projects,datasets,payroll,reports,workflows}.py).
- Fixtures `backend/tests/fixtures/*` are engineered per tool: payroll_issues.csv
  (missing/negative/excessive hours), customers_dupes.csv (duplicates),
  customers_v1/v2.csv (same records, different values), sales_orders.csv
  (KPI/chart material).
- Workflow execution is async (BackgroundTasks): execute returns a "Pending"
  run, so the tester polls GET /api/workflows/runs/{id} to a terminal state.
  `WorkflowExecuteRequest` carries `second_dataset_id` for Dataset Comparison;
  every template ends with a report (PDF or Excel) recorded via
  `output_report_id` (migration 4e6a9c2d8f31).
- Report downloads serve by format: pdf -> application/pdf, excel ->
  application/vnd.openxmlformats-officedocument.spreadsheetml.sheet.
- The repo's own suite (backend/tests, incl. the fixture-based data tests)
  passes under the runtime python: 838 tests, ~12 s.
"""

import time
import uuid
from pathlib import Path

import httpx

from app.testers import Tester
from app.testers._helpers import (
    TesterAssertionError,
    TesterContext,
    TesterEnvError,
    TesterTimeoutError,
)

PORT = "http://127.0.0.1:8000"
POLL_STEP_S = 5
MAX_WAIT_S = 180

FIXTURES = Path("backend") / "tests" / "fixtures"


def _interpreter(project_root: Path) -> str:
    runtime = project_root / "backend" / "runtime" / "python" / "python.exe"
    return f'"{runtime}"' if runtime.exists() else "python"


def _backend_command(project_root: Path) -> str:
    return f"cd backend && {_interpreter(project_root)} -m uvicorn app.main:app"


def _pytest_command(project_root: Path) -> str:
    return f"cd backend && {_interpreter(project_root)} -m pytest tests -q"


def _import_dataset(
    ctx: TesterContext, headers: dict, project_id: int, name: str
) -> int:
    fixture = Path(ctx.project.path) / FIXTURES / name
    if not fixture.exists():
        raise TesterEnvError(f"Fixture missing: {fixture}")
    with open(fixture, "rb") as fh:
        upload = httpx.post(
            f"{PORT}/api/datasets/import",
            data={"project_id": str(project_id)},
            files={"file": (name, fh, "text/csv")},
            timeout=60,
        )
    if upload.status_code != 200:
        raise TesterAssertionError(
            f"dataset import ({name}) -> {upload.status_code}, expected 200"
        )
    dataset_id = upload.json().get("id")
    if not dataset_id:
        raise TesterAssertionError(f"import response for {name} lacks dataset id")
    ctx.checkpoint(f"imported {name} -> dataset {dataset_id}")
    return dataset_id


def _resolve_template(ctx: TesterContext, category: str, name: str) -> int:
    templates = httpx.get(
        f"{PORT}/api/workflows/templates",
        params={"category": category},
        timeout=30,
    )
    if templates.status_code != 200:
        raise TesterAssertionError(
            f"workflow templates -> {templates.status_code}, expected 200"
        )
    template = next((t for t in templates.json() if t.get("name") == name), None)
    if template is None:
        raise TesterAssertionError(f"{name!r} template not found by name")
    ctx.checkpoint(f"{name} template resolved")
    return template["id"]


def _execute_template(
    ctx: TesterContext,
    headers: dict,
    project_id: int,
    template_id: int,
    dataset_id: int | None,
    second_dataset_id: int | None = None,
) -> dict:
    execute = httpx.post(
        f"{PORT}/api/workflows/templates/{template_id}/execute",
        json={
            "project_id": project_id,
            "dataset_id": dataset_id,
            "second_dataset_id": second_dataset_id,
        },
        headers=headers,
        timeout=60,
    )
    if execute.status_code != 200:
        raise TesterAssertionError(
            f"workflow execute -> {execute.status_code}, expected 200"
        )
    run_id = execute.json().get("id") or execute.json().get("run_id")
    if not run_id:
        raise TesterAssertionError("workflow execute response lacks run id")
    ctx.checkpoint(f"workflow run started: {run_id}")
    return _poll_run(run_id)


def _poll_run(run_id: int) -> dict:
    run_status = None
    deadline = time.time() + MAX_WAIT_S
    while time.time() < deadline:
        run_resp = httpx.get(f"{PORT}/api/workflows/runs/{run_id}", timeout=30)
        if run_resp.status_code != 200:
            raise TesterAssertionError(
                f"workflow run poll -> {run_resp.status_code}, expected 200"
            )
        run_status = run_resp.json().get("status")
        if run_status in ("Completed", "Failed"):
            break
        time.sleep(POLL_STEP_S)
    if run_status == "Failed":
        raise TesterAssertionError(
            f"workflow run failed: {run_resp.json().get('error', 'see log')}"
        )
    if run_status != "Completed":
        raise TesterTimeoutError(
            f"workflow run not completed after {MAX_WAIT_S}s (status={run_status!r})"
        )
    return run_resp.json()


def _assert_completed_with_report(ctx: TesterContext, run: dict) -> int:
    output_report_id = run.get("output_report_id")
    if not output_report_id:
        raise TesterAssertionError("completed run lacks output_report_id")
    ctx.checkpoint(f"workflow run completed with report {output_report_id}")
    return output_report_id


def _assert_report_download(
    ctx: TesterContext, report_id: int, media_hint: str
) -> None:
    download = httpx.get(f"{PORT}/api/reports/{report_id}/download", timeout=60)
    if download.status_code != 200:
        raise TesterAssertionError(
            f"report download -> {download.status_code}, expected 200"
        )
    content_type = download.headers.get("content-type", "")
    if media_hint not in content_type:
        raise TesterAssertionError(
            f"report download content-type: {content_type!r} (wanted {media_hint!r})"
        )
    ctx.checkpoint(f"report download serves {media_hint}")


def run(ctx: TesterContext) -> None:
    root = Path(ctx.project.path)

    ctx.launch(_backend_command(root), env={"PYTHONPATH": ""})
    # Deterministic readiness (live-fix 2026-08-18): the app log is shared
    # with the auto-launched window's stdout and uvicorn's file output is
    # block-buffered — a log wait can time out on a healthy backend. The
    # health endpoint is the contract (Rule 3: determinism over generation).
    ctx.http(
        "GET",
        f"{PORT}/health",
        expect_body="healthy",
        timeout_s=5,
        retries=20,
        retry_delay_s=3,
    )
    ctx.checkpoint("backend up on :8000")

    headers = {"Content-Type": "application/json"}
    name = f"sentinel-tester-{uuid.uuid4().hex[:8]}"

    create = httpx.post(
        f"{PORT}/api/projects/",
        json={"name": name, "description": "sentinel tester project"},
        headers=headers,
        timeout=30,
    )
    if create.status_code != 200:
        raise TesterAssertionError(
            f"create project -> {create.status_code}, expected 200"
        )
    project_id = create.json().get("id")
    if not project_id:
        raise TesterAssertionError("create project response lacks id")
    ctx.checkpoint(f"project created: {name}")

    # --------------------------------------------------------------- payroll
    payroll_dataset = _import_dataset(ctx, headers, project_id, "payroll_issues.csv")

    validate = httpx.get(f"{PORT}/api/payroll/validate/{payroll_dataset}", timeout=30)
    if validate.status_code != 200:
        raise TesterAssertionError(
            f"payroll validate -> {validate.status_code}, expected 200"
        )
    hours = validate.json().get("hours_validation", {})
    if hours.get("missing_hours", 0) <= 0:
        raise TesterAssertionError(
            "payroll validate found no missing hours (fixture engineered for E-106)"
        )
    if hours.get("negative_hours", 0) <= 0:
        raise TesterAssertionError(
            "payroll validate found no negative hours (fixture engineered for E-107)"
        )
    ctx.checkpoint("payroll validation caught engineered issues")

    report = httpx.post(
        f"{PORT}/api/payroll/report/{payroll_dataset}",
        params={"project_id": str(project_id)},
        timeout=120,
    )
    if report.status_code != 200:
        raise TesterAssertionError(
            f"payroll report -> {report.status_code}, expected 200"
        )
    file_path = report.json().get("file_path", "")
    if not file_path.lower().endswith(".pdf"):
        raise TesterAssertionError(f"report file_path not a PDF: {file_path!r}")
    ctx.checkpoint(f"payroll report generated: {file_path}")

    reports = httpx.get(
        f"{PORT}/api/reports/", params={"project_id": str(project_id)}, timeout=30
    )
    if reports.status_code != 200:
        raise TesterAssertionError(
            f"reports list -> {reports.status_code}, expected 200"
        )
    report_row = next(
        (r for r in reports.json() if r.get("report_type") == "Payroll"), None
    )
    if report_row is None:
        raise TesterAssertionError("reports list lacks the payroll report")
    _assert_report_download(ctx, report_row["id"], "pdf")

    payroll_template = _resolve_template(ctx, "Payroll", "Payroll Audit")
    run_ = _execute_template(
        ctx, headers, project_id, payroll_template, payroll_dataset
    )
    _assert_completed_with_report(ctx, run_)

    # -------------------------------------------------------- data quality
    dq_dataset = _import_dataset(ctx, headers, project_id, "customers_dupes.csv")
    dq_template = _resolve_template(ctx, "Data Quality", "Data Quality Review")
    run_ = _execute_template(ctx, headers, project_id, dq_template, dq_dataset)
    _assert_report_download(ctx, _assert_completed_with_report(ctx, run_), "pdf")

    # ------------------------------------------------------------ comparison
    cmp_a = _import_dataset(ctx, headers, project_id, "customers_v1.csv")
    cmp_b = _import_dataset(ctx, headers, project_id, "customers_v2.csv")
    cmp_template = _resolve_template(ctx, "Comparison", "Dataset Comparison")
    run_ = _execute_template(
        ctx, headers, project_id, cmp_template, cmp_a, second_dataset_id=cmp_b
    )
    _assert_report_download(ctx, _assert_completed_with_report(ctx, run_), "pdf")

    # ------------------------------------------------------------- dashboard
    dash_dataset = _import_dataset(ctx, headers, project_id, "sales_orders.csv")
    dash_template = _resolve_template(ctx, "Analytics", "Dashboard Builder")
    run_ = _execute_template(ctx, headers, project_id, dash_template, dash_dataset)
    _assert_report_download(
        ctx,
        _assert_completed_with_report(ctx, run_),
        "spreadsheetml.sheet",
    )

    # ------------------------------------------------------- own test suite
    ctx.pytest(_pytest_command(root), env={"PYTHONPATH": ""})


TESTER = Tester(
    name="WorkFlow-Toolkit E2E",
    description=(
        "Launch the FastAPI backend (bundled runtime python, PYTHONPATH "
        "neutralized), then exercise all four workflow templates end to end "
        "with engineered fixtures: Payroll Audit (validation + PDF), Data "
        "Quality Review (duplicates), Dataset Comparison (two datasets -> "
        "variance PDF), Dashboard Builder (KPIs/charts -> Excel download). "
        "Each run is polled to Completed and its report is downloaded and "
        "content-checked. Finally runs the repo's own pytest suite. Port "
        "8000 is shared with CG/Demake — a conflicting instance reports "
        "investigate."
    ),
    run=run,
    project_slug="Workflow-Toolkit",
    ports=(8000,),  # v1.17.18.5 (audit2 T11): shared with CG/Demake, declare it
)
