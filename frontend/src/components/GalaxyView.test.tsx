import { fireEvent, render, screen } from "@testing-library/react";
import { describe, expect, it } from "vitest";

import GalaxyView from "./GalaxyView";
import type { GalaxyGraph } from "../types";

const graph: GalaxyGraph = {
  nodes: [
    { id: "p-alpha", kind: "project", label: "Alpha", detail: null },
    { id: "p-beta", kind: "project", label: "Beta", detail: null },
    {
      id: "t-fastapi",
      kind: "tech",
      label: "FastAPI",
      detail: "used by 2 projects",
    },
  ],
  links: [
    { source: "p-alpha", target: "t-fastapi", tech: "fastapi" },
    { source: "p-beta", target: "t-fastapi", tech: "fastapi" },
  ],
};

describe("GalaxyView", () => {
  it("renders project and tech labels", () => {
    render(<GalaxyView graph={graph} />);
    // Labels also appear in SVG <title> tooltips — match any occurrence.
    expect(screen.getAllByText("Alpha").length).toBeGreaterThan(0);
    expect(screen.getAllByText("Beta").length).toBeGreaterThan(0);
    expect(
      screen.getByRole("button", { name: /FastAPI \(tech\)/ }),
    ).toBeInTheDocument();
  });

  it("focuses a project on click and shows the focus panel", () => {
    render(<GalaxyView graph={graph} />);
    fireEvent.click(screen.getByRole("button", { name: /Alpha \(project\)/ }));
    expect(screen.getByText("Shared technologies")).toBeInTheDocument();
  });

  it("clears focus via the panel close button", () => {
    render(<GalaxyView graph={graph} />);
    fireEvent.click(screen.getByRole("button", { name: /Alpha \(project\)/ }));
    fireEvent.click(screen.getByRole("button", { name: "Clear focus" }));
    expect(screen.queryByText("Shared technologies")).not.toBeInTheDocument();
  });
});
