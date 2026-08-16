import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { beforeEach, describe, expect, it, vi } from "vitest";

import RagChat from "./RagChat";
import { getChatHistory, ragQuery, saveChatMessage } from "../api/rag";
import type { RagResponse } from "../api/rag";

vi.mock("../api/rag", () => ({
  ragQuery: vi.fn(),
  getChatHistory: vi.fn(),
  saveChatMessage: vi.fn(),
}));

const mockRagQuery = vi.mocked(ragQuery);
const mockGetChatHistory = vi.mocked(getChatHistory);
const mockSaveChatMessage = vi.mocked(saveChatMessage);

function response(overrides: Partial<RagResponse> = {}): RagResponse {
  return {
    answer: "The project uses FastAPI.",
    sources: [
      {
        source: "file",
        project_id: "p1",
        content: "…",
        file_path: "backend/app/main.py",
        distance: 0.21,
      },
    ],
    model: "gemma2",
    generated_at: "2026-08-05T10:00:00Z",
    confidence: 0.97,
    ...overrides,
  };
}

describe("RagChat", () => {
  beforeEach(() => {
    mockRagQuery.mockReset();
    mockGetChatHistory.mockReset();
    mockGetChatHistory.mockResolvedValue([]);
    mockSaveChatMessage.mockReset();
    mockSaveChatMessage.mockResolvedValue({} as never);
  });

  it("loads and replays the persisted chat room", async () => {
    mockGetChatHistory.mockResolvedValue([
      {
        id: "m1",
        project_id: "p1",
        role: "user",
        text: "What does this do?",
        sources: null,
        model: null,
        confidence: null,
        error: null,
        created_at: "2026-08-06T12:00:00Z",
      },
      {
        id: "m2",
        project_id: "p1",
        role: "assistant",
        text: "The project uses FastAPI.",
        sources: ["file_summaries:backend/app/main.py"],
        model: "gemma2",
        confidence: 0.9,
        error: null,
        created_at: "2026-08-06T12:00:01Z",
      },
    ]);
    render(<RagChat projectId="p1" />);
    expect(mockGetChatHistory).toHaveBeenCalledWith("p1");
    expect(
      await screen.findByText("The project uses FastAPI."),
    ).toBeInTheDocument();
    expect(screen.getByText("What does this do?")).toBeInTheDocument();
    expect(screen.getByText(/gemma2/)).toBeInTheDocument();
  });

  it("loads the all-projects room (__all__) when no project is selected", async () => {
    render(<RagChat />);
    expect(mockGetChatHistory).toHaveBeenCalledWith("__all__");
    expect(
      await screen.findByText(
        'Ask anything, e.g. "What does this project do?"',
      ),
    ).toBeInTheDocument();
  });

  it("persists the user question into the __all__ room; the answer is saved server-side", async () => {
    mockRagQuery.mockResolvedValue(response());

    const user = userEvent.setup();
    render(<RagChat />);
    await screen.findByText('Ask anything, e.g. "What does this project do?"');

    await user.type(screen.getByPlaceholderText("Ask a question…"), "Hi");
    await user.click(screen.getByRole("button", { name: "Ask" }));
    await screen.findByText("The project uses FastAPI.");

    expect(mockSaveChatMessage).toHaveBeenCalledTimes(1);
    expect(mockSaveChatMessage).toHaveBeenCalledWith("__all__", {
      role: "user",
      text: "Hi",
      sources: undefined,
      model: null,
      confidence: null,
      error: null,
    });
  });

  it("persists the user question; the answer is saved server-side", async () => {
    mockRagQuery.mockResolvedValue(response());

    const user = userEvent.setup();
    render(<RagChat projectId="p1" />);
    await screen.findByText('Ask anything, e.g. "What does this project do?"');

    await user.type(
      screen.getByPlaceholderText("Ask a question…"),
      "What does this do?",
    );
    await user.click(screen.getByRole("button", { name: "Ask" }));
    await screen.findByText("The project uses FastAPI.");

    expect(mockSaveChatMessage).toHaveBeenCalledTimes(1);
    expect(mockSaveChatMessage).toHaveBeenCalledWith("p1", {
      role: "user",
      text: "What does this do?",
      sources: undefined,
      model: null,
      confidence: null,
      error: null,
    });
  });

  it("streams a question and answer exchange", async () => {
    mockRagQuery.mockResolvedValue(response());

    render(<RagChat projectId="p1" />);
    const input = screen.getByPlaceholderText("Ask a question…");

    await userEvent.type(input, "What does this do?");
    await userEvent.click(screen.getByRole("button", { name: "Ask" }));

    expect(screen.getByText("What does this do?")).toBeInTheDocument();
    expect(mockRagQuery).toHaveBeenCalledWith("What does this do?", "p1");

    expect(
      await screen.findByText("The project uses FastAPI."),
    ).toBeInTheDocument();
    expect(screen.getByText(/gemma2/)).toBeInTheDocument();
    expect(screen.getByText("Sources (1)")).toBeInTheDocument();
    expect(screen.getByText("backend/app/main.py")).toBeInTheDocument();
  });

  it("disables the submit button while input is empty", async () => {
    render(<RagChat />);
    expect(screen.getByRole("button", { name: "Ask" })).toBeDisabled();
  });

  it("renders a thinking indicator and re-enables input while loading", async () => {
    let resolve!: (value: RagResponse) => void;
    mockRagQuery.mockReturnValue(new Promise((r) => (resolve = r)));

    const user = userEvent.setup();
    render(<RagChat />);

    await user.type(screen.getByPlaceholderText("Ask a question…"), "Hi");
    await user.click(screen.getByRole("button", { name: "Ask" }));

    expect(screen.getByText("Thinking…")).toBeInTheDocument();
    expect(screen.getByPlaceholderText("Ask a question…")).toBeDisabled();

    resolve(response());
    expect(
      await screen.findByText("The project uses FastAPI."),
    ).toBeInTheDocument();
    expect(screen.queryByText("Thinking…")).not.toBeInTheDocument();
  });

  it("shows a fallback error message when the query fails", async () => {
    mockRagQuery.mockRejectedValue(new Error("olm down"));

    const user = userEvent.setup();
    render(<RagChat />);

    await user.type(screen.getByPlaceholderText("Ask a question…"), "Why?");
    await user.click(screen.getByRole("button", { name: "Ask" }));

    expect(
      await screen.findByText("Sorry, I couldn't answer that: olm down"),
    ).toBeInTheDocument();
  });
});
