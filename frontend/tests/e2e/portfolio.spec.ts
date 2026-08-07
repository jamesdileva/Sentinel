import { test, expect } from "@playwright/test";

test.describe("Portfolio page", () => {
  test("renders health cards with deterministic scores", async ({ page }) => {
    await page.goto("/portfolio");

    await expect(page.getByText(/Health scores/)).toBeVisible();
    await expect(
      page.getByText("Sample Python Project").first(),
    ).toBeVisible({ timeout: 20_000 });
    await expect(
      page.getByText(/Build: (passing|failing|pending)/).first(),
    ).toBeVisible();
  });

  test("shows the feature matrix table", async ({ page }) => {
    await page.goto("/portfolio");

    await expect(page.getByRole("table")).toBeVisible({ timeout: 20_000 });
    const rows = page.getByRole("row");
    expect(await rows.count()).toBeGreaterThanOrEqual(2);
  });
});