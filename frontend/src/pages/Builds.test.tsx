import { render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { beforeEach, describe, expect, it, vi } from "vitest";

import Builds from "./Builds";
import type { Project } from "../types";
import type { BuildJob, BuildLog } from "../api/builds";
import type { SessionRecord } from "../api/sessions";

vi.mock("../api/builds", () => ({
  getBuildHistory: vi.fn(),
  getBuildStatus: vi.fn(),
  triggerBuild: vi.fn(),
}));

vi.mock("../api/testers", () => ({
  getTester: vi.fn(),
  runTester: vi.fn(),
}));

vi.mock("../api/sessions", () => ({
  listSessions: vi.fn(),
}));

vi.mock("react-router", () => ({
  useNavigate: vi.fn(),
}));

vi.mock("../contexts/UIContext", () => ({
  useUI: vi.fn(),
}));

vi.mock("../hooks/useProjects", () => ({
  useProjectList: vi.fn(),
}));

import { getBuildHistory, getBuildStatus, triggerBuild } from "../api/builds";
import { getTester, runTester } from "../api/testers";
import { listSessions } from "../api/sessions";
import { useUI } from "../contexts/UIContext";
import { useProjectList } from "../hooks/useProjects";

const mockGetBuildHistory = vi.mocked(getBuildHistory);
const mockGetBuildStatus = vi.mocked(getBuildStatus);
const mockTriggerBuild = vi.mocked(triggerBuild);
const mockGetTester = vi.mocked(getTester);
const mockRunTester = vi.mocked(runTester);
const mockListSessions = vi.mocked(listSessions);
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

function makeLog(overrides: Partial<BuildLog> = {}): BuildLog {
  return {
    id: "j1",
    project_id: "p1",
    started_at: "2026-01-01T00:00:00Z",
    completed_at: "2026-01-01T00:01:00Z",
    exit_code: 0,
    success: true,
    stdout: "Build done.",
    stderr: null,
    commands: { install: "pip install -r requirements.txt" },
    launch_command: null,
    ...overrides,
  };
}

function makeRunningJob(overrides: Partial<BuildJob> = {}): BuildJob {
  return {
    id: "j9",
    project_id: "p1",
    status: "running",
    success: null,
    exit_code: null,
    started_at: "2026-01-01T00:00:00Z",
    completed_at: null,
    launch_command: null,
    ...overrides,
  };
}

function makeTesterSession(
  overrides: Partial<SessionRecord> = {},
): SessionRecord {
  return {
    id: "s1",
    project_id: "p1",
    project_name: "alpha",
    title: "Tester: Fake tester",
    expected_output: "runs a fake app",
    actual_outcome: "checkpoint ok",
    status: "passed",
    started_at: new Date(Date.now() + 1000).toISOString(),
    ended_at: new Date(Date.now() + 5000).toISOString(),
    log_slice: null,
    checkpoints: [],
    screenshots: [],
    ...overrides,
  };
}

describe("Builds", () => {
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
    mockGetBuildHistory.mockReset();
    mockGetBuildStatus.mockReset();
    mockTriggerBuild.mockReset();
    mockGetTester.mockReset();
    mockRunTester.mockReset();
    mockListSessions.mockReset();
    mockGetBuildHistory.mockResolvedValue([makeLog()]);
    mockGetBuildStatus.mockResolvedValue(makeRunningJob());
    mockTriggerBuild.mockResolvedValue({
      id: "j2",
      project_id: "p1",
      status: "queued",
      success: null,
      exit_code: null,
      started_at: null,
      completed_at: null,
      launch_command: null,
    });
    mockGetTester.mockResolvedValue({
      name: "Fake tester",
      description: "runs a fake app",
      kind: "custom",
    });
    mockRunTester.mockResolvedValue({
      job_id: "t1",
      status: "queued",
    });
    mockListSessions.mockResolvedValue([]);
  });

  it("requires a project before building", async () => {
    render(<Builds />);
    const button = screen.getByRole("button", { name: "Run build" });
    expect(button).toBeDisabled();
  });

  it("shows build history for the selected project", async () => {
    const user = userEvent.setup();
    render(<Builds />);
    await user.selectOptions(screen.getByRole("combobox"), "p1");
    expect(await screen.findByText("succeeded")).toBeInTheDocument();
    expect(screen.getByText(/exit 0/)).toBeInTheDocument();
  });

  it("triggers a build and refreshes history", async () => {
    const user = userEvent.setup();
    render(<Builds />);
    await user.selectOptions(screen.getByRole("combobox"), "p1");
    await user.click(await screen.findByRole("button", { name: "Run build" }));
    expect(mockTriggerBuild).toHaveBeenCalledWith("p1");
    expect(mockGetBuildHistory).toHaveBeenCalledWith("p1");
  });

  it("shows the empty state when no builds exist", async () => {
    mockGetBuildHistory.mockResolvedValue([]);
    const user = userEvent.setup();
    render(<Builds />);
    await user.selectOptions(screen.getByRole("combobox"), "p1");
    expect(
      await screen.findByText("No builds yet. Trigger one above."),
    ).toBeInTheDocument();
  });

  it("labels completed no-command builds as skipped, not passed or running", async () => {
    mockGetBuildHistory.mockResolvedValue([
      makeLog({
        success: null,
        exit_code: null,
        stdout: "No build command configured for this project.",
      }),
    ]);
    const user = userEvent.setup();
    render(<Builds />);
    await user.selectOptions(screen.getByRole("combobox"), "p1");
    expect(await screen.findByText("skipped")).toBeInTheDocument();
    expect(screen.queryByText("succeeded")).not.toBeInTheDocument();
    expect(screen.queryByText("running")).not.toBeInTheDocument();
  });

  it("polls a freshly triggered build to completion without a refresh", async () => {
    mockGetBuildStatus
      .mockResolvedValueOnce(makeRunningJob({ id: "j2" }))
      .mockResolvedValue(
        makeRunningJob({
          id: "j2",
          status: "succeeded",
          success: true,
          exit_code: 0,
          completed_at: "2026-01-01T00:02:00Z",
        }),
      );
    const user = userEvent.setup();
    render(<Builds />);
    await user.selectOptions(screen.getByRole("combobox"), "p1");
    await user.click(await screen.findByRole("button", { name: "Run build" }));

    // Polls the exact job it triggered (not just the generic list).
    await waitFor(() => expect(mockGetBuildStatus).toHaveBeenCalledWith("j2"), {
      timeout: 8000,
    });
    // The terminal status triggers one final history refresh + a toast.
    await waitFor(
      () =>
        expect(toastMock).toHaveBeenCalledWith(
          expect.stringContaining("succeeded"),
          "success",
        ),
      { timeout: 8000 },
    );
    await waitFor(() => expect(mockGetBuildHistory).toHaveBeenCalledTimes(3), {
      timeout: 8000,
    });
  });

  it("resumes live polling for a build already running on page load", async () => {
    mockGetBuildHistory
      .mockResolvedValueOnce([makeLog({ success: null, completed_at: null })])
      .mockResolvedValue([makeLog()]);
    mockGetBuildStatus
      .mockResolvedValueOnce(makeRunningJob({ id: "j1" }))
      .mockResolvedValue(
        makeRunningJob({
          id: "j1",
          status: "succeeded",
          success: true,
          exit_code: 0,
          completed_at: "2026-01-01T00:01:00Z",
        }),
      );
    const user = userEvent.setup();
    render(<Builds />);
    await user.selectOptions(screen.getByRole("combobox"), "p1");
    expect(await screen.findByText("running")).toBeInTheDocument();

    await waitFor(() => expect(mockGetBuildStatus).toHaveBeenCalledWith("j1"), {
      timeout: 8000,
    });
    expect(
      await screen.findByText("succeeded", undefined, { timeout: 8000 }),
    ).toBeInTheDocument();
  });

  it("keeps the refreshed history and toast when the completion refresh is slow", async () => {
    // Initial load: a terminal row (so no resume-poll holds the button).
    // The post-trigger refresh shows the running row; the final, slow
    // refresh carries the terminal result.
    mockGetBuildHistory
      .mockResolvedValueOnce([makeLog()])
      .mockResolvedValueOnce([makeLog({ success: null, completed_at: null })])
      .mockImplementation(async () => {
        await new Promise((resolve) => setTimeout(resolve, 50));
        return [makeLog({ success: true, exit_code: 0 })];
      });
    mockGetBuildStatus
      .mockResolvedValueOnce(makeRunningJob({ id: "j2" }))
      .mockResolvedValue(
        makeRunningJob({
          id: "j2",
          status: "succeeded",
          success: true,
          exit_code: 0,
          completed_at: "2026-01-01T00:02:00Z",
        }),
      );
    const user = userEvent.setup();
    render(<Builds />);
    await user.selectOptions(screen.getByRole("combobox"), "p1");
    await user.click(await screen.findByRole("button", { name: "Run build" }));

    // A slow final refresh must not lose the toast…
    await waitFor(
      () =>
        expect(toastMock).toHaveBeenCalledWith(
          expect.stringContaining("succeeded"),
          "success",
        ),
      { timeout: 8000 },
    );
    // …or the refreshed row (regression: the row stayed "running…" forever).
    await waitFor(
      () => expect(screen.queryByText("running")).not.toBeInTheDocument(),
      { timeout: 8000 },
    );
    expect(await screen.findByText("succeeded")).toBeInTheDocument();
  });

  it("labels the action Build & Open when build + startup exist", async () => {
    mockUseProjectList.mockReturnValue({
      projects: [
        makeProject({
          stack: {
            commands: { build: "npm run build", startup: "npm run start" },
          },
        }),
      ],
      loading: false,
      error: null,
      refresh: vi.fn(),
    } as never);
    const user = userEvent.setup();
    render(<Builds />);
    await user.selectOptions(screen.getByRole("combobox"), "p1");
    expect(
      await screen.findByRole("button", { name: "Build & Open" }),
    ).toBeEnabled();
  });

  it("labels the action Open app when only a startup command exists", async () => {
    mockUseProjectList.mockReturnValue({
      projects: [
        makeProject({
          stack: { commands: { startup: "python app.py" } },
        }),
      ],
      loading: false,
      error: null,
      refresh: vi.fn(),
    } as never);
    const user = userEvent.setup();
    render(<Builds />);
    await user.selectOptions(screen.getByRole("combobox"), "p1");
    expect(
      await screen.findByRole("button", { name: "Open app" }),
    ).toBeEnabled();
  });

  it("shows the launched app command in the expanded log", async () => {
    mockGetBuildHistory.mockResolvedValue([
      makeLog({
        launch_command: "python app.py",
        stdout:
          "Build not needed — this project has no compile step.\nApp launched: python app.py",
      }),
    ]);
    const user = userEvent.setup();
    render(<Builds />);
    await user.selectOptions(screen.getByRole("combobox"), "p1");
    await user.click(await screen.findByRole("button", { name: /succeeded/ }));
    expect(screen.getByText("App launched:")).toBeInTheDocument();
    expect(screen.getByText("python app.py")).toBeInTheDocument();
  });

  it("notes the launched app in the completion toast", async () => {
    mockGetBuildStatus
      .mockResolvedValueOnce(makeRunningJob({ id: "j2" }))
      .mockResolvedValue(
        makeRunningJob({
          id: "j2",
          status: "succeeded",
          success: true,
          exit_code: 0,
          completed_at: "2026-01-01T00:02:00Z",
          launch_command: "python app.py",
        }),
      );
    mockGetBuildHistory.mockResolvedValue([
      makeLog({ launch_command: "python app.py" }),
    ]);
    const user = userEvent.setup();
    render(<Builds />);
    await user.selectOptions(screen.getByRole("combobox"), "p1");
    await user.click(await screen.findByRole("button", { name: "Run build" }));
    await waitFor(
      () =>
        expect(toastMock).toHaveBeenCalledWith(
          expect.stringContaining("App launched."),
          "success",
        ),
      { timeout: 8000 },
    );
  });

  it("shows the Run tester button when the project has a tester", async () => {
    const user = userEvent.setup();
    render(<Builds />);
    await user.selectOptions(screen.getByRole("combobox"), "p1");
    expect(
      await screen.findByRole("button", { name: /Run tester/ }),
    ).toBeEnabled();
    expect(mockGetTester).toHaveBeenCalledWith("p1");
  });

  it("disables the tester button when the project has no tester", async () => {
    mockGetTester.mockRejectedValue(new Error("No tester"));
    const user = userEvent.setup();
    render(<Builds />);
    await user.selectOptions(screen.getByRole("combobox"), "p1");
    expect(
      await screen.findByRole("button", { name: "No tester" }),
    ).toBeDisabled();
  });

  it("runs the tester and shows the session result", async () => {
    mockListSessions.mockResolvedValue([makeTesterSession()]);
    const user = userEvent.setup();
    render(<Builds />);
    await user.selectOptions(screen.getByRole("combobox"), "p1");
    await user.click(
      await screen.findByRole("button", { name: /Run tester/ }),
    );
    expect(mockRunTester).toHaveBeenCalledWith("p1");
    await waitFor(
      () =>
        expect(toastMock).toHaveBeenCalledWith(
          expect.stringContaining("Tester passed"),
          "success",
        ),
      { timeout: 8000 },
    );
    expect(
      await screen.findByText(/Tester passed/i),
    ).toBeInTheDocument();
    expect(screen.getByText("checkpoint ok")).toBeInTheDocument();
  });

  it("shows a failed tester result in the red tone", async () => {
    mockListSessions.mockResolvedValue([
      makeTesterSession({
        status: "failed",
        actual_outcome: "expected: got: boom",
      }),
    ]);
    const user = userEvent.setup();
    render(<Builds />);
    await user.selectOptions(screen.getByRole("combobox"), "p1");
    await user.click(
      await screen.findByRole("button", { name: /Run tester/ }),
    );
    await waitFor(
      () =>
        expect(toastMock).toHaveBeenCalledWith(
          expect.stringContaining("Tester failed"),
          "error",
        ),
      { timeout: 8000 },
    );
    expect(await screen.findByText(/Tester failed/i)).toBeInTheDocument();
    expect(screen.getByText("expected: got: boom")).toBeInTheDocument();
  });
});
