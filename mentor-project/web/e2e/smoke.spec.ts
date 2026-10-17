import { expect, test } from "@playwright/test";

/**
 * End-to-end citation proof: register -> ask signup -> click chip ->
 * code view shows the cited lines at the cited SHA. Requires the backend
 * (`mentor serve`) and a model server running (see DEMO_RUNBOOK).
 */
test("citation opens the exact cited lines", async ({ page }) => {
  await page.goto("/");
  await page.getByRole("link", { name: "Ask", exact: true }).click();
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
  const banner = await page.getByTestId("sha-banner").textContent();
  expect(banner).toMatch(/\.py:\d+-\d+ @ [0-9a-f]{8,}/);
});

test("ask state survives citation navigation and back", async ({ page }) => {
  const question = "How does user registration (`register_user`) work?";
  await page.goto("/ask");
  await page.getByTestId("ask-box").fill(question);
  await page.getByTestId("ask-run").click();
  await page.getByTestId("answer").waitFor({ timeout: 120000 });
  const chip = page.locator('[data-testid^="chip-"]').first();
  await chip.click();
  await expect(page.getByTestId("sha-banner")).toContainText(
    /\.py:\d+-\d+ @ [0-9a-f]{8,}/,
    { timeout: 30000 }
  );
  await page.goBack();
  await expect(page.getByTestId("ask-box")).toHaveValue(question, {
    timeout: 30000,
  });
  await expect(page.getByTestId("answer")).toBeVisible({ timeout: 30000 });
});

test("stale badge shows on content-hash mismatch (Phase 17)", async ({
  page,
}) => {
  // A bogus ?hash= can never match the current lines: the badge must show
  // without any model call (code endpoint only reads files).
  await page.goto(
    "/code?repo=fst&path=backend/app/main.py&start=1&end=5&hash=deadbeef"
  );
  await expect(page.getByTestId("sha-banner")).toContainText(
    /stale-citation/,
    { timeout: 30000 }
  );
});

test("layout has no body horizontal scroll at 1280 and 400px", async ({  page,
}) => {
  for (const width of [1280, 400]) {
    await page.setViewportSize({ width, height: 800 });
    await page.goto("/ask");
    const overflow = await page.evaluate(
      () => document.scrollingElement!.scrollWidth - window.innerWidth
    );
    expect(overflow).toBeLessThanOrEqual(1);
  }
});
