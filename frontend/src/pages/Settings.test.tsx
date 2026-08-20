import { render, screen } from "@testing-library/react";
import { beforeEach, describe, expect, it, vi } from "vitest";

import Settings from "./Settings";
import type { SettingsReport } from "../api/settings";

vi.mock("../api/settings", () => ({
  getSettings: vi.fn(),
}));

vi.mock("../components/ServerStatus", () => ({
  default: () => <div data-testid="server-status" />,
}));

import { getSettings } from "../api/settings";

const mockGetSettings = vi.mocked(getSettings);

function makeReport(overrides: Partial<SettingsReport> = {}): SettingsReport {
  return {
    generated_at: "2026-08-20T12:00:00Z",
    version: "1.17.18.0",
    groups: [
      {
        name: "Server",
        items: [
          {
            key: "SENTINEL_PORT",
            label: "Port",
            value: "8420",
            default: "8420",
            source: "default",
            secret: false,
          },
          {
            key: "SENTINEL_API_KEY",
            label: "API key",
            value: "set",
            default: "not set",
            source: "env",
            secret: true,
          },
        ],
      },
      {
        name: "Paths",
        items: [
          {
            key: "SENTINEL_DB_PATH",
            label: "SQLite database",
            value: "data\\sqlite\\sentinel.db",
            default: "data\\sqlite\\sentinel.db",
            source: "default",
            secret: false,
          },
        ],
      },
    ],
    warnings: [],
    ...overrides,
  };
}

describe("Settings", () => {
  beforeEach(() => {
    mockGetSettings.mockReset();
    mockGetSettings.mockResolvedValue(makeReport());
  });

  it("renders grouped settings with values and source badges", async () => {
    render(<Settings />);
    expect(await screen.findByText("Settings")).toBeInTheDocument();
    expect(screen.getByText("Server")).toBeInTheDocument();
    expect(screen.getByText("Paths")).toBeInTheDocument();
    expect(screen.getByText("8420")).toBeInTheDocument();
    expect(screen.getByText("data\\sqlite\\sentinel.db")).toBeInTheDocument();
    expect(screen.getByText("env")).toBeInTheDocument();
    expect(screen.getAllByText("default").length).toBeGreaterThan(0);
  });

  it("shows the no-warnings banner when validation passes", async () => {
    render(<Settings />);
    expect(
      await screen.findByText(/No configuration warnings/),
    ).toBeInTheDocument();
  });

  it("renders validation warnings with level badges", async () => {
    mockGetSettings.mockResolvedValue(
      makeReport({
        warnings: [
          { key: "port", level: "error", message: "Port 99999 is out of range" },
          { key: "ollama", level: "warning", message: "Ollama unreachable" },
        ],
      }),
    );
    render(<Settings />);
    expect(await screen.findByText(/Configuration warnings \(2\)/)).toBeInTheDocument();
    expect(screen.getByText("Port 99999 is out of range")).toBeInTheDocument();
    expect(screen.getByText("Ollama unreachable")).toBeInTheDocument();
  });

  it("shows an error when the request fails", async () => {
    mockGetSettings.mockRejectedValue(
      new Error("Cannot reach the Sentinel backend."),
    );
    render(<Settings />);
    expect(
      await screen.findByText("Cannot reach the Sentinel backend."),
    ).toBeInTheDocument();
  });

  it("keeps the home-server status panel", async () => {
    render(<Settings />);
    expect(await screen.findByText("Home server")).toBeInTheDocument();
    expect(screen.getByTestId("server-status")).toBeInTheDocument();
  });
});