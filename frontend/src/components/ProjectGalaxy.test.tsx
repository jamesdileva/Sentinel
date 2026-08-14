import { fireEvent, render, screen, within } from "@testing-library/react";
import { beforeEach, describe, expect, it, vi } from "vitest";

import ProjectGalaxy from "./ProjectGalaxy";
import { getGalaxy } from "../api/observatory";

vi.mock("../api/observatory", () => ({
  getGalaxy: vi.fn(),
}));

const mockGetGalaxy = vi.mocked(getGalaxy);

describe("ProjectGalaxy", () => {
  beforeEach(() => {
    mockGetGalaxy.mockReset();
  });

  it("renders the graph and tech summary", async () => {
    mockGetGalaxy.mockResolvedValue({
      nodes: [
        { id: "alpha", kind: "project", label: "alpha", detail: null },
        { id: "react", kind: "tech", label: "React", detail: "18.x" },
      ],
      links: [{ source: "alpha", target: "react", tech: "React" }],
    });

    const { container } = render(<ProjectGalaxy />);

    // The label appears on the node and in the tech summary list.
    expect((await screen.findAllByText("React")).length).toBeGreaterThanOrEqual(
      1,
    );
    expect(screen.getAllByText(/18\.x/).length).toBeGreaterThanOrEqual(1);
    expect(container.querySelectorAll("circle")).toHaveLength(2);
    expect(container.querySelectorAll("line")).toHaveLength(1);
  });

  it("labels nodes and shows a legend", async () => {
    mockGetGalaxy.mockResolvedValue({
      nodes: [
        { id: "alpha", kind: "project", label: "alpha", detail: null },
        { id: "react", kind: "tech", label: "React", detail: "18.x" },
      ],
      links: [{ source: "alpha", target: "react", tech: "React" }],
    });

    render(<ProjectGalaxy />);
    await screen.findAllByText("React");
    expect(screen.getAllByText("alpha").length).toBeGreaterThanOrEqual(1);
    expect(screen.getByText("Project")).toBeInTheDocument();
    expect(screen.getByText("Technology / dependency")).toBeInTheDocument();
  });

  it("applies a larger radius to project nodes", async () => {
    mockGetGalaxy.mockResolvedValue({
      nodes: [
        { id: "alpha", kind: "project", label: "alpha", detail: null },
        { id: "rust", kind: "tech", label: "Rust", detail: "1.75" },
      ],
      links: [],
    });

    const { container } = render(<ProjectGalaxy />);
    await screen.findAllByText("Rust");

    const circles = container.querySelectorAll("circle");
    const projectNode = circles[0];
    const techNode = circles[1];
    expect(projectNode.getAttribute("r")).toBe("22");
    expect(techNode.getAttribute("r")).toBe("12");
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
        { id: "alpha", kind: "project", label: "alpha", detail: null },
        { id: "react", kind: "tech", label: "React", detail: "18.x" },
        { id: "beta", kind: "project", label: "beta", detail: null },
      ],
      links: [{ source: "alpha", target: "react", tech: "React" }],
    });

    const { container } = render(<ProjectGalaxy />);
    await screen.findAllByText("React");

    const circles = container.querySelectorAll("circle");
    const beta = [...circles].find((c) => c.parentElement?.querySelector("title")?.textContent === "beta");
    expect(beta?.parentElement?.getAttribute("opacity")).toBe("0.35");
    const alpha = [...circles].find((c) => c.parentElement?.querySelector("title")?.textContent === "alpha");
    expect(alpha?.parentElement?.getAttribute("opacity")).toBe("1");
  });

  it("highlights a clicked project's links and dims the rest", async () => {
    mockGetGalaxy.mockResolvedValue({
      nodes: [
        { id: "alpha", kind: "project", label: "alpha", detail: null },
        { id: "beta", kind: "project", label: "beta", detail: null },
        { id: "react", kind: "tech", label: "React", detail: "18.x" },
        { id: "rust", kind: "tech", label: "Rust", detail: "1.75" },
      ],
      links: [
        { source: "alpha", target: "react", tech: "React" },
        { source: "beta", target: "rust", tech: "Rust" },
      ],
    });

    const { container } = render(<ProjectGalaxy />);
    await screen.findAllByText("React");

    const alphaCircle = [...container.querySelectorAll("circle")].find(
      (c) => c.parentElement?.querySelector("title")?.textContent === "alpha",
    );
    fireEvent.click(alphaCircle!);

    const lines = container.querySelectorAll("line");
    // links render in graph order: alpha→react stays bright, beta→rust dims
    expect(lines[0].getAttribute("opacity")).toBe("1");
    expect(lines[1].getAttribute("opacity")).toBe("0.12");

    // beta dims as a project, react stays bright as a linked tech
    const circles = container.querySelectorAll("circle");
    const beta = [...circles].find((c) => c.parentElement?.querySelector("title")?.textContent === "beta");
    expect(beta?.parentElement?.getAttribute("opacity")).toBe("0.2");

    // clicking again clears the focus
    fireEvent.click(alphaCircle!);
    expect(container.querySelectorAll("line[opacity='0.12']")).toHaveLength(0);
  });

  it("sorts the tech summary by usage count", async () => {
    mockGetGalaxy.mockResolvedValue({
      nodes: [
        { id: "p1", kind: "project", label: "p1", detail: null },
        { id: "p2", kind: "project", label: "p2", detail: null },
        { id: "p3", kind: "project", label: "p3", detail: null },
        { id: "react", kind: "tech", label: "React", detail: "used by 3 projects" },
        { id: "rust", kind: "tech", label: "Rust", detail: "used by 2 projects" },
      ],
      links: [
        { source: "p1", target: "react", tech: "React" },
        { source: "p2", target: "react", tech: "React" },
        { source: "p3", target: "react", tech: "React" },
        { source: "p1", target: "rust", tech: "Rust" },
        { source: "p2", target: "rust", tech: "Rust" },
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
        { id: "a", kind: "project", label: "Cse455", detail: "jamesdileva" },
        { id: "b", kind: "project", label: "Cse455", detail: "juduncan" },
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
