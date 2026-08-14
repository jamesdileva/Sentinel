import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { beforeEach, describe, expect, it, vi } from "vitest";

import ProjectTimeline from "./ProjectTimeline";
import { getTimeline } from "../api/observatory";
import { listProjects } from "../api/projects";
import type { TimelineEvent } from "../types";

vi.mock("../api/observatory", () => ({
  getTimeline: vi.fn(),
}));

vi.mock("../api/projects", () => ({
  listProjects: vi.fn(),
}));

const mockGetTimeline = vi.mocked(getTimeline);
const mockListProjects = vi.mocked(listProjects);

const events: TimelineEvent[] = [
  {
    at: "2026-08-05T10:00:00Z",
    kind: "commit",
    project_id: "p1",
    project_name: "alpha",
    message: "feat: add pipeline",
  },
  {
    at: "2026-08-05T09:00:00Z",
    kind: "build",
    project_id: "p2",
    project_name: "beta",
    message: "build passed",
  },
  {
    at: "2026-08-04T09:00:00Z",
    kind: "finding",
    project_id: "p1",
    project_name: "alpha",
    message: "high severity",
  },
];

const baseParams = {
  days: 365,
  kinds: [] as string[],
  projectId: undefined as string | undefined,
  offset: 0,
  limit: 100,
};

describe("ProjectTimeline", () => {
  beforeEach(() => {
    mockGetTimeline.mockReset();
    mockListProjects.mockReset();
    mockListProjects.mockResolvedValue({
      projects: [
        {
          id: "p1",
          name: "alpha",
          path: "/dev/alpha",
          language: "py",
          framework: null,
          status: "active",
          health_score: null,
          last_indexed: null,
          last_scanned: null,
          created_at: "2026-01-01T00:00:00Z",
          updated_at: "2026-01-01T00:00:00Z",
        },
      ],
      total: 1,
    });
  });

  it("renders events grouped by day", async () => {
    mockGetTimeline.mockResolvedValue({ events, has_more: false });

    render(<ProjectTimeline />);

    expect((await screen.findAllByText("alpha")).length).toBeGreaterThanOrEqual(1);
    expect(screen.getByText("feat: add pipeline")).toBeInTheDocument();
    expect(screen.getByText("beta")).toBeInTheDocument();
    expect(screen.getByText("build passed")).toBeInTheDocument();
    // two day-group headers for the two distinct dates
    const headers = screen
      .getAllByText(/— \d+ events?$/i)
      .map((el) => el.textContent);
    expect(headers).toHaveLength(2);
    expect(mockGetTimeline).toHaveBeenCalledWith({ ...baseParams, kinds: [] });
  });

  it("refetches when the window changes", async () => {
    mockGetTimeline.mockResolvedValue({ events: [], has_more: false });
    render(<ProjectTimeline />);
    expect(await screen.findByText("No activity in this window.")).toBeInTheDocument();

    mockGetTimeline.mockResolvedValue({ events: [events[2]], has_more: false });
    await userEvent.selectOptions(screen.getAllByRole("combobox")[0], "30");
    expect(mockGetTimeline).toHaveBeenLastCalledWith({
      ...baseParams,
      days: 30,
      kinds: [],
    });
    expect(await screen.findByText("high severity")).toBeInTheDocument();
  });

  it("filters by kind chip", async () => {
    mockGetTimeline.mockResolvedValue({ events: [events[0]], has_more: false });
    render(<ProjectTimeline />);
    await screen.findByText("feat: add pipeline");

    await userEvent.click(screen.getByRole("button", { name: "Commits" }));
    expect(mockGetTimeline).toHaveBeenLastCalledWith({
      ...baseParams,
      kinds: ["commit"],
    });
  });

  it("filters by project", async () => {
    mockGetTimeline.mockResolvedValue({ events: [], has_more: false });
    render(<ProjectTimeline />);
    await screen.findByText("No activity in this window.");

    await userEvent.selectOptions(screen.getAllByRole("combobox")[1], "p1");
    expect(mockGetTimeline).toHaveBeenLastCalledWith({
      ...baseParams,
      projectId: "p1",
    });
  });

  it("loads more pages when available", async () => {
    mockGetTimeline.mockResolvedValueOnce({
      events: [events[0]],
      has_more: true,
    });
    mockGetTimeline.mockResolvedValueOnce({
      events: [events[1]],
      has_more: false,
    });
    render(<ProjectTimeline />);
    await screen.findByText("feat: add pipeline");

    await userEvent.click(screen.getByRole("button", { name: "Load more" }));
    expect(mockGetTimeline).toHaveBeenLastCalledWith({
      ...baseParams,
      offset: 1,
    });
    expect(await screen.findByText("build passed")).toBeInTheDocument();
  });

  it("shows an error when the request fails", async () => {
    mockGetTimeline.mockRejectedValue(new Error("boom"));
    render(<ProjectTimeline />);
    expect(
      await screen.findByText(/Timeline failed to load: Error: boom/),
    ).toBeInTheDocument();
  });
});