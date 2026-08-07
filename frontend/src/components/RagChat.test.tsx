import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { beforeEach, describe, expect, it, vi } from "vitest";

import RagChat from "./RagChat";
import { ragQuery } from "../api/rag";
import type { RagResponse } from "../api/rag";

vi.mock("../api/rag", () => ({
  ragQuery: vi.fn(),
}));

const mockRagQuery = vi.mocked(ragQuery);

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
  });

  it("streams a question and answer exchange", async () => {
    mockRagQuery.mockResolvedValue(response());

    render(<RagChat projectId="p1" />);
    const input = screen.getByPlaceholderText("Ask a question…");

    await userEvent.type(input, "What does this do?");
    await userEvent.click(screen.getByRole("button", { name: "Ask" }));

    expect(screen.getByText("What does this do?")).toBeInTheDocument();
    expect(mockRagQuery).toHaveBeenCalledWith("What does this do?", "p1");

    expect(await screen.findByText("The project uses FastAPI.")).toBeInTheDocument();
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
    expect(await screen.findByText("The project uses FastAPI.")).toBeInTheDocument();
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