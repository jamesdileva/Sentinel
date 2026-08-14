import { render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { beforeEach, describe, expect, it, vi } from "vitest";

import Security from "./Security";
import type { Project } from "../types";
import type { SecurityFinding } from "../api/security";

vi.mock("../api/security", () => ({
  getFindings: vi.fn(),
  triggerScan: vi.fn(),
  triggerScanAll: vi.fn(),
  clearResolvedFindings: vi.fn(),
}));

vi.mock("../api/projects", () => ({
  getProject: vi.fn(),
}));

vi.mock("../contexts/UIContext", () => ({
  useUI: vi.fn(),
}));

vi.mock("../hooks/useProjects", () => ({
  useProjectList: vi.fn(),
}));

import {
  clearResolvedFindings,
  getFindings,
  triggerScan,
  triggerScanAll,
} from "../api/security";
import { getProject } from "../api/projects";
import { useUI } from "../contexts/UIContext";
import { useProjectList } from "../hooks/useProjects";

const mockGetFindings = vi.mocked(getFindings);
const mockTriggerScan = vi.mocked(triggerScan);
const mockTriggerScanAll = vi.mocked(triggerScanAll);
const mockClearResolved = vi.mocked(clearResolvedFindings);
const mockGetProject = vi.mocked(getProject);
const mockUseUI = vi.mocked(useUI);
const mockUseProjectList = vi.mocked(useProjectList);

function makeProject(overrides: Partial<Project> = {}): Project {
  return {
    id: "p1",
    name: "alpha",
    path: "/dev/alpha",
    language: "python",
    framework: "fastapi",
    status: "active",
    health_score: null,
    last_indexed: null,
    last_scanned: null,
    created_at: "2026-01-01T00:00:00Z",
    updated_at: "2026-01-01T00:00:00Z",
    ...overrides,
  };
}

function makeFinding(
  overrides: Partial<SecurityFinding> = {},
): SecurityFinding {
  return {
    id: "f1",
    project_id: "p1",
    type: "static_analysis",
    severity: "high",
    title: "Hardcoded secret",
    description: "A credential found in the repository.",
    ai_explanation: null,
    file_path: "config.py",
    line_number: 12,
    cve_id: null,
    remediation: null,
    resolved: false,
    detected_at: "2026-01-01T00:00:00Z",
    ...overrides,
  };
}

describe("Security", () => {
  let toastMock: ReturnType<typeof vi.fn>;
  beforeEach(() => {
    toastMock = vi.fn();
    mockUseUI.mockReturnValue({ toast: toastMock } as never);
    mockUseProjectList.mockReturnValue({
      projects: [makeProject()],
      loading: false,
      error: null,
      refresh: vi.fn(),
    } as never);
    mockGetFindings.mockReset();
    mockTriggerScan.mockReset();
    mockTriggerScanAll.mockReset();
    mockClearResolved.mockReset();
    mockGetProject.mockReset();
    mockGetFindings.mockResolvedValue([makeFinding()]);
    mockTriggerScan.mockResolvedValue({ job_id: "j-scan", status: "queued" });
    mockTriggerScanAll.mockResolvedValue({
      job_id: "j-scan-all",
      status: "queued",
    });
    mockClearResolved.mockResolvedValue({ deleted: 0 });
    mockGetProject.mockResolvedValue(makeProject());
  });

  it("requires a project before scanning", async () => {
    render(<Security />);
    const button = screen.getByRole("button", { name: "Run scan" });
    expect(button).toBeDisabled();
  });

  it("renders findings for the selected project", async () => {
    const user = userEvent.setup();
    render(<Security />);
    await user.selectOptions(screen.getByRole("combobox"), "p1");
    expect(await screen.findByText("Hardcoded secret")).toBeInTheDocument();
    expect(screen.getByText("high")).toBeInTheDocument();
  });

  it("triggers a scan and starts polling for completion", async () => {
    const user = userEvent.setup();
    render(<Security />);
    await user.selectOptions(screen.getByRole("combobox"), "p1");
    await user.click(await screen.findByRole("button", { name: "Run scan" }));
    expect(mockTriggerScan).toHaveBeenCalledWith("p1");
    expect(
      await screen.findByRole("button", { name: "Scanning…" }),
    ).toBeDisabled();
  });

  it("polls last_scanned and refreshes findings when the scan completes", async () => {
    const baseline = "2026-01-01T00:00:00Z";
    mockUseProjectList.mockReturnValue({
      projects: [makeProject({ last_scanned: baseline })],
      loading: false,
      error: null,
      refresh: vi.fn(),
    } as never);
    mockGetProject
      .mockResolvedValueOnce(makeProject({ last_scanned: baseline }))
      .mockResolvedValue(makeProject({ last_scanned: "2026-01-01T00:01:00Z" }));
    const user = userEvent.setup();
    render(<Security />);
    await user.selectOptions(screen.getByRole("combobox"), "p1");
    await user.click(await screen.findByRole("button", { name: "Run scan" }));

    // The timestamp moved → the list is refreshed and the button returns.
    await waitFor(
      () =>
        expect(toastMock).toHaveBeenCalledWith(
          "Security scan complete.",
          "success",
        ),
      { timeout: 8000 },
    );
    await waitFor(
      () =>
        expect(screen.getByRole("button", { name: "Run scan" })).toBeEnabled(),
      { timeout: 8000 },
    );
    await waitFor(() => expect(mockGetFindings).toHaveBeenCalledTimes(2), {
      timeout: 8000,
    });
  });

  it("triggers a scan of all projects without a selection", async () => {
    const user = userEvent.setup();
    render(<Security />);
    const button = screen.getByRole("button", { name: "Run all" });
    expect(button).toBeEnabled();
    await user.click(button);
    expect(mockTriggerScanAll).toHaveBeenCalledOnce();
    expect(mockTriggerScan).not.toHaveBeenCalled();
    expect(
      await screen.findByRole("button", { name: "Run all" }),
    ).toBeEnabled();
  });

  it("shows the empty state when no findings exist", async () => {
    mockGetFindings.mockResolvedValue([]);
    const user = userEvent.setup();
    render(<Security />);
    await user.selectOptions(screen.getByRole("combobox"), "p1");
    expect(
      await screen.findByText("No findings yet. Run a scan above."),
    ).toBeInTheDocument();
  });

  it("hides resolved findings by default and shows them on toggle", async () => {
    mockGetFindings.mockResolvedValue([
      makeFinding({ id: "f1", title: "Open finding" }),
      makeFinding({ id: "f2", title: "Old finding", resolved: true }),
    ]);
    const user = userEvent.setup();
    render(<Security />);
    await user.selectOptions(screen.getByRole("combobox"), "p1");

    expect(await screen.findByText("Open finding")).toBeInTheDocument();
    expect(screen.queryByText("Old finding")).not.toBeInTheDocument();
    expect(screen.getByText("Findings (1)")).toBeInTheDocument();

    await user.click(screen.getByRole("checkbox", { name: "Show resolved" }));
    expect(screen.getByText("Old finding")).toBeInTheDocument();
    expect(screen.getByText("Findings (2)")).toBeInTheDocument();
  });

  it("hides the resolved-only empty state behind a hint", async () => {
    mockGetFindings.mockResolvedValue([
      makeFinding({ id: "f2", title: "Old finding", resolved: true }),
    ]);
    const user = userEvent.setup();
    render(<Security />);
    await user.selectOptions(screen.getByRole("combobox"), "p1");
    expect(
      await screen.findByText(/No open findings — resolved ones are hidden/),
    ).toBeInTheDocument();
    expect(screen.queryByText("Old finding")).not.toBeInTheDocument();
  });

  it("clears resolved findings and refreshes the list", async () => {
    mockGetFindings.mockResolvedValue([
      makeFinding({ id: "f1", title: "Open finding" }),
      makeFinding({ id: "f2", title: "Old finding", resolved: true }),
      makeFinding({ id: "f3", title: "Older finding", resolved: true }),
    ]);
    mockClearResolved.mockResolvedValue({ deleted: 2 });
    const user = userEvent.setup();
    render(<Security />);
    await user.selectOptions(screen.getByRole("combobox"), "p1");

    const button = await screen.findByRole("button", {
      name: "Clear resolved (2)",
    });
    await user.click(button);
    expect(mockClearResolved).toHaveBeenCalledWith("p1");
    await waitFor(
      () =>
        expect(toastMock).toHaveBeenCalledWith(
          "Cleared 2 resolved finding(s).",
          "success",
        ),
      { timeout: 8000 },
    );
    await waitFor(() => expect(mockGetFindings).toHaveBeenCalledTimes(2), {
      timeout: 8000,
    });
  });
});
