import { defineConfig, devices } from "@playwright/test";

// Demo-recording config (Phase 21, D21.2): video ON, desktop viewport.
// Run: npx playwright test -c playwright.demo.config.ts
// Output: ../data/demo_recording/ (git-ignored runtime).
export default defineConfig({
  testDir: "./e2e",
  testMatch: "demo-video.spec.ts",
  timeout: 300000,
  outputDir: "../data/demo_recording",
  use: {
    baseURL: "http://127.0.0.1:8000",
    video: "on",
  },
  projects: [
    {
      name: "chromium",
      use: {
        ...devices["Desktop Chrome"],
        viewport: { width: 1280, height: 800 },
      },
    },
  ],
});
