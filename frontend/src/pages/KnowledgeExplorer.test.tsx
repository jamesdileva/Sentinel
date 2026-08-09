import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { beforeEach, describe, expect, it, vi } from "vitest";

import type { Project } from "../types";

vi.mock("../api/rag", () => ({
  ragIndex: vi.fn(),
  ragSearch: vi.fn(),
  getIndexStatus: vi.fn(),
}));

vi.mock("../components/RagChat", () => ({
  default: () => <div>RAG chat stub</div>,
}));

vi.mock("../contexts/UIContext", () => ({
  useUI: vi.fn(),
}));

vi.mock("../hooks/useProjects", () => ({
  useProjectList: vi.fn(),
}));

import KnowledgeExplorer from "./KnowledgeExplorer";
import { getIndexStatus, ragIndex, ragSearch } from "../api/rag";
import { useUI } from "../contexts/UIContext";
import { useProjectList } from "../hooks/useProjects";

const mockGetIndexStatus = vi.mocked(getIndexStatus);
const mockRagIndex = vi.mocked(ragIndex);
const mockRagSearch = vi.mocked(ragSearch);
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

describe("KnowledgeExplorer", () => {
  beforeEach(() => {
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
    mockGetIndexStatus.mockResolvedValue({
      project_id: null,
      projects: { p1: { files: 4, embedded: 2 } },
      files_total: 4,
      files_embedded: 2,
    });
    mockRagSearch.mockResolvedValue({ query: "q", results: [] });
    mockRagIndex.mockResolvedValue({
      job_id: "job-1",
      status: "queued",
    });
  });

  it("shows the index progress across all projects", async () => {
    render(<KnowledgeExplorer />);
    expect(
      await screen.findByText(/2 of 4 files embedded across projects/),
    ).toBeInTheDocument();
  });

  it("shows per-project progress once one is selected", async () => {
    const user = userEvent.setup();
    render(<KnowledgeExplorer />);
    await screen.findByText(/2 of 4 files embedded across projects/);
    await user.selectOptions(screen.getByRole("combobox"), "p1");
    expect(screen.getByText(/2 of 4 files embedded/)).toBeInTheDocument();
  });

  it("marks a fully embedded project as complete", async () => {
    mockGetIndexStatus.mockResolvedValue({
      project_id: null,
      projects: { p1: { files: 4, embedded: 4 } },
      files_total: 4,
      files_embedded: 4,
    });
    const user = userEvent.setup();
    render(<KnowledgeExplorer />);
    await screen.findByText(/4 of 4 files embedded across projects/);
    await user.selectOptions(screen.getByRole("combobox"), "p1");
    expect(screen.getByText(/All 4 files embedded/)).toBeInTheDocument();
  });

  it("queues indexing and toasts the job id", async () => {
    const toast = vi.fn();
    mockUseUI.mockReturnValue({
      dark: false,
      toggleDark: vi.fn(),
      sidebarOpen: false,
      setSidebarOpen: vi.fn(),
      toasts: [],
      toast,
      dismissToast: vi.fn(),
    });
    const user = userEvent.setup();
    render(<KnowledgeExplorer />);
    await screen.findByText(/2 of 4 files embedded across projects/);
    await user.selectOptions(screen.getByRole("combobox"), "p1");
    await user.click(screen.getByRole("button", { name: "Index knowledge" }));
    expect(mockRagIndex).toHaveBeenCalledWith("p1", false);
    expect(toast).toHaveBeenCalledWith(
      expect.stringContaining("Knowledge indexing queued"),
      "success",
    );
  });
});