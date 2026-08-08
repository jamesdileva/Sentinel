import { render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { beforeEach, describe, expect, it, vi } from "vitest";

import ArchitectureMap from "./ArchitectureMap";
import { getArchitecture } from "../api/observatory";
import { listProjects } from "../api/projects";

vi.mock("../api/observatory", () => ({
  getArchitecture: vi.fn(),
}));

vi.mock("../api/projects", () => ({
  listProjects: vi.fn(),
}));

const mockListProjects = vi.mocked(listProjects);
const mockGetArchitecture = vi.mocked(getArchitecture);

describe("ArchitectureMap", () => {
  beforeEach(() => {
    mockListProjects.mockReset();
    mockGetArchitecture.mockReset();
  });

  it("loads projects and renders the first project's tree", async () => {
    mockListProjects.mockResolvedValue({
      projects: [
        {
          id: "p1",
          name: "alpha",
          path: "/dev/alpha",
          language: "ts",
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
    mockGetArchitecture.mockResolvedValue({
      name: "src",
      path: "src",
      kind: "dir",
      count: 2,
      children: [
        {
          name: "app",
          path: "src/app",
          kind: "dir",
          count: 0,
          children: [],
        },
      ],
    });

    render(<ArchitectureMap />);

    expect(await screen.findByText("alpha")).toBeInTheDocument();
    expect(mockGetArchitecture).toHaveBeenCalledWith("p1");
    expect(await screen.findByText(/▸ src/)).toBeInTheDocument();
    expect(screen.getByText("app")).toBeInTheDocument();
  });

  it("switches the tree when the project selection changes", async () => {
    const projects = [
      {
        id: "p1",
        name: "alpha",
        path: "/dev/alpha",
        language: "ts",
        framework: null,
        status: "active" as const,
        health_score: null,
        last_indexed: null,
        last_scanned: null,
        created_at: "2026-01-01T00:00:00Z",
        updated_at: "2026-01-01T00:00:00Z",
      },
      {
        id: "p2",
        name: "beta",
        path: "/dev/beta",
        language: "py",
        framework: null,
        status: "active" as const,
        health_score: null,
        last_indexed: null,
        last_scanned: null,
        created_at: "2026-01-01T00:00:00Z",
        updated_at: "2026-01-01T00:00:00Z",
      },
    ];
    mockListProjects.mockResolvedValue({ projects, total: 2 });
    mockGetArchitecture.mockResolvedValue({
      name: "src",
      path: "src",
      kind: "dir",
      count: 0,
      children: [
        {
          name: "main.ts",
          path: "src/main.ts",
          kind: "file",
          count: 0,
          children: [],
        },
      ],
    });

    render(<ArchitectureMap />);
    expect(await screen.findByText("main.ts")).toBeInTheDocument();

    await userEvent.selectOptions(screen.getByRole("combobox"), "p2");
    await waitFor(() =>
      expect(mockGetArchitecture).toHaveBeenLastCalledWith("p2"),
    );
    expect(mockGetArchitecture).toHaveBeenCalledTimes(2);
  });

  it("shows an error when project listing fails", async () => {
    mockListProjects.mockRejectedValue(new Error("offline"));
    render(<ArchitectureMap />);
    expect(
      await screen.findByText(/Architecture failed to load: Error: offline/),
    ).toBeInTheDocument();
  });
});