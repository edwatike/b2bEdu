import { NextResponse } from "next/server"
import { cookies } from "next/headers"

const foldersCache = new Map<string, { expiresAt: number; data: any }>()

export async function GET(request: Request) {
  try {
    const cookieStore = await cookies()
    const access = cookieStore.get("yandex_oauth_access")?.value
    const email = cookieStore.get("yandex_oauth_email")?.value

    if (!access || !email) {
      return NextResponse.json({ error: "Yandex OAuth not connected" }, { status: 401 })
    }

    const cacheKey = `${email}`
    const cached = foldersCache.get(cacheKey)
    if (cached && cached.expiresAt > Date.now()) {
      return NextResponse.json(cached.data)
    }

    const controller = new AbortController()
    const timeoutMs = 15000
    const timeoutId = setTimeout(() => controller.abort(), timeoutMs)

    const backendResp = await fetch("http://127.0.0.1:8000/api/mail/yandex/imap/folders", {
      method: "POST",
      headers: {
        "Content-Type": "application/json",
      },
      body: JSON.stringify({
        access_token: access,
        email,
      }),
      cache: "no-store",
      signal: controller.signal,
    })

    clearTimeout(timeoutId)

    const data = (await backendResp.json().catch(() => null)) as any
    if (!backendResp.ok) {
      return NextResponse.json(
        { error: data?.detail || data?.error || `HTTP ${backendResp.status}` },
        { status: backendResp.status },
      )
    }

    foldersCache.set(cacheKey, { expiresAt: Date.now() + 30_000, data })
    return NextResponse.json(data)
  } catch (error) {
    const errorMessage = error instanceof Error ? error.message : String(error)
    return NextResponse.json({ error: errorMessage }, { status: 500 })
  }
}
