import { NextResponse } from "next/server"
import { headers } from "next/headers"

function clearCookie(response: NextResponse, name: string, isLocalhost: boolean) {
  response.cookies.set(name, "", {
    httpOnly: true,
    secure: process.env.NODE_ENV === "production" && !isLocalhost,
    sameSite: "lax",
    maxAge: 0,
    path: "/",
  })
}

export async function POST() {
  const h = await headers()
  const host = h.get("x-forwarded-host") || h.get("host") || ""
  const isLocalhost = host.includes('localhost') || host.includes('127.0.0.1')
  
  const response = NextResponse.json({ success: true })
  clearCookie(response, "yandex_oauth_access", isLocalhost)
  clearCookie(response, "yandex_oauth_refresh", isLocalhost)
  clearCookie(response, "yandex_oauth_email", isLocalhost)
  clearCookie(response, "yandex_oauth_state", isLocalhost)
  clearCookie(response, "yandex_oauth_states", isLocalhost)
  return response
}
