import { test, expect } from "@playwright/test";

test.describe("Observatory page", () => {
  test("renders the galaxy graph and shared-tech list", async ({ page }) => {
    await page.goto("/observatory");

    await expect(page.getByText("Project Galaxy")).toBeVisible();
    await expect(page.locator("svg circle").first()).toBeVisible({ timeout: 20_000 });
  });

  test("renders a non-empty activity timeline", async ({ page }) => {
    await page.goto("/observatory");

    await expect(page.getByText("Activity Timeline")).toBeVisible();
    await expect(page.locator("ol li").first()).toBeVisible({ timeout: 20_000 });
  });

  test("lets the user pick a project in the architecture map", async ({
    page,
  }) => {
    await page.goto("/observatory");

    await expect(page.getByText("Architecture Map")).toBeVisible();
    await page.getByLabel("Project").selectOption({ label: "Sample Python Project" });
    await expect(page.getByText(/▸/).first()).toBeVisible({ timeout: 20_000 });
  });
});