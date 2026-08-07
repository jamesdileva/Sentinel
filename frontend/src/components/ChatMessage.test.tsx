import { describe, expect, it } from "vitest";
import { render, screen } from "@testing-library/react";

import ChatMessage, { type ChatMessageData } from "./ChatMessage";

describe("ChatMessage", () => {
  it("renders a user message aligned right", () => {
    render(<ChatMessage message={{ id: 1, role: "user", text: "Hello" }} />);
    const bubble = screen.getByText("Hello").closest("div") as HTMLElement;
    expect(screen.getByTestId("message-user")).toBeInTheDocument();
    expect(bubble.className).toContain("bg-indigo-600");
  });

  it("renders an assistant message with sources, model, and confidence", () => {
    const message: ChatMessageData = {
      id: 2,
      role: "assistant",
      text: "The project uses FastAPI.",
      model: "gemma2",
      generatedAt: "2026-08-05T10:00:00Z",
      confidence: 0.97,
      sources: [
        {
          source: "section",
          project_id: "p1",
          content: "…",
          file_path: "backend/app/main.py",
          distance: 0.21,
        },
        {
          source: "summary",
          project_id: "p1",
          content: "…",
          file_path: null,
          distance: 0.45,
        },
      ],
    };

    render(<ChatMessage message={message} />);

    expect(screen.getByText(message.text)).toBeInTheDocument();
    expect(screen.getByText("Sources (2)")).toBeInTheDocument();
    expect(screen.getByText("backend/app/main.py")).toBeInTheDocument();
    expect(screen.getByText(/0\.210/)).toBeInTheDocument();
    expect(screen.getByText(/gemma2/)).toBeInTheDocument();
    expect(screen.getByText(/confidence 0\.97/)).toBeInTheDocument();
  });

  it("shows an error style for failed assistant messages", () => {
    const message: ChatMessageData = {
      id: 3,
      role: "assistant",
      text: "Sorry, I couldn't answer that.",
      error: true,
    };
    render(<ChatMessage message={message} />);
    expect(screen.getByText(message.text)).toBeInTheDocument();
    const bubble = screen.getByText(message.text).closest("div") as HTMLElement;
    expect(bubble.className).toContain("bg-red-50");
  });
});