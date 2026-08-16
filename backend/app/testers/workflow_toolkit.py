"""WorkFlow-Toolkit tester — deep payroll-audit E2E over the FastAPI backend.

Verified ground truth (2026-08-15):
- Backend: `cd backend && python -m uvicorn app.main:app` on :8000 (default;
  the same port CG and Demake use, so a tester run while another 8000-bound
  app is up reports investigate honestly). No venv — the repo ships a bundled
  runtime at `backend/runtime/python/python.exe`; the tester prefers it and
  falls back to PATH `python`.
- No auth and no UI needed — every step below is plain REST (verified against
  backend/app/api/{projects,datasets,payroll,reports,workflows}.py).
- Fixture `backend/tests/fixtures/payroll_issues.csv` is engineered for the
  audit: missing hours (E-106), negative hours (E-107), excessive hours
  (E-108), below-minimum pay (E-112).
- Workflow execution is async (BackgroundTasks): execute returns a "Running"
  run, so the tester polls GET /api/workflows/runs/{id} to a terminal state.
- The direct payroll endpoints are synchronous — the report PDF is rendered
  within the request.
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

FIXTURE = Path("backend") / "tests" / "fixtures" / "payroll_issues.csv"


def _backend_command(project_root: Path) -> str:
    runtime = project_root / "backend" / "runtime" / "python" / "python.exe"
    interpreter = f'"{runtime}"' if runtime.exists() else "python"
    return f"cd backend && {interpreter} -m uvicorn app.main:app"


def run(ctx: TesterContext) -> None:
    root = Path(ctx.project.path)
    fixture = root / FIXTURE
    if not fixture.exists():
        raise TesterEnvError(f"Payroll fixture missing: {fixture}")

    ctx.launch(_backend_command(root))
    ctx.wait_log("Uvicorn running", 60)
    ctx.wait(3)
    ctx.http("GET", f"{PORT}/health", expect_body="healthy")
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

    with open(fixture, "rb") as fh:
        upload = httpx.post(
            f"{PORT}/api/datasets/import",
            data={"project_id": str(project_id)},
            files={"file": (fixture.name, fh, "text/csv")},
            timeout=60,
        )
    if upload.status_code != 200:
        raise TesterAssertionError(
            f"dataset import -> {upload.status_code}, expected 200"
        )
    dataset_id = upload.json().get("id")
    if not dataset_id:
        raise TesterAssertionError("import response lacks dataset id")
    ctx.checkpoint(f"imported payroll_issues.csv -> dataset {dataset_id}")

    validate = httpx.get(f"{PORT}/api/payroll/validate/{dataset_id}", timeout=30)
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
        f"{PORT}/api/payroll/report/{dataset_id}",
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
        f"{PORT}/api/reports", params={"project_id": str(project_id)}, timeout=30
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
    download = httpx.get(f"{PORT}/api/reports/{report_row['id']}/download", timeout=60)
    if download.status_code != 200:
        raise TesterAssertionError(
            f"report download -> {download.status_code}, expected 200"
        )
    if "pdf" not in download.headers.get("content-type", ""):
        raise TesterAssertionError(
            f"report download content-type: {download.headers.get('content-type')!r}"
        )
    ctx.checkpoint("report download serves a PDF")

    templates = httpx.get(
        f"{PORT}/api/workflows/templates",
        params={"category": "Payroll"},
        timeout=30,
    )
    if templates.status_code != 200:
        raise TesterAssertionError(
            f"workflow templates -> {templates.status_code}, expected 200"
        )
    template = next(
        (t for t in templates.json() if t.get("name") == "Payroll Audit"), None
    )
    if template is None:
        raise TesterAssertionError("Payroll Audit template not found by name")
    ctx.checkpoint("Payroll Audit template resolved")

    execute = httpx.post(
        f"{PORT}/api/workflows/templates/{template['id']}/execute",
        json={"project_id": project_id, "dataset_id": dataset_id},
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
    if not run_resp.json().get("output_report_id"):
        raise TesterAssertionError("completed run lacks output_report_id")
    ctx.checkpoint("workflow run completed with a report")


TESTER = Tester(
    name="WorkFlow-Toolkit payroll E2E",
    description=(
        "Launch the FastAPI backend (bundled runtime python), import the "
        "engineered payroll_issues.csv fixture, verify payroll validation "
        "catches its issues, generate + download the PDF report, then execute "
        "the Payroll Audit workflow template and poll it to completion. Port "
        "8000 is shared with CG/Demake — a conflicting instance reports "
        "investigate."
    ),
    run=run,
    project_slug="Workflow-Toolkit",
)
