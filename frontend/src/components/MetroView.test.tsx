import { fireEvent, render, screen, within } from "@testing-library/react";
import { beforeEach, describe, expect, it, vi } from "vitest";

import MetroView from "./MetroView";
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

function station(container: HTMLElement, id: string) {
  return container.querySelector<SVGGElement>(`g[data-id="${id}"]`);
}

function rails(container: HTMLElement) {
  return [...container.querySelectorAll<SVGLineElement>('line[data-rail="true"]')];
}

function railById(container: HTMLElement, id: string) {
  return container.querySelector<SVGGElement>(`g[data-line="${id}"]`);
}

describe("MetroView", () => {
  beforeEach(() => {
    mockGetGalaxy.mockReset();
  });

  it("renders one rail per visible tech line", async () => {
    mockGetGalaxy.mockResolvedValue({
      nodes: [
        node("p1", "project", "Alpha"),
        node("p2", "project", "Beta"),
        node("react", "tech", "React", "used by 2 projects"),
        node("rust", "tech", "Rust", "used by 2 projects"),
      ],
      links: [link("p1", "react", "React"), link("p2", "rust", "Rust")],
    });

    const { container } = render(<MetroView />);
    await screen.findAllByText(/used by 2 projects/);

    expect(rails(container)).toHaveLength(2);
    expect(container.querySelectorAll('g[data-kind="project"]')).toHaveLength(2);
  });

  it("line slider limits the rails and demotes projects to unserved chips", async () => {
    mockGetGalaxy.mockResolvedValue({
      nodes: [
        node("p1", "project", "Alpha"),
        node("p2", "project", "Beta"),
        node("p3", "project", "Gamma"),
        node("p4", "project", "Delta"),
        node("react", "tech", "React", "used by 2 projects"),
        node("rust", "tech", "Rust", "used by 2 projects"),
        node("flask", "tech", "Flask", "used by 2 projects"),
      ],
      links: [
        link("p1", "react", "React"),
        link("p2", "react", "React"),
        link("p3", "rust", "Rust"),
        link("p4", "flask", "Flask"),
      ],
    });

    const { container } = render(<MetroView />);
    await screen.findAllByText(/used by 2 projects/);
    expect(rails(container)).toHaveLength(3);

    fireEvent.change(screen.getByRole("slider", { name: "Lines shown" }), {
      target: { value: "2" },
    });
    expect(rails(container)).toHaveLength(2);
    expect(container.querySelectorAll('g[data-kind="project"]')).toHaveLength(3);
    expect(container.querySelector('[data-unserved="p4"]')).not.toBeNull();
    expect(screen.getByText(/Unserved \(1/)).toBeInTheDocument();
  });

  it("a station appears on every line it uses at the same x (interchange)", async () => {
    mockGetGalaxy.mockResolvedValue({
      nodes: [
        node("p1", "project", "Alpha"),
        node("p2", "project", "Beta"),
        node("react", "tech", "React", "used by 2 projects"),
        node("rust", "tech", "Rust", "used by 2 projects"),
      ],
      links: [link("p1", "react", "React"), link("p1", "rust", "Rust")],
    });

    const { container } = render(<MetroView />);
    await screen.findAllByText(/used by 2 projects/);

    const circles = station(container, "p1")!.querySelectorAll("circle");
    expect(circles).toHaveLength(2);
    const cxs = [...circles].map((c) => c.getAttribute("cx"));
    expect(cxs[0]).toBe(cxs[1]);
  });

  it("projects never share an x slot on the same line", async () => {
    mockGetGalaxy.mockResolvedValue({
      nodes: [
        node("p1", "project", "Alpha"),
        node("p2", "project", "Beta"),
        node("rust", "tech", "Rust", "used by 2 projects"),
      ],
      links: [link("p1", "rust", "Rust"), link("p2", "rust", "Rust")],
    });

    const { container } = render(<MetroView />);
    await screen.findAllByText(/used by 2 projects/);

    const x1 = station(container, "p1")!.querySelector("circle")!.getAttribute("cx");
    const x2 = station(container, "p2")!.querySelector("circle")!.getAttribute("cx");
    expect(x1).not.toBe(x2);
  });

  it("hovering a station dims unrelated lines and stations", async () => {
    mockGetGalaxy.mockResolvedValue({
      nodes: [
        node("p1", "project", "Alpha"),
        node("p2", "project", "Beta"),
        node("p3", "project", "Gamma"),
        node("react", "tech", "React", "used by 2 projects"),
        node("flask", "tech", "Flask", "used by 2 projects"),
        node("rust", "tech", "Rust", "used by 2 projects"),
      ],
      links: [
        link("p1", "react", "React"),
        link("p2", "flask", "Flask"),
        link("p3", "rust", "Rust"),
      ],
    });

    const { container } = render(<MetroView />);
    await screen.findAllByText(/used by 2 projects/);

    fireEvent.mouseEnter(station(container, "p1")!);
    expect(railById(container, "react")!.getAttribute("opacity")).toBe("1");
    expect(railById(container, "flask")!.getAttribute("opacity")).toBe("0.15");
    expect(railById(container, "rust")!.getAttribute("opacity")).toBe("0.15");
    expect(station(container, "p2")!.getAttribute("opacity")).toBe("0.25");
    expect(station(container, "p3")!.getAttribute("opacity")).toBe("0.25");

    fireEvent.mouseLeave(station(container, "p1")!);
    expect(railById(container, "flask")!.getAttribute("opacity")).toBe("1");
  });

  it("clicking a station opens the focus panel; clicking again clears it", async () => {
    mockGetGalaxy.mockResolvedValue({
      nodes: [
        node("p1", "project", "Alpha", null, "fastapi"),
        node("p2", "project", "Beta"),
        node("react", "tech", "React", "used by 2 projects"),
      ],
      links: [link("p1", "react", "React"), link("p2", "react", "React")],
    });

    const { container } = render(<MetroView />);
    await screen.findAllByText(/used by 2 projects/);

    fireEvent.click(station(container, "p1")!);
    expect(screen.getByText("Shared technologies")).toBeInTheDocument();
    expect(screen.getByText(/fastapi/)).toBeInTheDocument();
    expect(within(screen.getByRole("complementary")).getByText("React")).toBeInTheDocument();

    fireEvent.click(station(container, "p1")!);
    expect(screen.queryByText("Shared technologies")).not.toBeInTheDocument();
  });

  it("clicking a line reverse-focuses the stations on it", async () => {
    mockGetGalaxy.mockResolvedValue({
      nodes: [
        node("p1", "project", "Alpha"),
        node("p2", "project", "Beta"),
        node("react", "tech", "React", "used by 2 projects"),
        node("flask", "tech", "Flask", "used by 2 projects"),
      ],
      links: [link("p1", "react", "React"), link("p2", "flask", "Flask")],
    });

    const { container } = render(<MetroView />);
    await screen.findAllByText(/used by 2 projects/);

    fireEvent.click(railById(container, "react")!);
    expect(station(container, "p1")!.getAttribute("opacity")).toBe("1");
    expect(station(container, "p2")!.getAttribute("opacity")).toBe("0.25");
    expect(railById(container, "flask")!.getAttribute("opacity")).toBe("0.15");
  });

  it("dragging slides a station and Reset restores it", async () => {
    mockGetGalaxy.mockResolvedValue({
      nodes: [
        node("p1", "project", "Alpha"),
        node("p2", "project", "Beta"),
        node("react", "tech", "React", "used by 2 projects"),
      ],
      links: [link("p1", "react", "React"), link("p2", "react", "React")],
    });

    const { container } = render(<MetroView />);
    await screen.findAllByText(/used by 2 projects/);

    const before = station(container, "p1")!.querySelector("circle")!.getAttribute("cx");
    fireEvent.pointerDown(station(container, "p1")!, {
      pointerId: 1,
      clientX: 100,
      clientY: 40,
    });
    fireEvent.pointerMove(station(container, "p1")!, {
      pointerId: 1,
      clientX: 160,
      clientY: 40,
    });
    fireEvent.pointerUp(station(container, "p1")!);
    const after = station(container, "p1")!.querySelector("circle")!.getAttribute("cx");
    expect(Number(after)).toBeGreaterThan(Number(before) + 40);

    fireEvent.click(screen.getByRole("button", { name: "Reset layout" }));
    const reset = station(container, "p1")!.querySelector("circle")!.getAttribute("cx");
    expect(reset).toBe(before);
  });

  it("keeps checkout-dir detail in station tooltips for duplicate names", async () => {
    mockGetGalaxy.mockResolvedValue({
      nodes: [
        node("a", "project", "Cse455", "jamesdileva"),
        node("b", "project", "Cse455", "juduncan"),
        node("flask", "tech", "Flask", "used by 2 projects"),
      ],
      links: [link("a", "flask", "Flask"), link("b", "flask", "Flask")],
    });

    const { container } = render(<MetroView />);
    await screen.findAllByText("Cse455");

    const titles = [...container.querySelectorAll("title")].map((t) => t.textContent);
    expect(titles).toContain("Cse455 (jamesdileva)");
    expect(titles).toContain("Cse455 (juduncan)");
  });

  it("shows the tech summary sorted by usage", async () => {
    mockGetGalaxy.mockResolvedValue({
      nodes: [
        node("p1", "project", "Alpha"),
        node("p2", "project", "Beta"),
        node("p3", "project", "Gamma"),
        node("react", "tech", "React", "used by 3 projects"),
        node("rust", "tech", "Rust", "used by 2 projects"),
      ],
      links: [
        link("p1", "react", "React"),
        link("p2", "react", "React"),
        link("p3", "react", "React"),
        link("p1", "rust", "Rust"),
        link("p2", "rust", "Rust"),
      ],
    });

    render(<MetroView />);
    await screen.findAllByText(/used by 3 projects/);

    const items = within(screen.getByTestId("galaxy-tech-list")).getAllByText(
      /used by \d+ projects/,
    );
    expect(items[0].textContent).toContain("used by 3");
    expect(items[1].textContent).toContain("used by 2");
  });
});