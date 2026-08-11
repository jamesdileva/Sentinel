import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { beforeEach, describe, expect, it, vi } from "vitest";

import Dashboard from "./Dashboard";
import type { Project } from "../types";
import type { BuildJob } from "../api/builds";

vi.mock("../contexts/BuildContext", () => ({
  useBuilds: vi.fn(),
}));

vi.mock("../contexts/UIContext", () => ({
  useUI: vi.fn(),
}));

vi.mock("../hooks/useProjects", () => ({
  useProjectList: vi.fn(),
}));

vi.mock("../hooks/useActivity", () => ({
  useActivity: vi.fn(),
}));

vi.mock("../api/portfolio", () => ({
  getSummary: vi.fn(),
}));

vi.mock("../api/system", () => ({
  getSystemOverview: vi.fn(),
}));

import { useBuilds } from "../contexts/BuildContext";
import { useUI } from "../contexts/UIContext";
import { useProjectList } from "../hooks/useProjects";
import { useActivity } from "../hooks/useActivity";
import { getSummary } from "../api/portfolio";
import { getSystemOverview } from "../api/system";

const mockUseBuilds = vi.mocked(useBuilds);
const mockUseUI = vi.mocked(useUI);
const mockUseProjectList = vi.mocked(useProjectList);
const mockUseActivity = vi.mocked(useActivity);
const mockGetSummary = vi.mocked(getSummary);
const mockGetSystemOverview = vi.mocked(getSystemOverview);

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

function makeJob(overrides: Partial<BuildJob> = {}): BuildJob {
  return {
    id: "j1",
    project_id: "p1",
    status: "running",
    ...overrides,
  } as BuildJob;
}

describe("Dashboard", () => {
  beforeEach(() => {
    mockUseBuilds.mockReturnValue({
      activeJobs: [makeJob()],
      history: [],
      trackJob: vi.fn(),
      setJobStatus: vi.fn(),
    });
    mockUseUI.mockReturnValue({
      dark: false,
      toggleDark: vi.fn(),
      sidebarOpen: false,
      setSidebarOpen: vi.fn(),
      toasts: [],
      toast: vi.fn(),
      dismissToast: vi.fn(),
    });
    mockUseProjectList.mockReturnValue({
      projects: [makeProject()],
      loading: false,
      error: null,
      refresh: vi.fn(),
    });
    mockUseActivity.mockReturnValue({ events: [], status: "closed" });
    mockGetSummary.mockResolvedValue({
      projects: 1,
      buildable: 1,
      open_findings: 0,
      avg_health: 92.5,
    });
    mockGetSystemOverview.mockReset();
    mockGetSystemOverview.mockResolvedValue({
      generated_at: "2026-08-06T12:00:00Z",
      startup: {
        states: [
          { name: "database", ok: true, detail: "/data/sqlite/sentinel.db" },
        ],
      },
      ollama: {
        available: true,
        host: "http://192.168.4.40:11434",
        model_default: "gemma2",
        models: ["gemma2"],
        recent: [],
      },
    });
  });

  it("shows summary stats and project cards", async () => {
    render(<Dashboard />);
    expect(screen.getByText("Projects")).toBeInTheDocument();
    expect(screen.getAllByText("1")).toHaveLength(2);
    expect(screen.getByText("Builds")).toBeInTheDocument();
    expect(screen.getByText("Findings")).toBeInTheDocument();
    expect(screen.getByText("alpha")).toBeInTheDocument();
  });

  it("shows real portfolio numbers from the summary endpoint", async () => {
    mockGetSummary.mockResolvedValue({
      projects: 3,
      buildable: 2,
      open_findings: 1,
      avg_health: 52.5,
    });
    render(<Dashboard />);
    expect(await screen.findByText("52.5")).toBeInTheDocument();
    expect(screen.getAllByText("1").length).toBeGreaterThanOrEqual(2);
    expect(screen.getByText("2 of 3 buildable")).toBeInTheDocument();
  });

  it("falls back to em dashes when the summary fetch fails", async () => {
    mockGetSummary.mockRejectedValue(new Error("backend down"));
    render(<Dashboard />);
    expect(await screen.findByText("Health")).toBeInTheDocument();
    expect(screen.getAllByText("—")).toHaveLength(2);
  });

  it("renders an error banner and retries on click", async () => {
    const refresh = vi.fn();
    mockUseProjectList.mockReturnValue({
      projects: [],
      loading: false,
      error: "failed to load projects",
      refresh,
    });

    const user = userEvent.setup();
    render(<Dashboard />);

    expect(screen.getByText("failed to load projects")).toBeInTheDocument();
    await user.click(screen.getByRole("button", { name: "Retry" }));
    expect(refresh).toHaveBeenCalledTimes(1);
  });

  it("shows the live activity feed with connection status", () => {
    mockUseActivity.mockReturnValue({
      events: [
        {
          id: "e1",
          kind: "ollama",
          message: "Ollama rag-query for 120 tokens",
          detail: null,
          data: { model: "gemma2", purpose: "rag-query", tokens: 120 },
          created_at: "2026-08-06T12:00:00Z",
        },
      ],
      status: "open",
    });
    render(<Dashboard />);
    expect(screen.getByText("Live activity")).toBeInTheDocument();
    expect(
      screen.getByText("Ollama rag-query for 120 tokens"),
    ).toBeInTheDocument();
    expect(screen.getByText("live")).toBeInTheDocument();
    expect(screen.getByText("ollama")).toBeInTheDocument();
  });

  it("surfaces the event detail line (v1.17.1 logging pass)", () => {
    mockUseActivity.mockReturnValue({
      events: [
        {
          id: "e1",
          kind: "sync",
          message: "Repo sync skipped — SENTINEL_GITHUB_TOKEN is not configured",
          detail: "Set SENTINEL_GITHUB_TOKEN in .env and restart, or press Sync now.",
          data: { configured: false },
          created_at: "2026-08-06T12:00:00Z",
        },
      ],
      status: "open",
    });
    render(<Dashboard />);
    expect(
      screen.getByText("Repo sync skipped — SENTINEL_GITHUB_TOKEN is not configured"),
    ).toBeInTheDocument();
    expect(
      screen.getByText("Set SENTINEL_GITHUB_TOKEN in .env and restart, or press Sync now."),
    ).toBeInTheDocument();
  });

  it("shows an empty state while no activity has happened", () => {
    mockUseActivity.mockReturnValue({ events: [], status: "connecting" });
    render(<Dashboard />);
    expect(screen.getByText(/Nothing happened yet/)).toBeInTheDocument();
    expect(screen.getByText("connecting")).toBeInTheDocument();
  });

  it("shows home server status inline (v1.17.3 System merge)", async () => {
    render(<Dashboard />);
    expect(await screen.findByText("Ollama (AI)")).toBeInTheDocument();
    expect(screen.getByText("Startup checks")).toBeInTheDocument();
    expect(screen.getByText("database")).toBeInTheDocument();
    expect(screen.getByText("gemma2")).toBeInTheDocument();
  });
});
