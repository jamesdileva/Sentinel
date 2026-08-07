import { test, expect } from "@playwright/test";

test.describe("System health", () => {
  test("backend is healthy through the Vite proxy", async ({ page }) => {
    const response = await page.request.get("/api/v1/health");
    expect(response.ok()).toBe(true);

    const body = await response.json();
    expect(body.status).toBe("healthy");
    expect(body.database.reachable).toBe(true);
  });

  test("dashboard loads summary stats from the indexed database", async ({
    page,
  }) => {
    await page.goto("/");

    await expect(page.getByText("Builds", { exact: true })).toBeVisible();
    await expect(page.getByText("Findings", { exact: true })).toBeVisible();
    await expect(page.getByText("Health", { exact: true })).toBeVisible();

    // The persisted SQLite database holds indexed projects.
    await expect(page.getByText("Sample Python Project").first()).toBeVisible();
    await expect(page.getByText("Sample React Project").first()).toBeVisible();
  }, { timeout: 60_000 });
});