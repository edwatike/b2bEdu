import { defineConfig } from "@playwright/test"

export default defineConfig({
  testDir: "./tests",
  timeout: 3 * 60 * 1000,
  expect: {
    timeout: 30 * 1000,
  },
  retries: 0,
  reporter: [["list"]],
})
