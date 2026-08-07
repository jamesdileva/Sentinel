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

vi.mock("../hooks/useWebSocket", () => ({
  useWebSocket: vi.fn(),
}));

import {
  useBuilds,
} from "../contexts/BuildContext";
import {
  useUI,
} from "../contexts/UIContext";
import {
  useProjectList,
} from "../hooks/useProjects";
import { useWebSocket } from "../hooks/useWebSocket";

const mockUseBuilds = vi.mocked(useBuilds);
const mockUseUI = vi.mocked(useUI);
const mockUseProjectList = vi.mocked(useProjectList);
const mockUseWebSocket = vi.mocked(useWebSocket);

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
    mockUseWebSocket.mockReturnValue({ status: "open", lastMessage: null });
  });

  it("shows summary stats and project cards", () => {
    render(<Dashboard />);
    expect(screen.getByText("Projects")).toBeInTheDocument();
    expect(screen.getAllByText("1")).toHaveLength(2);
    expect(screen.getByText("Builds")).toBeInTheDocument();
    expect(screen.getByText("Findings")).toBeInTheDocument();
    expect(screen.getByText("alpha")).toBeInTheDocument();
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

  it("shows the websocket channel status", () => {
    mockUseWebSocket.mockReturnValue({
      status: "connecting",
      lastMessage: { type: "welcome" },
    });
    render(<Dashboard />);
    expect(screen.getByText("Channel: welcome")).toBeInTheDocument();
    expect(screen.getByText("connecting")).toBeInTheDocument();
  });
});