import { render, screen } from "@testing-library/react";
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
});
