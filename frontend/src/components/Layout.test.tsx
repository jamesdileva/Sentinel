import { beforeEach, describe, expect, it, vi } from "vitest";
import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { MemoryRouter, Route, Routes } from "react-router";

import Layout from "./Layout";
import { UIProvider } from "../contexts/UIContext";

vi.mock("../api/system", () => ({
  getSyncStatus: vi.fn(),
  getActivity: vi.fn(),
}));

vi.mock("../hooks/useActivity", () => ({
  useActivity: vi.fn(),
}));

import { getSyncStatus } from "../api/system";
import type { SyncStatus } from "../api/system";
import { useActivity } from "../hooks/useActivity";

const mockGetSyncStatus = vi.mocked(getSyncStatus);
const mockUseActivity = vi.mocked(useActivity);

function makeSync(overrides: Partial<SyncStatus> = {}): SyncStatus {
  return {
    configured: true,
    interval_minutes: 15,
    last_run: {
      status: "success",
      ran_at: "2026-08-06T12:00:00Z",
      cloned: ["a/b"],
      pulled: [],
      failed: {},
      indexed: 1,
      knowledge_queued: 1,
      detail: null,
    },
    ...overrides,
  };
}

function renderLayout() {
  return render(
    <UIProvider>
      <MemoryRouter initialEntries={["/"]}>
        <Routes>
          <Route element={<Layout />}>
            <Route path="/" element={<div>Home page</div>} />
          </Route>
        </Routes>
      </MemoryRouter>
    </UIProvider>,
  );
}

describe("Layout", () => {
  beforeEach(() => {
    mockGetSyncStatus.mockReset();
    mockGetSyncStatus.mockResolvedValue(makeSync());
    mockUseActivity.mockReset();
    mockUseActivity.mockReturnValue({ events: [], status: "closed" });
  });

  it("renders the brand, nav links, and outlet", async () => {
    renderLayout();
    expect(screen.getByText("Sentinel")).toBeInTheDocument();
    expect(screen.getAllByRole("link").length).toBeGreaterThan(0);
    expect(screen.getByText("Home page")).toBeInTheDocument();
  });

  it("toggles dark mode", async () => {
    const user = userEvent.setup();
    renderLayout();
    const toggle = screen.getByRole("button", { name: "Toggle dark mode" });
    expect(toggle).toHaveTextContent("☾");
    await user.click(toggle);
    expect(toggle).toHaveTextContent("☀");
    expect(document.documentElement.classList.contains("dark")).toBe(true);
  });

  it("opens a mobile sidebar overlay", async () => {
    const user = userEvent.setup();
    renderLayout();
    expect(screen.getAllByText("Sentinel")).toHaveLength(1);
    await user.click(screen.getByRole("button", { name: "Toggle navigation" }));
    expect(screen.getAllByText("Sentinel")).toHaveLength(2);
    await user.click(screen.getByRole("button", { name: "Toggle navigation" }));
    expect(screen.getAllByText("Sentinel")).toHaveLength(1);
  });

  it("shows the last successful sync in a header pill", async () => {
    renderLayout();
    const pill = await screen.findByText(/^Synced /);
    expect(pill).toBeInTheDocument();
    expect(pill.textContent).toMatch(/Aug 6/);
  });

  it("marks a failed sync red and surfaces the detail", async () => {
    mockGetSyncStatus.mockResolvedValue(
      makeSync({
        last_run: {
          status: "error",
          ran_at: "2026-08-06T12:00:00Z",
          cloned: [],
          pulled: [],
          failed: { "a/b": "pull failed: x" },
          indexed: 0,
          knowledge_queued: 0,
          detail: "pull failed: x",
        },
      }),
    );
    renderLayout();
    const pill = await screen.findByText("Sync failed");
    expect(pill).toBeInTheDocument();
    expect(pill).toHaveAttribute("title", "pull failed: x");
  });

  it("shows 'Sync not run' when no run is persisted yet", async () => {
    mockGetSyncStatus.mockResolvedValue(makeSync({ last_run: null }));
    renderLayout();
    expect(await screen.findByText("Sync not run")).toBeInTheDocument();
  });

  it("shows 'Sync not configured' when repo sync is unconfigured", async () => {
    mockGetSyncStatus.mockResolvedValue(
      makeSync({ configured: false, last_run: null }),
    );
    renderLayout();
    const pill = await screen.findByText("Sync not configured");
    expect(pill).toBeInTheDocument();
    expect(pill).toHaveAttribute(
      "title",
      expect.stringContaining("SENTINEL_GITHUB_TOKEN"),
    );
  });

  it("renders the global status bar with the latest activity", async () => {
    mockUseActivity.mockReturnValue({
      events: [
        {
          id: "e1",
          kind: "sync",
          message: "Synced 2 repositories",
          detail: null,
          data: {},
          created_at: "2026-08-06T12:00:00Z",
        },
      ],
      status: "open",
    });
    renderLayout();
    expect(
      await screen.findByText(
        (_content, element) =>
          element?.textContent?.startsWith("Sync: Synced 2 repositories") ??
          false,
      ),
    ).toBeInTheDocument();
    expect(screen.getByText("live")).toBeInTheDocument();
  });
});
