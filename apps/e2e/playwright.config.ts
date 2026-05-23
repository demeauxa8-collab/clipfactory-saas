import { defineConfig, devices } from "@playwright/test";

const baseURL = process.env.BASE_URL ?? "https://clipfactory.app";

export default defineConfig({
  testDir: "./test",
  timeout: 10 * 60 * 1000,
  expect: {
    timeout: 15 * 1000,
  },
  fullyParallel: false,
  forbidOnly: !!process.env.CI,
  retries: process.env.CI ? 1 : 0,
  workers: 1,
  reporter: process.env.CI ? [["github"], ["list"]] : "list",
  use: {
    baseURL,
    trace: "retain-on-failure",
    video: "retain-on-failure",
    screenshot: "only-on-failure",
    storageState: process.env.E2E_AUTH_STATE || undefined,
  },
  projects: [
    {
      name: "chromium",
      use: { ...devices["Desktop Chrome"] },
    },
  ],
});
