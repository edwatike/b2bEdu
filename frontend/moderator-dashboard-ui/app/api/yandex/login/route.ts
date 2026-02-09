import { NextResponse } from "next/server"
import { cookies } from "next/headers"
import { headers } from "next/headers"
import crypto from "crypto"

export async function GET() {
  const clientId = process.env.YANDEX_CLIENT_ID
  const h = await headers()
  const host = h.get("x-forwarded-host") || h.get("host")
  const proto = h.get("x-forwarded-proto") || "http"
  const origin = host ? `${proto}://${host}` : "http://localhost:3000"

  // IMPORTANT: keep OAuth flow on a single host.
  // If we start at 127.0.0.1, cookies will be bound to 127.0.0.1 and won't be sent to localhost callback.
  // This leads to invalid state and endless relogin/redirect loops.
  if (host && host.startsWith("127.0.0.1:")) {
    return NextResponse.redirect(`${proto}://localhost:3000/api/yandex/login`)
  }

  const configuredRedirectUri = process.env.YANDEX_REDIRECT_URI
  let redirectUri = configuredRedirectUri || `${origin}/api/yandex/callback`

  if (configuredRedirectUri) {
    try {
      const configured = new URL(configuredRedirectUri)
      const configuredIsLocalhost = configured.hostname === "localhost" || configured.hostname === "127.0.0.1"

      const current = new URL(origin)
      const currentIsLocalhost = current.hostname === "localhost" || current.hostname === "127.0.0.1"

      if (!currentIsLocalhost && configuredIsLocalhost) {
        redirectUri = `${origin}/api/yandex/callback`
      }
    } catch {
      redirectUri = `${origin}/api/yandex/callback`
    }
  }

  if (!clientId) {
    return NextResponse.json({ error: "YANDEX_CLIENT_ID is not configured" }, { status: 500 })
  }

  const state = crypto.randomBytes(16).toString("hex")
  const cookieStore = await cookies()
  const existingStatesRaw = cookieStore.get("yandex_oauth_states")?.value
  let states: string[] = []
  if (existingStatesRaw) {
    try {
      const parsed = JSON.parse(existingStatesRaw)
      if (Array.isArray(parsed)) {
        states = parsed.filter((v) => typeof v === "string")
      }
    } catch {
      states = []
    }
  }
  states = [state, ...states].slice(0, 5)

  const isLocalhost = origin.includes('localhost') || origin.includes('127.0.0.1')
  
  cookieStore.set("yandex_oauth_states", JSON.stringify(states), {
    httpOnly: true,
    secure: process.env.NODE_ENV === "production" && !isLocalhost,
    sameSite: "lax",
    maxAge: 10 * 60,
    path: "/",
  })

  cookieStore.set("yandex_oauth_redirect_uri", redirectUri, {
    httpOnly: true,
    secure: process.env.NODE_ENV === "production" && !isLocalhost,
    sameSite: "lax",
    maxAge: 10 * 60,
    path: "/",
  })

  // Backward compatibility
  cookieStore.set("yandex_oauth_state", state, {
    httpOnly: true,
    secure: process.env.NODE_ENV === "production" && !isLocalhost,
    sameSite: "lax",
    maxAge: 10 * 60,
    path: "/",
  })

  const scope = process.env.YANDEX_SCOPE?.trim()

  const authorizeUrl = new URL("https://oauth.yandex.ru/authorize")
  authorizeUrl.searchParams.set("response_type", "code")
  authorizeUrl.searchParams.set("client_id", clientId)
  authorizeUrl.searchParams.set("redirect_uri", redirectUri)
  if (scope) {
    authorizeUrl.searchParams.set("scope", scope)
  }
  authorizeUrl.searchParams.set("state", state)

  return NextResponse.redirect(authorizeUrl.toString())
}
