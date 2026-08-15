import { fireEvent, render, screen, within } from "@testing-library/react";
import { beforeEach, describe, expect, it, vi } from "vitest";

import ProjectGalaxy from "./ProjectGalaxy";
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

function projectById(container: HTMLElement, id: string) {
  return container.querySelector<SVGGElement>(`g[data-id="${id}"]`);
}

describe("ProjectGalaxy", () => {
  beforeEach(() => {
    mockGetGalaxy.mockReset();
  });

  it("renders the graph and tech summary", async () => {
    mockGetGalaxy.mockResolvedValue({
      nodes: [node("alpha", "project", "alpha"), node("react", "tech", "React", "18.x")],
      links: [link("alpha", "react", "React")],
    });

    const { container } = render(<ProjectGalaxy />);

    expect((await screen.findAllByText("React")).length).toBeGreaterThanOrEqual(1);
    expect(screen.getAllByText(/18\.x/).length).toBeGreaterThanOrEqual(1);
    expect(container.querySelectorAll('g[data-kind="project"]')).toHaveLength(1);
    expect(container.querySelectorAll('g[data-kind="tech"]')).toHaveLength(1);
    expect(container.querySelectorAll("path[data-link]")).toHaveLength(1);
  });

  it("labels nodes and shows a legend", async () => {
    mockGetGalaxy.mockResolvedValue({
      nodes: [node("alpha", "project", "alpha"), node("react", "tech", "React", "18.x")],
      links: [link("alpha", "react", "React")],
    });

    render(<ProjectGalaxy />);
    await screen.findAllByText("React");
    expect(screen.getAllByText("alpha").length).toBeGreaterThanOrEqual(1);
    expect(screen.getByText("Project")).toBeInTheDocument();
    expect(screen.getByText("Technology / dependency")).toBeInTheDocument();
  });

  it("keeps project labels out of the link field (gutter, end-anchored)", async () => {
    mockGetGalaxy.mockResolvedValue({
      nodes: [node("alpha", "project", "alpha"), node("react", "tech", "React", "18.x")],
      links: [link("alpha", "react", "React")],
    });

    const { container } = render(<ProjectGalaxy />);
    await screen.findAllByText("React");

    const label = projectById(container, "alpha")!.querySelector("text")!;
    expect(label.getAttribute("text-anchor")).toBe("end");
    const labelX = Number(label.getAttribute("x"));
    const circleX = Number(projectById(container, "alpha")!.querySelector("circle")!.getAttribute("cx"));
    expect(labelX).toBeLessThan(circleX);
  });

  it("applies a larger radius to project nodes", async () => {
    mockGetGalaxy.mockResolvedValue({
      nodes: [node("alpha", "project", "alpha"), node("rust", "tech", "Rust", "1.75")],
      links: [],
    });

    const { container } = render(<ProjectGalaxy />);
    await screen.findAllByText("Rust");

    expect(
      projectById(container, "alpha")!.querySelector("circle")!.getAttribute("r"),
    ).toBe("26");
    expect(
      projectById(container, "rust")!.querySelector("rect")!.getAttribute("width"),
    ).toBe("18");
  });

  it("shows an error badge when the request fails", async () => {
    mockGetGalaxy.mockRejectedValue(new Error("boom"));
    render(<ProjectGalaxy />);
    expect(
      await screen.findByText(/Galaxy failed to load: Error: boom/),
    ).toBeInTheDocument();
  });

  it("dims projects with no shared technology", async () => {
    mockGetGalaxy.mockResolvedValue({
      nodes: [
        node("alpha", "project", "alpha"),
        node("react", "tech", "React", "18.x"),
        node("beta", "project", "beta"),
      ],
      links: [link("alpha", "react", "React")],
    });

    const { container } = render(<ProjectGalaxy />);
    await screen.findAllByText("React");

    expect(projectById(container, "beta")!.getAttribute("opacity")).toBe("0.35");
    expect(projectById(container, "alpha")!.getAttribute("opacity")).toBe("1");
  });

  it("highlights a clicked project's links and dims the rest", async () => {
    mockGetGalaxy.mockResolvedValue({
      nodes: [
        node("alpha", "project", "alpha"),
        node("beta", "project", "beta"),
        node("react", "tech", "React", "18.x"),
        node("rust", "tech", "Rust", "1.75"),
      ],
      links: [link("alpha", "react", "React"), link("beta", "rust", "Rust")],
    });

    const { container } = render(<ProjectGalaxy />);
    await screen.findAllByText("React");

    fireEvent.click(projectById(container, "alpha")!);

    const links = container.querySelectorAll("path[data-link]");
    expect(links[0].getAttribute("opacity")).toBe("1");
    expect(links[1].getAttribute("opacity")).toBe("0.12");

    expect(projectById(container, "beta")!.getAttribute("opacity")).toBe("0.2");
    expect(projectById(container, "react")!.getAttribute("opacity")).toBe("1");

    // clicking again clears the focus
    fireEvent.click(projectById(container, "alpha")!);
    expect(container.querySelectorAll("path[data-link][opacity='0.12']")).toHaveLength(0);
  });

  it("highlights on hover without pinning", async () => {
    mockGetGalaxy.mockResolvedValue({
      nodes: [
        node("alpha", "project", "alpha"),
        node("beta", "project", "beta"),
        node("react", "tech", "React", "18.x"),
        node("rust", "tech", "Rust", "1.75"),
      ],
      links: [link("alpha", "react", "React"), link("beta", "rust", "Rust")],
    });

    const { container } = render(<ProjectGalaxy />);
    await screen.findAllByText("React");

    fireEvent.mouseEnter(projectById(container, "alpha")!);
    expect(projectById(container, "beta")!.getAttribute("opacity")).toBe("0.2");
    expect(projectById(container, "react")!.getAttribute("opacity")).toBe("1");

    fireEvent.mouseLeave(projectById(container, "alpha")!);
    expect(projectById(container, "beta")!.getAttribute("opacity")).toBe("1");
  });

  it("clicking a tech reverse-focuses the projects sharing it", async () => {
    mockGetGalaxy.mockResolvedValue({
      nodes: [
        node("alpha", "project", "alpha"),
        node("beta", "project", "beta"),
        node("react", "tech", "React", "18.x"),
        node("rust", "tech", "Rust", "1.75"),
      ],
      links: [link("alpha", "react", "React"), link("beta", "rust", "Rust")],
    });

    const { container } = render(<ProjectGalaxy />);
    await screen.findAllByText("React");

    fireEvent.click(projectById(container, "react")!);
    expect(projectById(container, "alpha")!.getAttribute("opacity")).toBe("1");
    expect(projectById(container, "beta")!.getAttribute("opacity")).toBe("0.2");
    expect(projectById(container, "rust")!.getAttribute("opacity")).toBe("0.2");
  });

  it("drag repositions a node and reset restores the layout", async () => {
    mockGetGalaxy.mockResolvedValue({
      nodes: [node("alpha", "project", "alpha"), node("react", "tech", "React", "18.x")],
      links: [link("alpha", "react", "React")],
    });

    const { container } = render(<ProjectGalaxy />);
    await screen.findAllByText("React");

    const alpha = projectById(container, "alpha")!;
    const before = Number(alpha.querySelector("circle")!.getAttribute("cx"));

    fireEvent.pointerDown(alpha, { pointerId: 1, clientX: 100, clientY: 100 });
    fireEvent.pointerMove(alpha, { pointerId: 1, clientX: 160, clientY: 100 });
    fireEvent.pointerUp(alpha);

    const after = Number(
      projectById(container, "alpha")!.querySelector("circle")!.getAttribute("cx"),
    );
    expect(after).toBeGreaterThan(before + 40);

    fireEvent.click(screen.getByRole("button", { name: "Reset layout" }));
    const reset = Number(
      projectById(container, "alpha")!.querySelector("circle")!.getAttribute("cx"),
    );
    expect(reset).toBe(before);
  });

  it("shows a focus panel with framework and shared techs", async () => {
    mockGetGalaxy.mockResolvedValue({
      nodes: [
        node("alpha", "project", "alpha", null, "fastapi"),
        node("beta", "project", "beta"),
        node("react", "tech", "React", "used by 2 projects"),
      ],
      links: [link("alpha", "react", "React"), link("beta", "react", "React")],
    });

    const { container } = render(<ProjectGalaxy />);
    await screen.findAllByText("React");

    fireEvent.click(projectById(container, "alpha")!);
    expect(screen.getByText("Shared technologies")).toBeInTheDocument();
    expect(screen.getByText(/fastapi/)).toBeInTheDocument();
    expect(within(screen.getByRole("complementary")).getByText("React")).toBeInTheDocument();

    fireEvent.click(screen.getByRole("button", { name: "Clear focus" }));
    expect(screen.queryByText("Shared technologies")).not.toBeInTheDocument();
  });

  it("sorts the tech summary by usage count", async () => {
    mockGetGalaxy.mockResolvedValue({
      nodes: [
        node("p1", "project", "p1"),
        node("p2", "project", "p2"),
        node("p3", "project", "p3"),
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

    render(<ProjectGalaxy />);
    await screen.findAllByText(/used by 3 projects/);

    const items = within(screen.getByTestId("galaxy-tech-list")).getAllByText(
      /used by \d+ projects/,
    );
    expect(items[0].textContent).toContain("used by 3");
    expect(items[1].textContent).toContain("used by 2");
  });

  it("shows the checkout dir as detail for duplicate names", async () => {
    mockGetGalaxy.mockResolvedValue({
      nodes: [
        node("a", "project", "Cse455", "jamesdileva"),
        node("b", "project", "Cse455", "juduncan"),
      ],
      links: [],
    });

    const { container } = render(<ProjectGalaxy />);
    await screen.findAllByText("Cse455");

    const titles = [...container.querySelectorAll("title")].map((t) => t.textContent);
    expect(titles).toContain("Cse455 (jamesdileva)");
    expect(titles).toContain("Cse455 (juduncan)");
  });
});