import { expect, type Browser, type BrowserContext, type Page } from "@playwright/test"
import { chromium } from "playwright"

export function nowStamp(): string {
  const d = new Date()
  const pad = (n: number) => String(n).padStart(2, "0")
  return (
    d.getFullYear() +
    pad(d.getMonth() + 1) +
    pad(d.getDate()) +
    "_" +
    pad(d.getHours()) +
    pad(d.getMinutes()) +
    pad(d.getSeconds())
  )
}

export async function openBrowserWithCdpFallback(cdpUrl: string): Promise<{ browser: Browser; context: BrowserContext }> {
  let browser: Browser
  try {
    browser = await chromium.connectOverCDP(cdpUrl)
  } catch {
    browser = await chromium.launch({ headless: true })
  }
  const context = browser.contexts()[0] || (await browser.newContext())
  return { browser, context }
}

export async function loginByApiAndSetCookie(
  page: Page,
  context: BrowserContext,
  apiBaseUrl: string,
  email: string,
): Promise<string> {
  const authResp = await page.request.post(`${apiBaseUrl}/api/auth/yandex-oauth`, {
    data: {
      email,
      yandex_access_token: "e2e-mock-token",
      yandex_refresh_token: "e2e-mock-refresh",
      expires_in: 3600,
    },
  })
  expect(authResp.ok()).toBeTruthy()
  const authJson = (await authResp.json()) as { access_token?: string }
  const accessToken = authJson?.access_token
  expect(accessToken).toBeTruthy()

  await context.addCookies([
    {
      name: "auth_token",
      value: String(accessToken),
      domain: "localhost",
      path: "/",
      httpOnly: false,
      secure: false,
      sameSite: "Lax",
    },
    {
      name: "auth_token",
      value: String(accessToken),
      domain: "127.0.0.1",
      path: "/",
      httpOnly: false,
      secure: false,
      sameSite: "Lax",
    },
  ])

  return String(accessToken)
}

export async function waitForRunsByKeys(
  page: Page,
  apiBaseUrl: string,
  accessToken: string,
  requestId: number,
  keys: string[],
): Promise<void> {
  await expect
    .poll(
      async () => {
        const resp = await page.request.get(`${apiBaseUrl}/parsing/runs?request_id=${requestId}&limit=100&offset=0`, {
          headers: { Authorization: `Bearer ${accessToken}` },
        })
        if (!resp.ok()) return false
        const payload = (await resp.json()) as { runs?: Array<{ keyword?: string }> }
        const runKeywords = (payload.runs || []).map((r) => String(r.keyword || "").toLowerCase())
        return keys.every((k) => runKeywords.some((rk) => rk.includes(k.toLowerCase())))
      },
      { timeout: 180_000, intervals: [1000, 2000, 4000, 6000, 8000] },
    )
    .toBe(true)
}

export async function waitForSuppliersInRequest(
  page: Page,
  apiBaseUrl: string,
  accessToken: string,
  requestId: number,
): Promise<void> {
  await expect
    .poll(
      async () => {
        const resp = await page.request.get(`${apiBaseUrl}/cabinet/requests/${requestId}/suppliers`, {
          headers: { Authorization: `Bearer ${accessToken}` },
        })
        if (!resp.ok()) return 0
        const suppliers = (await resp.json()) as Array<unknown>
        return Array.isArray(suppliers) ? suppliers.length : 0
      },
      { timeout: 240_000, intervals: [2000, 4000, 8000, 12000] },
    )
    .toBeGreaterThan(0)
}
