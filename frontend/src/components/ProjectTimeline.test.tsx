import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { beforeEach, describe, expect, it, vi } from "vitest";

import ProjectTimeline from "./ProjectTimeline";
import { getTimeline } from "../api/observatory";

vi.mock("../api/observatory", () => ({
  getTimeline: vi.fn(),
}));

const mockGetTimeline = vi.mocked(getTimeline);

describe("ProjectTimeline", () => {
  beforeEach(() => {
    mockGetTimeline.mockReset();
  });

  it("renders events for the selected window", async () => {
    mockGetTimeline.mockResolvedValue({
      events: [
        {
          at: "2026-08-05T10:00:00Z",
          kind: "commit",
          project_id: "p1",
          project_name: "alpha",
          message: "feat: add pipeline",
        },
        {
          at: "2026-08-04T09:00:00Z",
          kind: "build",
          project_id: "p2",
          project_name: "beta",
          message: "build passed",
        },
      ],
    });

    render(<ProjectTimeline />);

    expect(await screen.findByText("alpha")).toBeInTheDocument();
    expect(screen.getByText("feat: add pipeline")).toBeInTheDocument();
    expect(screen.getByText("beta")).toBeInTheDocument();
    expect(screen.getByText("build passed")).toBeInTheDocument();
    expect(mockGetTimeline).toHaveBeenCalledWith(365);
  });

  it("relabels events when the window changes", async () => {
    mockGetTimeline.mockResolvedValue({ events: [] });
    render(<ProjectTimeline />);
    expect(await screen.findByText("No activity in this window.")).toBeInTheDocument();

    mockGetTimeline.mockResolvedValue({
      events: [
        {
          at: "2026-08-05T10:00:00Z",
          kind: "finding",
          project_id: "p1",
          project_name: "alpha",
          message: "high severity",
        },
      ],
    });

    await userEvent.selectOptions(screen.getByRole("combobox"), "30");
    expect(mockGetTimeline).toHaveBeenLastCalledWith(30);
    expect(await screen.findByText("high severity")).toBeInTheDocument();
  });

  it("shows an error when the request fails", async () => {
    mockGetTimeline.mockRejectedValue(new Error("boom"));
    render(<ProjectTimeline />);
    expect(
      await screen.findByText(/Timeline failed to load: Error: boom/),
    ).toBeInTheDocument();
  });
});