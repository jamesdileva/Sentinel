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
    await waitFor(() =>
      expect(mockGetArchitecture).toHaveBeenCalledWith("p1"),
    );
    expect(await screen.findByRole("button", { name: /src/ })).toBeInTheDocument();
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

  it("collapses and expands directories", async () => {
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
          count: 1,
          children: [
            {
              name: "routes.py",
              path: "src/app/routes.py",
              kind: "file",
              count: 0,
              children: [],
            },
          ],
        },
      ],
    });

    render(<ArchitectureMap />);
    expect(await screen.findByText("routes.py")).toBeInTheDocument();

    await userEvent.click(screen.getByRole("button", { name: /▸ app/ }));
    expect(screen.queryByText("routes.py")).not.toBeInTheDocument();

    await userEvent.click(screen.getByRole("button", { name: /▸ app/ }));
    expect(await screen.findByText("routes.py")).toBeInTheDocument();
  });

  it("filters the tree by search term", async () => {
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
          name: "main.ts",
          path: "src/main.ts",
          kind: "file",
          count: 0,
          children: [],
        },
        {
          name: "util.py",
          path: "src/util.py",
          kind: "file",
          count: 0,
          children: [],
        },
      ],
    });

    render(<ArchitectureMap />);
    await screen.findByText("main.ts");

    await userEvent.type(screen.getByPlaceholderText("Filter files…"), "main");
    expect(screen.getByText("main.ts")).toBeInTheDocument();
    expect(screen.queryByText("util.py")).not.toBeInTheDocument();

    await userEvent.clear(screen.getByPlaceholderText("Filter files…"));
    expect(await screen.findByText("util.py")).toBeInTheDocument();
  });

  it("shows a stats header with file and dir counts", async () => {
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
      name: "alpha",
      path: "",
      kind: "dir",
      count: 3,
      children: [
        {
          name: "src",
          path: "src",
          kind: "dir",
          count: 2,
          children: [
            {
              name: "main.ts",
              path: "src/main.ts",
              kind: "file",
              count: 0,
              children: [],
            },
            {
              name: "util.py",
              path: "src/util.py",
              kind: "file",
              count: 0,
              children: [],
            },
          ],
        },
        {
          name: "README.md",
          path: "README.md",
          kind: "file",
          count: 0,
          children: [],
        },
      ],
    });

    render(<ArchitectureMap />);
    expect(await screen.findByText("3 files")).toBeInTheDocument();
    expect(screen.getByText("1 dirs")).toBeInTheDocument();
    expect(screen.getByText(/src · 2/)).toBeInTheDocument();
  });
});