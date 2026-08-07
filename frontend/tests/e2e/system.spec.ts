import { test, expect } from "@playwright/test";

test.describe("System page", () => {
  test("renders ollama and pi-hole panels read-only", async ({ page }) => {
    await page.goto("/system");

    await expect(page.getByText("Ollama (AI)")).toBeVisible({
      timeout: 20_000,
    });
    await expect(
      page.getByRole("heading", { name: "Pi-hole" }),
    ).toBeVisible();
    await expect(page.getByText("Startup checks")).toBeVisible();
  });

  test("reports home server state from the overview endpoint", async ({
    request,
  }) => {
    const response = await request.get("/api/v1/system/overview");
    expect(response.ok()).toBeTruthy();
    const body = await response.json();
    expect(body).toHaveProperty("ollama");
    expect(body).toHaveProperty("pihole");
    expect(body).toHaveProperty("startup.states");
    expect(Array.isArray(body.ollama.models)).toBe(true);
    expect(typeof body.pihole.configured).toBe("boolean");
  });
});