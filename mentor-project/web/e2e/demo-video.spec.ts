import { expect, test } from "@playwright/test";

/**
 * Backup demo recording (Phase 21, D21.2). Run with the demo config
 * (video on) against `mentor serve`. Cached answers → no model needed.
 * The .webm is runtime (git-ignored); its SHA-256 goes to docs/demo_recording.md.
 */
test("demo walkthrough recording", async ({ page }) => {
  await page.goto("/ask");
  await page.getByTestId("ask-box").fill(
    "How does user registration (`register_user`) work?"
  );
  await page.getByTestId("ask-run").click();
  await page.getByTestId("answer").waitFor({ timeout: 120000 });
  const chip = page.locator('[data-testid^="chip-"]').first();
  await chip.click();
  await expect(page.getByTestId("sha-banner")).toContainText(
    /\.py:\d+-\d+ @ [0-9a-f]{8,}/,
    { timeout: 30000 }
  );
  await page.goto("/arch");
  await page
    .locator('[data-testid="arch-svg"] svg, [data-testid="arch-list"]')
    .first()
    .waitFor({ timeout: 30000 });
  await page.goto("/tours");
  await page.getByText(/signs up/i).first().waitFor({ timeout: 30000 });
  await page.goto("/tasks");
  await page
    .getByRole("heading", { name: /starter tasks/i })
    .waitFor({ timeout: 30000 });
});
