import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { describe, expect, it, vi } from "vitest";

import ErrorBoundary from "./ErrorBoundary";

function Bomb(): never {
  throw new Error("boom");
}

function Flaky({ fails }: { fails: { current: boolean } }) {
  if (fails.current) throw new Error("boom");
  return <div>recovered</div>;
}

describe("ErrorBoundary", () => {
  it("shows a fallback when a child throws", () => {
    const spy = vi.spyOn(console, "error").mockImplementation(() => {});
    render(
      <ErrorBoundary>
        <Bomb />
      </ErrorBoundary>,
    );
    expect(screen.getByText("Something went wrong")).toBeInTheDocument();
    expect(screen.getByText("boom")).toBeInTheDocument();
    spy.mockRestore();
  });

  it("recovers when the user clicks try again", async () => {
    const spy = vi.spyOn(console, "error").mockImplementation(() => {});
    const fails = { current: true };
    render(
      <ErrorBoundary>
        <Flaky fails={fails} />
      </ErrorBoundary>,
    );
    expect(screen.getByText("Something went wrong")).toBeInTheDocument();
    fails.current = false;
    const user = userEvent.setup();
    await user.click(screen.getByRole("button", { name: "Try again" }));
    expect(screen.getByText("recovered")).toBeInTheDocument();
    expect(screen.queryByText("Something went wrong")).not.toBeInTheDocument();
    spy.mockRestore();
  });

  it("renders children when no error occurs", () => {
    render(
      <ErrorBoundary>
        <div>all good</div>
      </ErrorBoundary>,
    );
    expect(screen.getByText("all good")).toBeInTheDocument();
  });
});
