import { test, expect } from "@playwright/test"
import {
  loginByApiAndSetCookie,
  nowStamp,
  openBrowserWithCdpFallback,
  waitForRunsByKeys,
  waitForSuppliersInRequest,
} from "./e2e-helpers"

test("cabinet: create request (3 keys) -> submit -> moderator task exists -> 3 parsing runs -> suppliers appear", async () => {
  const CDP_URL = process.env.CDP_URL || "http://127.0.0.1:7000"
  const BASE_URL = process.env.BASE_URL || "http://localhost:3000"
  const API_BASE_URL = process.env.API_BASE_URL || "http://127.0.0.1:8000"
  const E2E_EMAIL = process.env.E2E_EMAIL || "edwatik@yandex.ru"

  const keys = ["Труба гофрированная", "Труба разборная", "Заглушка"]
  const title = `E2E 3 keys ${nowStamp()}`

  const { browser, context } = await openBrowserWithCdpFallback(CDP_URL)
  const page = await context.newPage()

  const accessToken = await loginByApiAndSetCookie(page, context, API_BASE_URL, E2E_EMAIL)

  // Ensure we are authenticated in this Chrome profile.
  await page.goto(`${BASE_URL}/cabinet`, { waitUntil: "domcontentloaded" })
  await page.waitForTimeout(800)

  // If redirected to login, fail fast (cookie auth is broken).
  expect(page.url()).not.toContain("/login")

  // Fill title
  await page.getByPlaceholder("Например: Поставщики бетона — Москва").fill(title)

  // Ensure we have exactly 3 key fields
  // There is at least one textarea by default. Add 2 more.
  await page.getByRole("button", { name: "Добавить позицию" }).click()
  await page.getByRole("button", { name: "Добавить позицию" }).click()

  const textareas = page.locator("textarea")
  await expect(textareas).toHaveCount(3, { timeout: 15_000 })

  for (let i = 0; i < keys.length; i++) {
    await textareas.nth(i).fill(keys[i])
  }

  // Submit
  await page.getByRole("button", { name: "Отправить в работу" }).click()

  // Redirect to request detail
  await page.waitForURL(/\/cabinet\/requests\/[0-9]+/, { timeout: 60_000 })
  const requestUrl = page.url()
  const m = requestUrl.match(/\/cabinet\/requests\/(\d+)/)
  expect(m).toBeTruthy()
  const requestId = Number(m?.[1])
  expect(Number.isFinite(requestId) && requestId > 0).toBeTruthy()

  // 1) Parsing runs exist for this request and include all keys.
  await waitForRunsByKeys(page, API_BASE_URL, accessToken, requestId, keys)

  // 2) Suppliers appear for this request in cabinet data.
  await waitForSuppliersInRequest(page, API_BASE_URL, accessToken, requestId)

  await page.close()
  await browser.close()
})
