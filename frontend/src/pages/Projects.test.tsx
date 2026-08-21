import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { beforeEach, describe, expect, it, vi } from "vitest";

import Projects from "./Projects";
import type { Project } from "../types";
import type { ProjectFile } from "../types";

vi.mock("../api/projects", () => ({
  listProjects: vi.fn(),
  getProjectFiles: vi.fn(),
}));

import { getProjectFiles, listProjects } from "../api/projects";

const mockListProjects = vi.mocked(listProjects);
const mockGetProjectFiles = vi.mocked(getProjectFiles);

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

function makeFile(overrides: Partial<ProjectFile> = {}): ProjectFile {
  return {
    id: "f1",
    path: "app/main.py",
    language: "python",
    size_bytes: 1024,
    summary: null,
    created_at: "2026-01-01T00:00:00Z",
    ...overrides,
  };
}

describe("Projects", () => {
  beforeEach(() => {
    mockListProjects.mockReset();
    mockGetProjectFiles.mockReset();
    mockListProjects.mockResolvedValue({
      projects: [makeProject()],
      total: 1,
    });
    mockGetProjectFiles.mockResolvedValue([makeFile()]);
  });

  it("renders the indexed project list", async () => {
    render(<Projects />);
    expect(await screen.findByText("alpha")).toBeInTheDocument();
    expect(screen.getByText(/dev\/alpha/)).toBeInTheDocument();
    expect(screen.getByText("python")).toBeInTheDocument();
    expect(screen.getByText("fastapi")).toBeInTheDocument();
  });

  it("expands a project to show its files", async () => {
    const user = userEvent.setup();
    render(<Projects />);
    await user.click(await screen.findByText("alpha"));
    expect(await screen.findByText("app/main.py")).toBeInTheDocument();
  });

  it("reports an empty index", async () => {
    mockListProjects.mockResolvedValue({ projects: [], total: 0 });
    render(<Projects />);
    expect(
      await screen.findByText("No projects indexed. Add one via the CLI indexer."),
    ).toBeInTheDocument();
  });

  it("shows an error when the request fails", async () => {
    mockListProjects.mockRejectedValue(new Error("Cannot reach the Sentinel backend."));
    render(<Projects />);
    expect(
      await screen.findByText("Cannot reach the Sentinel backend."),
    ).toBeInTheDocument();
  });
});