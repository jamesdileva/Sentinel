import { describe, expect, it } from "vitest";
import { render, screen } from "@testing-library/react";

import HealthCard from "./HealthCard";
import type { PortfolioScore } from "../api/portfolio";

describe("HealthCard", () => {
  const passing: PortfolioScore = {
    id: "s1",
    project_id: "p1",
    portfolio_score: 92,
    build_status: "passing",
    test_status: "passing",
    security_status: "clean",
    documentation_pct: 82,
    screenshots_available: true,
    updated_at: "2026-08-05T10:00:00Z",
  };

  it("renders the project name, id, score, and docs percentage", () => {
    render(<HealthCard name="Alpha" score={passing} />);
    expect(screen.getByText("Alpha")).toBeInTheDocument();
    expect(screen.getByText("p1")).toBeInTheDocument();
    expect(screen.getByText("92")).toBeInTheDocument();
    expect(screen.getByText("Docs: 82%")).toBeInTheDocument();
  });

  it("renders status chips for build, tests, and security", () => {
    render(<HealthCard name="Alpha" score={passing} />);
    expect(screen.getByText("Build: passing")).toBeInTheDocument();
    expect(screen.getByText("Tests: passing")).toBeInTheDocument();
    expect(screen.getByText("Security: clean")).toBeInTheDocument();
  });

  it("shows a pending-style docs chip when documentation is missing", () => {
    render(
      <HealthCard
        name="Alpha"
        score={{ ...passing, documentation_pct: 0 }}
      />,
    );
    expect(screen.getByText("Docs: none")).toBeInTheDocument();
    expect(screen.getByText("Docs: none").className).toContain("bg-slate-100");
  });

  it("colors the score by health band", () => {
    render(<HealthCard name="Good" score={passing} />);
    expect(screen.getByText("92").className).toContain("text-green-600");

    render(
      <HealthCard
        name="Warn"
        score={{ ...passing, portfolio_score: 55 }}
      />,
    );
    const warn = screen.getByText("55");
    expect(warn.className).toContain("text-amber-600");

    render(
      <HealthCard
        name="Bad"
        score={{ ...passing, portfolio_score: 30 }}
      />,
    );
    expect(screen.getByText("30").className).toContain("text-red-600");
  });
});