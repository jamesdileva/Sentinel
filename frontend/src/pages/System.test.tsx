import { render, screen } from "@testing-library/react";
import { beforeEach, describe, expect, it, vi } from "vitest";

import System from "./System";
import type { SystemOverview } from "../api/system";

vi.mock("../api/system", () => ({
  getSystemOverview: vi.fn(),
}));

import { getSystemOverview } from "../api/system";

const mockGetSystemOverview = vi.mocked(getSystemOverview);

function makeOverview(): SystemOverview {
  return {
    generated_at: "2026-08-06T12:00:00Z",
    startup: {
      states: [
        { name: "database", ok: true, detail: "/data/sqlite/sentinel.db" },
        { name: "ollama", ok: true, detail: "gemma2" },
      ],
    },
    ollama: {
      available: true,
      host: "http://192.168.4.40:11434",
      model_default: "gemma2",
      models: ["gemma2", "nomic-embed-text"],
      recent: [
        {
          model: "gemma2",
          prompt_chars: 120,
          response_chars: 400,
          eval_count: 300,
          eval_duration_ns: 1_000_000_000,
          total_duration_ns: 1_250_000_000,
          tokens_per_second: 300,
          latency_ms: 1250.0,
          created_at: "2026-08-06T11:59:00Z",
        },
      ],
    },
    pihole: {
      configured: true,
      host: "http://192.168.4.40:8053",
      blocking: "enabled",
      queries_total: 1234,
      queries_blocked: 310,
      blocked_percent: 25.1,
      clients: 4,
      error: null,
    },
  };
}

describe("System", () => {
  beforeEach(() => {
    mockGetSystemOverview.mockReset();
    mockGetSystemOverview.mockResolvedValue(makeOverview());
  });

  it("renders ollama status, models and avg tokens/sec", async () => {
    render(<System />);
    expect(await screen.findByText("Ollama (AI)")).toBeInTheDocument();
    expect(screen.getByText("gemma2")).toBeInTheDocument();
    expect(screen.getByText("avg 300.0 t/s")).toBeInTheDocument();
    expect(screen.getByText(/300 tokens/)).toBeInTheDocument();
  });

  it("renders pihole blocking stats", async () => {
    render(<System />);
    expect(await screen.findByText("Pi-hole")).toBeInTheDocument();
    expect(screen.getByText("Queries today")).toBeInTheDocument();
    expect(screen.getByText("1,234")).toBeInTheDocument();
    expect(screen.getByText("Blocked today")).toBeInTheDocument();
    expect(screen.getByText("310")).toBeInTheDocument();
  });

  it("shows an error when the request fails", async () => {
    mockGetSystemOverview.mockRejectedValue(
      new Error("Cannot reach the Sentinel backend."),
    );
    render(<System />);
    expect(
      await screen.findByText("Cannot reach the Sentinel backend."),
    ).toBeInTheDocument();
  });

  it("reports startup check states", async () => {
    render(<System />);
    expect(await screen.findByText("Startup checks")).toBeInTheDocument();
    expect(screen.getByText("database")).toBeInTheDocument();
    expect(screen.getByText("ollama")).toBeInTheDocument();
  });
});
