import { NextResponse } from "next/server"
import { cookies } from "next/headers"

export async function GET(_request: Request, context: { params: Promise<{ id: string }> }) {
  try {
    const { id } = (await context.params) as { id: string }

    const cookieStore = await cookies()
    const access = cookieStore.get("yandex_oauth_access")?.value
    const email = cookieStore.get("yandex_oauth_email")?.value

    if (!access || !email) {
      return NextResponse.json({ error: "Yandex OAuth not connected" }, { status: 401 })
    }

    const controller = new AbortController()
    const timeoutMs = 35000
    const timeoutId = setTimeout(() => controller.abort(), timeoutMs)

    const backendResp = await fetch(`http://127.0.0.1:8000/api/mail/yandex/imap/${encodeURIComponent(id)}`, {
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

    if (!backendResp.ok) {
      const errorText = await backendResp.text()
      return NextResponse.json(
        { error: `Backend mail API error: ${backendResp.status} - ${errorText}` },
        { status: backendResp.status }
      )
    }

    const data = await backendResp.json()
    return NextResponse.json(data)
  } catch (error) {
    const errorMessage = error instanceof Error ? error.message : String(error)
    return NextResponse.json({ error: errorMessage }, { status: 500 })
  }
}
