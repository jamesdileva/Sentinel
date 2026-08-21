import { fireEvent, render, screen, within } from "@testing-library/react";
import { describe, expect, it } from "vitest";

import ClusterView from "./ClusterView";
import type { GalaxyGraph } from "../types";

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

function makeGraph(nodes: ReturnType<typeof node>[], links: ReturnType<typeof link>[]): GalaxyGraph {
  return { nodes, links };
}

function cells(container: HTMLElement) {
  return [...container.querySelectorAll<SVGRectElement>('rect[data-cell="true"]')];
}

function cell(container: HTMLElement, row: string, col: string) {
  return container.querySelector<SVGRectElement>(`rect[data-row="${row}"][data-col="${col}"]`);
}

describe("ClusterView", () => {
  it("renders one row per project and one cell per usage", () => {
    const graph = makeGraph(
      [
        node("p1", "project", "Alpha"),
        node("p2", "project", "Beta"),
        node("react", "tech", "React", "used by 2 projects"),
        node("rust", "tech", "Rust", "used by 2 projects"),
      ],
      [link("p1", "react", "React"), link("p2", "rust", "Rust")],
    );

    const { container } = render(<ClusterView graph={graph} />);

    expect(
      container.querySelectorAll('text[data-project-label]'),
    ).toHaveLength(2);
    expect(container.querySelectorAll('text[data-tech-label]')).toHaveLength(2);
    expect(cells(container)).toHaveLength(2);
  });

  it("clusters identical projects next to each other in leaf order", () => {
    const graph = makeGraph(
      [
        node("p1", "project", "Alpha"),
        node("p2", "project", "Beta"),
        node("p3", "project", "Gamma"),
        node("react", "tech", "React", "used by 2 projects"),
        node("rust", "tech", "Rust", "used by 2 projects"),
      ],
      [
        link("p1", "react", "React"),
        link("p1", "rust", "Rust"),
        link("p2", "react", "React"),
        link("p2", "rust", "Rust"),
        link("p3", "rust", "Rust"),
      ],
    );

    const { container } = render(<ClusterView graph={graph} />);

    const labels = [...container.querySelectorAll('text[data-project-label]')].map(
      (t) => t.textContent,
    );
    expect(labels).toEqual(["Alpha", "Beta", "Gamma"]);
  });

  it("hovering a cell highlights its row and column", () => {
    const graph = makeGraph(
      [
        node("p1", "project", "Alpha"),
        node("p2", "project", "Beta"),
        node("react", "tech", "React", "used by 2 projects"),
        node("rust", "tech", "Rust", "used by 2 projects"),
      ],
      [link("p1", "react", "React"), link("p2", "rust", "Rust")],
    );

    const { container } = render(<ClusterView graph={graph} />);

    fireEvent.mouseEnter(cell(container, "p1", "react")!);
    expect(container.querySelector('rect[data-row-hl="true"]')).not.toBeNull();
    expect(container.querySelector('rect[data-col-hl="true"]')).not.toBeNull();

    fireEvent.mouseLeave(cell(container, "p1", "react")!);
    expect(container.querySelector('rect[data-row-hl="true"]')).toBeNull();
  });

  it("clicking a project label opens the focus panel with framework", () => {
    const graph = makeGraph(
      [
        node("p1", "project", "Alpha", null, "fastapi"),
        node("p2", "project", "Beta"),
        node("react", "tech", "React", "used by 2 projects"),
      ],
      [link("p1", "react", "React"), link("p2", "react", "React")],
    );

    const { container } = render(<ClusterView graph={graph} />);

    fireEvent.click(
      container.querySelector('text[data-project-label="p1"]')!,
    );
    expect(screen.getByText("Shared technologies")).toBeInTheDocument();
    expect(screen.getByText(/fastapi/)).toBeInTheDocument();
  });

  it("clicking a tech label reverse-focuses its projects", () => {
    const graph = makeGraph(
      [
        node("p1", "project", "Alpha"),
        node("p2", "project", "Beta"),
        node("react", "tech", "React", "used by 2 projects"),
        node("rust", "tech", "Rust", "used by 2 projects"),
      ],
      [
        link("p1", "react", "React"),
        link("p1", "rust", "Rust"),
        link("p2", "react", "React"),
      ],
    );

    const { container } = render(<ClusterView graph={graph} />);

    fireEvent.click(
      container.querySelector('text[data-tech-label="rust"]')!,
    );
    expect(cell(container, "p1", "rust")!.getAttribute("opacity")).toBe("1");
    expect(cell(container, "p2", "react")!.getAttribute("opacity")).toBe("0.2");
  });

  it("clicking a filled cell focuses the tech (not the project)", () => {
    const graph = makeGraph(
      [
        node("p1", "project", "Alpha"),
        node("p2", "project", "Beta"),
        node("react", "tech", "React", "used by 2 projects"),
        node("rust", "tech", "Rust", "used by 2 projects"),
      ],
      [
        link("p1", "react", "React"),
        link("p1", "rust", "Rust"),
        link("p2", "react", "React"),
      ],
    );

    const { container } = render(<ClusterView graph={graph} />);

    // Clicking cell p1×react should focus tech "react", not project "p1"
    fireEvent.click(cell(container, "p1", "react")!);
    // react column cells are highlighted; rows that use react show all cells
    expect(cell(container, "p1", "react")!.getAttribute("opacity")).toBe("1");
    expect(cell(container, "p2", "react")!.getAttribute("opacity")).toBe("1");
    // p1 also uses rust, so its rust cell stays at full opacity (row shares focused tech)
    expect(cell(container, "p1", "rust")!.getAttribute("opacity")).toBe("1");
  });

  it("renders island projects (no shared techs) without crashing", () => {
    const graph = makeGraph(
      [
        node("p1", "project", "Alpha"),
        node("p2", "project", "Beta"),
        node("react", "tech", "React", "used by 2 projects"),
      ],
      [link("p1", "react", "React")],
    );

    const { container } = render(<ClusterView graph={graph} />);

    expect(
      container.querySelectorAll('text[data-project-label]'),
    ).toHaveLength(2);
    expect(cells(container)).toHaveLength(1);
    expect(container.querySelector('rect[data-row="p2"]')).toBeNull();
  });

  it("renders a single-project portfolio without crashing", () => {
    const graph = makeGraph(
      [node("p1", "project", "Alpha")],
      [],
    );

    const { container } = render(<ClusterView graph={graph} />);

    expect(
      container.querySelectorAll('text[data-project-label]'),
    ).toHaveLength(1);
    expect(container.querySelectorAll('text[data-tech-label]')).toHaveLength(0);
    expect(
      within(screen.getByTestId("galaxy-tech-list")).queryAllByRole("listitem"),
    ).toHaveLength(0);
  });
});
