import { describe, expect, it } from "vitest";
import { render, screen, within } from "@testing-library/react";

import FeatureMatrix from "./FeatureMatrix";
import type { FeatureMatrix as FeatureMatrixData } from "../api/portfolio";

describe("FeatureMatrix", () => {
  const matrix: FeatureMatrixData = {
    features: ["Storage", "Commits"],
    projects: ["alpha", "beta"],
    matrix: [
      ["✓", "✓"],
      ["✓", "⚠"],
    ],
  };

  it("renders feature columns and per-project symbols", () => {
    render(<FeatureMatrix matrix={matrix} />);
    expect(screen.getByText("Project")).toBeInTheDocument();
    expect(screen.getByText("Storage")).toBeInTheDocument();
    expect(screen.getByText("Commits")).toBeInTheDocument();

    const alphaRow = screen.getByText("alpha").closest("tr");
    expect(alphaRow).not.toBeNull();
    const cells = within(alphaRow as HTMLElement).getAllByRole("cell");
    expect(cells).toHaveLength(3);
    expect(cells[1]).toHaveTextContent("✓");
    expect(cells[2]).toHaveTextContent("✓");
  });

  it("colors symbols by type", () => {
    render(<FeatureMatrix matrix={matrix} />);
    const betaRow = screen.getByText("beta").closest("tr");
    const cells = within(betaRow as HTMLElement).getAllByRole("cell");
    const warnCell = cells[2];
    expect(warnCell.textContent).toBe("⚠");
    expect(warnCell.className).toContain("text-amber-500");
  });

  it("shows an empty state when no projects are indexed", () => {
    render(<FeatureMatrix matrix={{ features: [], projects: [], matrix: [] }} />);
    expect(screen.getByText("No projects indexed yet.")).toBeInTheDocument();
  });
});