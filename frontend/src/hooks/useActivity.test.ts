import { beforeEach, describe, expect, it, vi } from "vitest";
import { act, renderHook, waitFor } from "@testing-library/react";

const wsState: { status: "connecting" | "open" | "closed"; lastMessage: object | null } =
  {
    status: "closed",
    lastMessage: null,
  };

vi.mock("../hooks/useWebSocket", () => ({
  useWebSocket: () => wsState,
}));

import { useActivity } from "./useActivity";

vi.mock("../api/system", () => ({
  getActivity: vi.fn(),
}));

import { getActivity } from "../api/system";

const mockGetActivity = vi.mocked(getActivity);

const HISTORICAL = [
  {
    id: "h1",
    kind: "sync",
    message: "Repo sync: nothing changed",
    detail: "All repos already up to date with GitHub.",
    data: {},
    created_at: "2026-08-08T09:00:00+00:00",
  },
  {
    id: "h2",
    kind: "job",
    message: "run_repo_sync finished",
    detail: "job beat:repo-sync",
    data: { state: "finished" },
    created_at: "2026-08-08T08:59:00+00:00",
  },
];

describe("useActivity", () => {
  beforeEach(() => {
    wsState.status = "closed";
    wsState.lastMessage = null;
    mockGetActivity.mockReset();
    mockGetActivity.mockResolvedValue(HISTORICAL);
  });

  it("loads persisted history on mount so the feed survives page switches", async () => {
    const { result } = renderHook(() => useActivity());
    await waitFor(() => expect(result.current.events).toHaveLength(2));
    expect(mockGetActivity).toHaveBeenCalledWith(200);
    expect(result.current.events[0].id).toBe("h1");
  });

  it("keeps history when the backend is unreachable", async () => {
    mockGetActivity.mockRejectedValue(new Error("backend down"));
    const { result } = renderHook(() => useActivity());
    await waitFor(() => expect(result.current.events).toHaveLength(0));
  });

  it("re-seeds persisted history when the socket opens", async () => {
    const { result, rerender } = renderHook(() => useActivity());
    await waitFor(() => expect(mockGetActivity).toHaveBeenCalled());
    mockGetActivity.mockClear();
    wsState.status = "open";
    rerender();
    await waitFor(() => expect(result.current.events).toHaveLength(2));
    expect(mockGetActivity).toHaveBeenCalledWith(100);
  });

  it("retries the history seed once after an empty response", async () => {
    vi.useFakeTimers();
    try {
      wsState.status = "open";
      mockGetActivity
        .mockResolvedValueOnce([])
        .mockResolvedValueOnce([])
        .mockResolvedValue(HISTORICAL);
      const { result } = renderHook(() => useActivity());
      await act(async () => {
        await vi.advanceTimersByTimeAsync(2_000);
      });
      expect(result.current.events).toHaveLength(2);
    } finally {
      vi.useRealTimers();
    }
  });
});