import { chromium } from "playwright"

const FRONTEND_URL = (process.env.FRONTEND_URL || "http://127.0.0.1:3000").trim()
const BACKEND_URL = (process.env.BACKEND_URL || "http://127.0.0.1:8000").trim()
const MODERATOR_EMAIL = (process.env.MODERATOR_EMAIL || "edwatik@yandex.ru").trim()
const USER_EMAIL = (process.env.USER_EMAIL || "user1@example.com").trim()
const FRONTEND_HOST = new URL(FRONTEND_URL).hostname
const FRONTEND_SECURE = new URL(FRONTEND_URL).protocol === "https:"

function normalizeUrl(path) {
  return new URL(path, FRONTEND_URL).toString()
}

function cookieForToken(token) {
  return [
    {
      name: "auth_token",
      value: token,
      domain: FRONTEND_HOST,
      path: "/",
      secure: FRONTEND_SECURE,
      sameSite: "Lax",
    },
  ]
}

async function login(email) {
  const payload = {
    email,
    yandex_access_token: "smoke-test",
    yandex_refresh_token: "",
    expires_in: 3600,
  }
  const resp = await fetch(`${BACKEND_URL}/api/auth/yandex-oauth`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(payload),
  })
  if (!resp.ok) {
    const text = await resp.text().catch(() => "")
    throw new Error(`Auth failed for ${email}: HTTP ${resp.status} ${text}`)
  }
  const data = await resp.json()
  if (!data?.access_token) {
    throw new Error(`Auth failed for ${email}: no access_token`)
  }
  return data.access_token
}

async function fetchJson(path, token) {
  const resp = await fetch(`${BACKEND_URL}${path}`, {
    headers: {
      Authorization: `Bearer ${token}`,
      "Content-Type": "application/json",
    },
  })
  if (!resp.ok) {
    return null
  }
  return await resp.json().catch(() => null)
}

async function getDynamicIds(modToken, userToken) {
  const ids = {
    runId: null,
    supplierId: null,
    requestId: null,
  }

  try {
    const runs = await fetchJson("/parsing/runs?limit=1&order=desc", modToken)
    const first = runs?.runs?.[0]
    ids.runId = first?.runId || first?.run_id || null
  } catch {
    ids.runId = null
  }

  try {
    const suppliers = await fetchJson("/moderator/suppliers?limit=1&offset=0", modToken)
    const s0 = suppliers?.suppliers?.[0]
    ids.supplierId = s0?.id || null
  } catch {
    ids.supplierId = null
  }

  try {
    const create = await fetch(`${BACKEND_URL}/cabinet/requests`, {
      method: "POST",
      headers: {
        Authorization: `Bearer ${userToken}`,
        "Content-Type": "application/json",
      },
      body: JSON.stringify({
        title: "Smoke test request",
        keys: ["smoke test"],
        depth: 1,
        source: "google",
      }),
    })
    if (create.ok) {
      const data = await create.json().catch(() => null)
      ids.requestId = data?.id || null
    }
  } catch {
    ids.requestId = null
  }

  return ids
}

async function checkRoutes(label, token, routes) {
  const browser = await chromium.launch()
  const context = await browser.newContext()
  await context.addCookies(cookieForToken(token))
  const page = await context.newPage()
  page.setDefaultTimeout(15000)

  const errors = []
  page.on("pageerror", (err) => errors.push(`pageerror: ${err.message}`))
  page.on("console", (msg) => {
    if (msg.type() === "error") {
      errors.push(`console: ${msg.text()}`)
    }
  })

  const results = []
  for (const route of routes) {
    const startErrors = errors.length
    const url = normalizeUrl(route)
    let status = 0
    let ok = false
    try {
      const resp = await page.goto(url, { waitUntil: "domcontentloaded" })
      status = resp?.status() || 0
      ok = status >= 200 && status < 400
    } catch (err) {
      errors.push(`nav: ${route} -> ${err?.message || String(err)}`)
      ok = false
    }
    const routeErrors = errors.slice(startErrors)
    results.push({ label, route, url, ok, status, errors: routeErrors })
  }

  await page.close()
  await context.close()
  await browser.close()

  return results
}

async function checkPublic() {
  const browser = await chromium.launch()
  const page = await browser.newPage()
  page.setDefaultTimeout(15000)

  const routes = ["/", "/login"]
  const results = []
  for (const route of routes) {
    let status = 0
    let ok = false
    try {
      const resp = await page.goto(normalizeUrl(route), { waitUntil: "domcontentloaded" })
      status = resp?.status() || 0
      ok = status >= 200 && status < 400
    } catch {
      ok = false
    }
    results.push({ label: "public", route, url: normalizeUrl(route), ok, status, errors: [] })
  }
  await page.close()
  await browser.close()
  return results
}

function printResults(results) {
  let failed = 0
  for (const r of results) {
    const flag = r.ok ? "PASS" : "FAIL"
    console.log(`[${flag}] ${r.label} ${r.route} -> ${r.status} ${r.url}`)
    if (r.errors.length > 0) {
      for (const e of r.errors) {
        console.log(`  - ${e}`)
      }
    }
    if (!r.ok) failed += 1
  }
  return failed
}

async function main() {
  const modToken = await login(MODERATOR_EMAIL)
  const userToken = await login(USER_EMAIL)
  const ids = await getDynamicIds(modToken, userToken)

  const modRun = ids.runId || "00000000-0000-0000-0000-000000000000"
  const modSupplier = ids.supplierId || 0
  const userRequest = ids.requestId || 0

  const moderatorRoutes = [
    "/moderator",
    "/manual-parsing",
    "/parsing-runs",
    `/parsing-runs/${modRun}`,
    "/keywords",
    "/blacklist",
    "/domains",
    "/suppliers",
    "/suppliers/new",
    `/suppliers/${modSupplier}`,
    `/suppliers/${modSupplier}/edit`,
    "/moderator/tasks",
    "/users",
    "/moderator/users",
    "/moderator/suppliers",
    "/settings",
  ]

  const userRoutes = [
    "/cabinet",
    "/cabinet/overview",
    "/cabinet/requests",
    "/cabinet/requests/all",
    "/cabinet/requests/drafts",
    `/cabinet/requests/${userRequest}`,
    "/cabinet/results",
    "/cabinet/messages",
    "/cabinet/settings",
  ]

  const publicResults = await checkPublic()
  const moderatorResults = await checkRoutes("moderator", modToken, moderatorRoutes)
  const userResults = await checkRoutes("user", userToken, userRoutes)
  const all = [...publicResults, ...moderatorResults, ...userResults]

  const failed = printResults(all)
  if (failed > 0) {
    console.error(`Failed routes: ${failed}`)
    process.exit(1)
  }
  console.log("All routes passed.")
}

main().catch((err) => {
  console.error(err)
  process.exit(1)
})
