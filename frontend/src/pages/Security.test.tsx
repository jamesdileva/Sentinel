import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { beforeEach, describe, expect, it, vi } from "vitest";

import Security from "./Security";
import type { Project } from "../types";
import type { SecurityFinding } from "../api/security";

vi.mock("../api/security", () => ({
  getFindings: vi.fn(),
  triggerScan: vi.fn(),
  triggerScanAll: vi.fn(),
}));

vi.mock("../contexts/UIContext", () => ({
  useUI: vi.fn(),
}));

vi.mock("../hooks/useProjects", () => ({
  useProjectList: vi.fn(),
}));

import { getFindings, triggerScan, triggerScanAll } from "../api/security";
import { useUI } from "../contexts/UIContext";
import { useProjectList } from "../hooks/useProjects";

const mockGetFindings = vi.mocked(getFindings);
const mockTriggerScan = vi.mocked(triggerScan);
const mockTriggerScanAll = vi.mocked(triggerScanAll);
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

function makeFinding(overrides: Partial<SecurityFinding> = {}): SecurityFinding {
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
  beforeEach(() => {
    mockUseUI.mockReturnValue({ toast: vi.fn() } as never);
    mockUseProjectList.mockReturnValue({
      projects: [makeProject()],
      loading: false,
      error: null,
      refresh: vi.fn(),
    } as never);
    mockGetFindings.mockReset();
    mockTriggerScan.mockReset();
    mockTriggerScanAll.mockReset();
    mockGetFindings.mockResolvedValue([makeFinding()]);
    mockTriggerScan.mockResolvedValue({ job_id: "j-scan", status: "queued" });
    mockTriggerScanAll.mockResolvedValue({ job_id: "j-scan-all", status: "queued" });
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

  it("triggers a scan and refreshes findings", async () => {
    const user = userEvent.setup();
    render(<Security />);
    await user.selectOptions(screen.getByRole("combobox"), "p1");
    await user.click(await screen.findByRole("button", { name: "Run scan" }));
    expect(mockTriggerScan).toHaveBeenCalledWith("p1");
    expect(mockGetFindings).toHaveBeenCalledWith("p1");
  });

  it("triggers a scan of all projects without a selection", async () => {
    const user = userEvent.setup();
    render(<Security />);
    const button = screen.getByRole("button", { name: "Run all" });
    expect(button).toBeEnabled();
    await user.click(button);
    expect(mockTriggerScanAll).toHaveBeenCalledOnce();
    expect(mockTriggerScan).not.toHaveBeenCalled();
  });

  it("shows the empty state when no findings exist", async () => {
    mockGetFindings.mockResolvedValue([]);
    const user = userEvent.setup();
    render(<Security />);
    await user.selectOptions(screen.getByRole("combobox"), "p1");
    expect(await screen.findByText("No findings yet. Run a scan above.")).toBeInTheDocument();
  });
});