import { describe, expect, it } from "vitest";
import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { MemoryRouter, Route, Routes } from "react-router";

import Layout from "./Layout";
import { UIProvider } from "../contexts/UIContext";

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
  it("renders the brand, nav links, and outlet", () => {
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
});