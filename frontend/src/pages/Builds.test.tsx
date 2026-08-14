import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { beforeEach, describe, expect, it, vi } from "vitest";

import Builds from "./Builds";
import type { Project } from "../types";
import type { BuildLog } from "../api/builds";

vi.mock("../api/builds", () => ({
  getBuildHistory: vi.fn(),
  triggerBuild: vi.fn(),
}));

vi.mock("../contexts/UIContext", () => ({
  useUI: vi.fn(),
}));

vi.mock("../hooks/useProjects", () => ({
  useProjectList: vi.fn(),
}));

import { getBuildHistory, triggerBuild } from "../api/builds";
import { useUI } from "../contexts/UIContext";
import { useProjectList } from "../hooks/useProjects";

const mockGetBuildHistory = vi.mocked(getBuildHistory);
const mockTriggerBuild = vi.mocked(triggerBuild);
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

function makeLog(overrides: Partial<BuildLog> = {}): BuildLog {
  return {
    id: "j1",
    project_id: "p1",
    started_at: "2026-01-01T00:00:00Z",
    completed_at: "2026-01-01T00:01:00Z",
    exit_code: 0,
    success: true,
    stdout: "Build done.",
    stderr: null,
    commands: { install: "pip install -r requirements.txt" },
    ...overrides,
  };
}

describe("Builds", () => {
  beforeEach(() => {
    mockUseUI.mockReturnValue({ toast: vi.fn() } as never);
    mockUseProjectList.mockReturnValue({
      projects: [makeProject()],
      loading: false,
      error: null,
      refresh: vi.fn(),
    } as never);
    mockGetBuildHistory.mockReset();
    mockTriggerBuild.mockReset();
    mockGetBuildHistory.mockResolvedValue([makeLog()]);
    mockTriggerBuild.mockResolvedValue({
      id: "j2",
      project_id: "p1",
      status: "queued",
      success: null,
      exit_code: null,
      started_at: null,
      completed_at: null,
    });
  });

  it("requires a project before building", async () => {
    render(<Builds />);
    const button = screen.getByRole("button", { name: "Run build" });
    expect(button).toBeDisabled();
  });

  it("shows build history for the selected project", async () => {
    const user = userEvent.setup();
    render(<Builds />);
    await user.selectOptions(screen.getByRole("combobox"), "p1");
    expect(await screen.findByText("succeeded")).toBeInTheDocument();
    expect(screen.getByText(/exit 0/)).toBeInTheDocument();
  });

  it("triggers a build and refreshes history", async () => {
    const user = userEvent.setup();
    render(<Builds />);
    await user.selectOptions(screen.getByRole("combobox"), "p1");
    await user.click(await screen.findByRole("button", { name: "Run build" }));
    expect(mockTriggerBuild).toHaveBeenCalledWith("p1");
    expect(mockGetBuildHistory).toHaveBeenCalledWith("p1");
  });

  it("shows the empty state when no builds exist", async () => {
    mockGetBuildHistory.mockResolvedValue([]);
    const user = userEvent.setup();
    render(<Builds />);
    await user.selectOptions(screen.getByRole("combobox"), "p1");
    expect(await screen.findByText("No builds yet. Trigger one above.")).toBeInTheDocument();
  });

  it("labels completed no-command builds as skipped, not passed or running", async () => {
    mockGetBuildHistory.mockResolvedValue([
      makeLog({
        success: null,
        exit_code: null,
        stdout: "No build command configured for this project.",
      }),
    ]);
    const user = userEvent.setup();
    render(<Builds />);
    await user.selectOptions(screen.getByRole("combobox"), "p1");
    expect(await screen.findByText("skipped")).toBeInTheDocument();
    expect(screen.queryByText("succeeded")).not.toBeInTheDocument();
    expect(screen.queryByText("running")).not.toBeInTheDocument();
  });
});