import { fireEvent, render, screen, within } from "@testing-library/react";
import { beforeEach, describe, expect, it, vi } from "vitest";

import ClusterView from "./ClusterView";
import { getGalaxy } from "../api/observatory";

vi.mock("../api/observatory", () => ({
  getGalaxy: vi.fn(),
}));

const mockGetGalaxy = vi.mocked(getGalaxy);

const node = (
  id: string,
  kind: "project" | "tech",
  label: string,
  detail: string | null = null,
  framework: string | null = null,
) => ({ id, kind, label, detail, framework });

const link = (source: string, target: string, tech: string) => ({
  source,
  target,
  tech,
});

function cells(container: HTMLElement) {
  return [...container.querySelectorAll<SVGRectElement>('rect[data-cell="true"]')];
}

function cell(container: HTMLElement, row: string, col: string) {
  return container.querySelector<SVGRectElement>(`rect[data-row="${row}"][data-col="${col}"]`);
}

describe("ClusterView", () => {
  beforeEach(() => {
    mockGetGalaxy.mockReset();
  });

  it("renders one row per project and one cell per usage", async () => {
    mockGetGalaxy.mockResolvedValue({
      nodes: [
        node("p1", "project", "Alpha"),
        node("p2", "project", "Beta"),
        node("react", "tech", "React", "used by 2 projects"),
        node("rust", "tech", "Rust", "used by 2 projects"),
      ],
      links: [link("p1", "react", "React"), link("p2", "rust", "Rust")],
    });

    const { container } = render(<ClusterView />);
    await screen.findAllByText(/used by 2 projects/);

    expect(
      container.querySelectorAll('text[data-project-label]'),
    ).toHaveLength(2);
    expect(container.querySelectorAll('text[data-tech-label]')).toHaveLength(2);
    expect(cells(container)).toHaveLength(2);
  });

  it("clusters identical projects next to each other in leaf order", async () => {
    mockGetGalaxy.mockResolvedValue({
      nodes: [
        node("p1", "project", "Alpha"),
        node("p2", "project", "Beta"),
        node("p3", "project", "Gamma"),
        node("react", "tech", "React", "used by 2 projects"),
        node("rust", "tech", "Rust", "used by 2 projects"),
      ],
      links: [
        link("p1", "react", "React"),
        link("p1", "rust", "Rust"),
        link("p2", "react", "React"),
        link("p2", "rust", "Rust"),
        link("p3", "rust", "Rust"),
      ],
    });

    const { container } = render(<ClusterView />);
    await screen.findAllByText(/used by 2 projects/);

    const labels = [...container.querySelectorAll('text[data-project-label]')].map(
      (t) => t.textContent,
    );
    expect(labels).toEqual(["Alpha", "Beta", "Gamma"]);
  });

  it("hovering a cell highlights its row and column", async () => {
    mockGetGalaxy.mockResolvedValue({
      nodes: [
        node("p1", "project", "Alpha"),
        node("p2", "project", "Beta"),
        node("react", "tech", "React", "used by 2 projects"),
        node("rust", "tech", "Rust", "used by 2 projects"),
      ],
      links: [link("p1", "react", "React"), link("p2", "rust", "Rust")],
    });

    const { container } = render(<ClusterView />);
    await screen.findAllByText(/used by 2 projects/);

    fireEvent.mouseEnter(cell(container, "p1", "react")!);
    expect(container.querySelector('rect[data-row-hl="true"]')).not.toBeNull();
    expect(container.querySelector('rect[data-col-hl="true"]')).not.toBeNull();

    fireEvent.mouseLeave(cell(container, "p1", "react")!);
    expect(container.querySelector('rect[data-row-hl="true"]')).toBeNull();
  });

  it("clicking a project label opens the focus panel with framework", async () => {
    mockGetGalaxy.mockResolvedValue({
      nodes: [
        node("p1", "project", "Alpha", null, "fastapi"),
        node("p2", "project", "Beta"),
        node("react", "tech", "React", "used by 2 projects"),
      ],
      links: [link("p1", "react", "React"), link("p2", "react", "React")],
    });

    const { container } = render(<ClusterView />);
    await screen.findAllByText(/used by 2 projects/);

    fireEvent.click(
      container.querySelector('text[data-project-label="p1"]')!,
    );
    expect(screen.getByText("Shared technologies")).toBeInTheDocument();
    expect(screen.getByText(/fastapi/)).toBeInTheDocument();
  });

  it("clicking a tech label reverse-focuses its projects", async () => {
    mockGetGalaxy.mockResolvedValue({
      nodes: [
        node("p1", "project", "Alpha"),
        node("p2", "project", "Beta"),
        node("react", "tech", "React", "used by 2 projects"),
        node("rust", "tech", "Rust", "used by 2 projects"),
      ],
      links: [
        link("p1", "react", "React"),
        link("p1", "rust", "Rust"),
        link("p2", "react", "React"),
      ],
    });

    const { container } = render(<ClusterView />);
    await screen.findAllByText(/used by 2 projects/);

    fireEvent.click(
      container.querySelector('text[data-tech-label="rust"]')!,
    );
    expect(cell(container, "p1", "rust")!.getAttribute("opacity")).toBe("1");
    expect(cell(container, "p2", "react")!.getAttribute("opacity")).toBe("0.2");
  });

  it("renders island projects (no shared techs) without crashing", async () => {
    mockGetGalaxy.mockResolvedValue({
      nodes: [
        node("p1", "project", "Alpha"),
        node("p2", "project", "Beta"),
        node("react", "tech", "React", "used by 2 projects"),
      ],
      links: [link("p1", "react", "React")],
    });

    const { container } = render(<ClusterView />);
    await screen.findAllByText(/used by 2 projects/);

    expect(
      container.querySelectorAll('text[data-project-label]'),
    ).toHaveLength(2);
    expect(cells(container)).toHaveLength(1);
    expect(container.querySelector('rect[data-row="p2"]')).toBeNull();
  });

  it("renders a single-project portfolio without crashing", async () => {
    mockGetGalaxy.mockResolvedValue({
      nodes: [node("p1", "project", "Alpha")],
      links: [],
    });

    const { container } = render(<ClusterView />);
    await screen.findAllByText("Alpha");
    expect(
      container.querySelectorAll('text[data-project-label]'),
    ).toHaveLength(1);
    expect(container.querySelectorAll('text[data-tech-label]')).toHaveLength(0);
    expect(
      within(screen.getByTestId("galaxy-tech-list")).queryAllByRole("listitem"),
    ).toHaveLength(0);
  });
});