"""WorkFlow-Toolkit click-through features (docs/clickthrough_plan.md,
Phase 2, v1.17.14.4).

Drives the packaged desktop app's real window
(release/win-unpacked/WorkFlow Toolkit.exe) via the CDP-attached
FeatureRunner: the app spawns its own FastAPI backend on a free port and
loads the dashboard from http://127.0.0.1:<port> (electron/main.js
pickFreePort). The run uses a sandboxed --user-data-dir, so the app starts
with a FRESH database — the feature creates its own project, imports an
engineered fixture, runs the Payroll Audit template and asserts the
completed run row plus the generated report row appear. Every entity is
self-created in the sandbox (plan: destructive actions never touch the
user's data; the sandbox is discarded after the session).

UI ground truth (2026-08-18 source scan):
- Sidebar nav (components/Sidebar/Sidebar.tsx): NavLink anchors Dashboard,
  Projects, Import Hub, Analytics, Reports, Templates, Payroll,
  Productivity.
- Projects page: `.new-project-btn` "+ New Project" opens ProjectModal
  (placeholders "Project Name" / "Description", "Create" button); each
  `.project-card` (h2 name) has an "Open" button that sets the active
  project (ProjectContext).
- Import Hub: `.import-btn` "Import File" triggers a hidden
  `input[type=file]` (accept .csv/.xlsx/.xls/.json); imports render as
  `.dataset-card` with an h3 name.
- Templates: `.category-btn` chips (Payroll, ...); `.template-card` with
  `.template-card-name` (h3) + `.run-template-btn` "Run"; the run modal
  holds a `.run-modal-select` dataset dropdown (index 0 = "No dataset")
  and `.wizard-generate-btn` "Execute Workflow"; Workflow History rows
  carry `td.report-name` (template name) and `.run-status-badge`
  (status text, e.g. "Completed").
- Reports: `.reports-table` rows with `.report-name` and
  `.report-type-badge` — workflow-run reports are recorded with
  `report_type="Workflow"` (action_registry.py).
"""

from pathlib import Path

from app.testers._helpers import (
    TesterAssertionError,
    TesterEnvError,
)
from app.testers.features import Feature, FeatureContext

PROJECT_NAME = "Sentinel Feature Project"
FIXTURE = Path("backend") / "tests" / "fixtures" / "payroll_issues.csv"
TEMPLATE_NAME = "Payroll Audit"
DATASET_NAME = "payroll_issues.csv"


def _run_payroll_audit(ctx: FeatureContext) -> None:
    page = ctx.page

    # 1. create + open a project (fresh sandbox DB — the UI starts with
    #    "Select a project to view templates").
    page.get_by_role("link", name="Projects").click()
    page.get_by_role("button", name="+ New Project").click()
    page.get_by_placeholder("Project Name").fill(PROJECT_NAME)
    page.get_by_placeholder("Description").fill("created by Sentinel feature run")
    page.get_by_role("button", name="Create", exact=True).click()
    project_card = page.locator(".project-card", has_text=PROJECT_NAME)
    project_card.wait_for(state="visible", timeout=15000)
    ctx.step("project created in the sandboxed app")
    project_card.get_by_role("button", name="Open", exact=True).click()
    ctx.step("project opened (active)")

    # 2. import the engineered fixture via the Import Hub file input.
    fixture = Path(ctx.project.path) / FIXTURE
    if not fixture.exists():
        raise TesterEnvError(f"fixture missing: {fixture}")
    page.get_by_role("link", name="Import Hub").click()
    page.get_by_role("button", name="Import File").click()
    page.set_input_files("input[type=file]", [str(fixture)])
    dataset = page.locator(".dataset-card", has_text=DATASET_NAME)
    dataset.wait_for(state="visible", timeout=30000)
    ctx.step(f"fixture imported as dataset ({DATASET_NAME})")
    ctx.shot("imported dataset in Import Hub")

    # 3. Templates -> Payroll -> Payroll Audit -> run modal.
    page.get_by_role("link", name="Templates").click()
    page.get_by_role("button", name="Payroll", exact=True).click()
    template = page.locator(".template-card", has_text=TEMPLATE_NAME)
    template.wait_for(state="visible", timeout=15000)
    template.get_by_role("button", name="Run", exact=True).click()
    select = page.locator(".run-modal-select")
    select.wait_for(state="visible", timeout=15000)
    options = select.locator("option")
    if options.count() < 2:
        raise TesterAssertionError(
            "run modal dataset dropdown lacks the imported dataset"
        )
    select.select_option(index=1)
    ctx.step(f"{TEMPLATE_NAME} run modal: dataset selected")
    page.get_by_role("button", name="Execute Workflow").click()
    ctx.step("workflow execute submitted")

    # 4. Workflow History row flips to Completed (the UI polls the run).
    completed = page.locator(
        "xpath=//tr[.//td[contains(@class,'report-name')]"
        f"[normalize-space()='{TEMPLATE_NAME}']]"
        "//span[contains(@class,'run-status-badge')]"
        "[normalize-space()='Completed']"
    )
    completed.wait_for(state="visible", timeout=60000)
    ctx.step(f"{TEMPLATE_NAME} run completed")
    ctx.shot("workflow history: completed run")

    # The run modal stays open (with the completed status) and its
    # modal-overlay blocks the sidebar — close it before navigating.
    page.locator(".run-modal").get_by_role("button", name="Close", exact=True).click()
    ctx.step("run modal closed")

    # 5. Reports page shows the run's report row (report_type "Workflow").
    page.get_by_role("link", name="Reports").click()
    report = page.locator(".report-type-badge", has_text="Workflow")
    report.wait_for(state="visible", timeout=30000)
    ctx.step("report row appears in Reports")
    ctx.shot("reports page: workflow report row")


FEATURES = [
    Feature(
        "run Payroll Audit end to end",
        "Create a project, import the engineered payroll fixture, run the "
        "Payroll Audit template and assert the completed run row plus the "
        "generated report row appear (all entities self-created in the "
        "sandboxed app data).",
        _run_payroll_audit,
        electron=True,
        budget_s=180,
    ),
]
