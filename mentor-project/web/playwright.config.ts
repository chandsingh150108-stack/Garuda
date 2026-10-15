import { defineConfig, devices } from "@playwright/test";

export default defineConfig({
  testDir: "./e2e",
  timeout: 180000,
  use: {
    baseURL: "http://127.0.0.1:8000",
  },
  projects: [{ name: "chromium", use: { ...devices["Desktop Chrome"] } }],
});
