import { render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { beforeEach, describe, expect, it, vi } from "vitest";

import Sessions from "./Sessions";
import type { Project } from "../types";
import type {
  SessionCheckpoint,
  SessionRecord,
  SessionScreenshot,
  TriageRecord,
} from "../api/sessions";

vi.mock("../api/sessions", () => ({
  addCheckpoint: vi.fn(),
  captureScreenshot: vi.fn(),
  deleteSession: vi.fn(),
  endSession: vi.fn(),
  exportScreenshot: vi.fn(),
  getSession: vi.fn(),
  listSessions: vi.fn(),
  screenshotUrl: vi.fn(
    (sessionId: string, filename: string) =>
      `/api/v1/sessions/${sessionId}/screenshots/${filename}`,
  ),
  startSession: vi.fn(),
  summarizeSession: vi.fn(),
  triageSession: vi.fn(),
}));

vi.mock("../contexts/UIContext", () => ({
  useUI: vi.fn(),
}));

vi.mock("../hooks/useProjects", () => ({
  useProjectList: vi.fn(),
}));

import {
  addCheckpoint,
  captureScreenshot,
  deleteSession,
  endSession,
  exportScreenshot,
  getSession,
  listSessions,
  startSession,
  summarizeSession,
  triageSession,
} from "../api/sessions";
import { useUI } from "../contexts/UIContext";
import { useProjectList } from "../hooks/useProjects";

const mockAddCheckpoint = vi.mocked(addCheckpoint);
const mockCaptureScreenshot = vi.mocked(captureScreenshot);
const mockDeleteSession = vi.mocked(deleteSession);
const mockEndSession = vi.mocked(endSession);
const mockExportScreenshot = vi.mocked(exportScreenshot);
const mockGetSession = vi.mocked(getSession);
const mockListSessions = vi.mocked(listSessions);
const mockStartSession = vi.mocked(startSession);
const mockSummarizeSession = vi.mocked(summarizeSession);
const mockTriageSession = vi.mocked(triageSession);
const mockUseUI = vi.mocked(useUI);
const mockUseProjectList = vi.mocked(useProjectList);

function makeProject(overrides: Partial<Project> = {}): Project {
  return {
    id: "p1",
    name: "alpha",
    path: "/dev/alpha",
    language: "python",
    framework: "fastapi",
    status: "active",
    health_score: null,
    last_indexed: null,
    last_scanned: null,
    created_at: "2026-01-01T00:00:00Z",
    updated_at: "2026-01-01T00:00:00Z",
    ...overrides,
  };
}

function makeCheckpoint(
  overrides: Partial<SessionCheckpoint> = {},
): SessionCheckpoint {
  return {
    id: "c1",
    session_id: "s1",
    label: "menu loaded",
    at: "2026-01-01T00:01:00Z",
    ...overrides,
  };
}

function makeShot(
  overrides: Partial<SessionScreenshot> = {},
): SessionScreenshot {
  return {
    id: "shot1",
    session_id: "s1",
    checkpoint_id: null,
    path: "20260101-000100-000000.png",
    captured_at: "2026-01-01T00:01:00Z",
    ...overrides,
  };
}

function makeSession(overrides: Partial<SessionRecord> = {}): SessionRecord {
  return {
    id: "s1",
    project_id: "p1",
    project_name: "alpha",
    title: "Play the demo",
    expected_output: "Main menu appears",
    actual_outcome: null,
    status: "running",
    started_at: "2026-01-01T00:00:00Z",
    ended_at: null,
    log_slice: null,
    checkpoints: [],
    screenshots: [],
    ...overrides,
  };
}

function makeTriage(overrides: Partial<TriageRecord> = {}): TriageRecord {
  return {
    id: "tr1",
    session_id: "s1",
    evidence: {
      status: "failed",
      actual_outcome: "asset -> 404, expected 200",
      error_lines: ["ERROR 404: asset missing", "Traceback (most recent call last):"],
      patterns: ["ModuleNotFoundError"],
      frames: [
        {
          file: "C:\\demo\\app\\main.py",
          relative_path: "app\\main.py",
          line: 42,
          function: "handler",
          source: [
            { line_number: 41, text: "    result = run()" },
            { line_number: 42, text: "    boom()" },
            { line_number: 43, text: "    ok()" },
          ],
        },
      ],
      traceback_available: true,
      note: null,
    },
    summary: null,
    model: null,
    created_at: "2026-01-01T00:05:00Z",
    ...overrides,
  };
}

describe("Sessions", () => {
  let toastMock: ReturnType<typeof vi.fn>;
  beforeEach(() => {
    toastMock = vi.fn();
    mockUseUI.mockReturnValue({ toast: toastMock } as never);
    mockUseProjectList.mockReturnValue({
      projects: [makeProject()],
      loading: false,
      error: null,
      refresh: vi.fn(),
    } as never);
    mockListSessions.mockReset();
    mockStartSession.mockReset();
    mockAddCheckpoint.mockReset();
    mockCaptureScreenshot.mockReset();
    mockEndSession.mockReset();
    mockExportScreenshot.mockReset();
    mockDeleteSession.mockReset();
    mockGetSession.mockReset();
    mockTriageSession.mockReset();
    mockSummarizeSession.mockReset();
    mockListSessions.mockResolvedValue([]);
  });

  it("shows the empty state when no sessions exist", async () => {
    render(<Sessions />);
    expect(await screen.findByText(/No sessions yet/)).toBeInTheDocument();
  });

  it("lists sessions with status badges", async () => {
    mockListSessions.mockResolvedValue([
      makeSession({ status: "passed", actual_outcome: "all good" }),
      makeSession({
        id: "s2",
        title: "Second run",
        status: "running",
        checkpoints: [makeCheckpoint()],
      }),
    ]);
    render(<Sessions />);
    expect(await screen.findByText("Play the demo")).toBeInTheDocument();
    expect(screen.getByText("Second run")).toBeInTheDocument();
    expect(screen.getByText("passed")).toBeInTheDocument();
    expect(screen.getByText("running")).toBeInTheDocument();
    expect(screen.getByText("1 checkpoint(s) · 0 shot(s)")).toBeInTheDocument();
  });

  it("filters by project", async () => {
    const user = userEvent.setup();
    render(<Sessions />);
    await user.selectOptions(screen.getByRole("combobox"), "p1");
    await waitFor(() => {
      expect(mockListSessions).toHaveBeenLastCalledWith("p1", undefined);
    });
  });

  it("filters by status chip", async () => {
    const user = userEvent.setup();
    render(<Sessions />);
    await user.click(screen.getByRole("button", { name: /passed \(0\)/ }));
    await waitFor(() => {
      expect(mockListSessions).toHaveBeenLastCalledWith(undefined, "passed");
    });
  });

  it("expands a session to show checkpoints and log slice", async () => {
    mockListSessions.mockResolvedValue([
      makeSession({
        status: "passed",
        checkpoints: [makeCheckpoint()],
        log_slice:
          "[sentinel] Session started 2026-01-01 s1: Play the demo\napp booted\n[sentinel] Session ended 2026-01-01 s1: passed",
        screenshots: [makeShot()],
      }),
    ]);
    const user = userEvent.setup();
    render(<Sessions />);
    await user.click(await screen.findByText("Play the demo"));
    expect(await screen.findByText("menu loaded")).toBeInTheDocument();
    expect(screen.getByText("app booted")).toBeInTheDocument();
    expect(screen.getByText(/Main menu appears/)).toBeInTheDocument();
    expect(screen.getByAltText(/Screenshot/)).toBeInTheDocument();
  });

  it("opens the create dialog and starts a session", async () => {
    mockStartSession.mockResolvedValue(makeSession());
    const user = userEvent.setup();
    render(<Sessions />);
    await user.click(screen.getByRole("button", { name: "New session" }));
    await user.selectOptions(screen.getAllByRole("combobox")[1], "p1");
    await user.type(
      screen.getByPlaceholderText(/Play through first level/),
      "Test run",
    );
    await user.click(screen.getByRole("button", { name: "Start session" }));
    await waitFor(() => {
      expect(mockStartSession).toHaveBeenCalledWith({
        project_id: "p1",
        title: "Test run",
        expected_output: null,
      });
    });
    expect(toastMock).toHaveBeenCalledWith(
      expect.stringContaining("Session started"),
      "success",
    );
  });

  it("records a checkpoint from the detail pane", async () => {
    mockListSessions.mockResolvedValue([makeSession()]);
    mockAddCheckpoint.mockResolvedValue(
      makeCheckpoint({ label: "hud visible" }),
    );
    mockGetSession.mockResolvedValue(
      makeSession({ checkpoints: [makeCheckpoint({ label: "hud visible" })] }),
    );
    const user = userEvent.setup();
    render(<Sessions />);
    await user.click(await screen.findByText("Play the demo"));
    await user.type(
      screen.getByPlaceholderText("Checkpoint label…"),
      "hud visible",
    );
    await user.click(screen.getByRole("button", { name: "Add checkpoint" }));
    await waitFor(() => {
      expect(mockAddCheckpoint).toHaveBeenCalledWith("s1", "hud visible");
    });
    expect(await screen.findByText("hud visible")).toBeInTheDocument();
  });

  it("captures a screenshot on demand", async () => {
    mockListSessions.mockResolvedValue([makeSession()]);
    mockCaptureScreenshot.mockResolvedValue(makeShot());
    mockGetSession.mockResolvedValue(
      makeSession({ screenshots: [makeShot()] }),
    );
    const user = userEvent.setup();
    render(<Sessions />);
    await user.click(await screen.findByText("Play the demo"));
    await user.click(
      screen.getByRole("button", { name: "Capture screenshot" }),
    );
    await waitFor(() => {
      expect(mockCaptureScreenshot).toHaveBeenCalledWith("s1", undefined);
    });
    expect(toastMock).toHaveBeenCalledWith("Screenshot captured.", "success");
  });

  it("ends a running session with status and outcome", async () => {
    mockListSessions.mockResolvedValue([makeSession()]);
    mockEndSession.mockResolvedValue(
      makeSession({ status: "failed", actual_outcome: "crashed" }),
    );
    mockGetSession.mockResolvedValue(
      makeSession({ status: "failed", actual_outcome: "crashed" }),
    );
    const user = userEvent.setup();
    render(<Sessions />);
    await user.click(await screen.findByText("Play the demo"));
    await user.type(
      screen.getByPlaceholderText(/What actually happened/),
      "crashed",
    );
    await user.click(screen.getByRole("radio", { name: "failed" }));
    await user.click(screen.getByRole("button", { name: "End session" }));
    await waitFor(() => {
      expect(mockEndSession).toHaveBeenCalledWith("s1", "crashed", "failed");
    });
    expect(toastMock).toHaveBeenCalledWith(
      expect.stringContaining("Session ended"),
      "success",
    );
  });

  it("exports a screenshot and shows the card HTML", async () => {
    mockListSessions.mockResolvedValue([
      makeSession({ status: "passed", screenshots: [makeShot()] }),
    ]);
    mockExportScreenshot.mockResolvedValue({
      copied: ["C:\\portfolio\\images\\sessions\\alpha-20260101.png"],
      snippet: '<div class="card">…</div>',
    });
    const user = userEvent.setup();
    render(<Sessions />);
    await user.click(await screen.findByText("Play the demo"));
    await user.click(
      await screen.findByRole("button", { name: "Export to portfolio" }),
    );
    expect(mockExportScreenshot).toHaveBeenCalledWith("s1", "shot1");
    expect(
      await screen.findByText(/Paste the card HTML into index.html/),
    ).toBeInTheDocument();
    expect(screen.getByText(/<div class="card">/)).toBeInTheDocument();
  });

  it("deletes a session after confirmation-less click", async () => {
    mockListSessions.mockResolvedValue([makeSession()]);
    const user = userEvent.setup();
    render(<Sessions />);
    await user.click(await screen.findByText("Play the demo"));
    await user.click(screen.getByRole("button", { name: "Delete" }));
    await waitFor(() => {
      expect(mockDeleteSession).toHaveBeenCalledWith("s1");
    });
    expect(toastMock).toHaveBeenCalledWith("Session deleted.", "success");
  });

  it("zooms a screenshot into a modal", async () => {
    mockListSessions.mockResolvedValue([
      makeSession({ status: "passed", screenshots: [makeShot()] }),
    ]);
    const user = userEvent.setup();
    render(<Sessions />);
    await user.click(await screen.findByText("Play the demo"));
    await user.click(screen.getByRole("button", { name: "View screenshot" }));
    expect(
      screen.getByRole("dialog", { name: "Screenshot preview" }),
    ).toBeInTheDocument();
    await user.click(
      screen.getByRole("dialog", { name: "Screenshot preview" }),
    );
    expect(
      screen.queryByRole("dialog", { name: "Screenshot preview" }),
    ).not.toBeInTheDocument();
  });

  it("shows the triage button only for failed/investigate sessions", async () => {
    mockListSessions.mockResolvedValue([
      makeSession({ status: "passed" }),
      makeSession({ id: "s2", title: "Broken run", status: "failed" }),
    ]);
    render(<Sessions />);
    await userEvent.setup().click(await screen.findByText("Play the demo"));
    expect(
      screen.queryByRole("button", { name: "Triage failure" }),
    ).not.toBeInTheDocument();
    await userEvent.setup().click(await screen.findByText("Broken run"));
    expect(
      screen.getByRole("button", { name: "Triage failure" }),
    ).toBeInTheDocument();
  });

  it("triages a failed session and renders the evidence card", async () => {
    mockListSessions.mockResolvedValue([
      makeSession({ status: "failed", actual_outcome: "boom" }),
    ]);
    mockTriageSession.mockResolvedValue(makeTriage());
    const user = userEvent.setup();
    render(<Sessions />);
    await user.click(await screen.findByText("Play the demo"));
    await user.click(screen.getByRole("button", { name: "Triage failure" }));
    expect(await screen.findByText(/Error lines \(verbatim/)).toBeInTheDocument();
    expect(screen.getByText(/ERROR 404: asset missing/)).toBeInTheDocument();
    expect(screen.getByText(/app\\main\.py:42/)).toBeInTheDocument();
    expect(screen.getByText("ModuleNotFoundError")).toBeInTheDocument();
    expect(screen.getByText("boom()")).toBeInTheDocument();
    expect(mockTriageSession).toHaveBeenCalledWith("s1");
  });

  it("runs the AI summary and shows provenance", async () => {
    mockListSessions.mockResolvedValue([
      makeSession({ status: "investigate" }),
    ]);
    mockSummarizeSession.mockResolvedValue(
      makeTriage({
        summary: "The handler failed at app/main.py:42.",
        model: "llama3.1:8b",
        created_at: "2026-01-01T00:05:00Z",
      }),
    );
    const user = userEvent.setup();
    render(<Sessions />);
    await user.click(await screen.findByText("Play the demo"));
    await user.click(screen.getByRole("button", { name: "AI summary" }));
    expect(
      await screen.findByText("The handler failed at app/main.py:42."),
    ).toBeInTheDocument();
    expect(screen.getByText(/llama3\.1:8b ·/)).toBeInTheDocument();
    expect(mockSummarizeSession).toHaveBeenCalledWith("s1");
  });

  it("toasts an error when Ollama is unavailable", async () => {
    mockListSessions.mockResolvedValue([
      makeSession({ status: "failed" }),
    ]);
    mockSummarizeSession.mockRejectedValue(new Error("Ollama unavailable: down"));
    const user = userEvent.setup();
    render(<Sessions />);
    await user.click(await screen.findByText("Play the demo"));
    await user.click(screen.getByRole("button", { name: "AI summary" }));
    await waitFor(() => {
      expect(toastMock).toHaveBeenCalledWith(
        expect.stringContaining("Ollama unavailable"),
        "error",
      );
    });
  });
});
