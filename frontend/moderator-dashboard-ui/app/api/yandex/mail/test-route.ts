import { NextResponse } from "next/server"
import { cookies } from "next/headers"

export async function GET() {
  try {
    const cookieStore = await cookies()
    const access = cookieStore.get("yandex_oauth_access")?.value
    const email = cookieStore.get("yandex_oauth_email")?.value

    if (!access) {
      return NextResponse.json({
        error: "No access token found",
        cookies: {
          yandex_oauth_access: access,
          yandex_oauth_email: email,
          all_cookies: cookieStore.getAll().map(c => ({ name: c.name, value: c.value }))
        }
      }, { status: 401 })
    }

    // Пробуем получить реальные письма через бэкенд
    const mailResponse = await fetch("http://127.0.0.1:8000/api/mail/yandex/imap", {
      method: "POST",
      headers: {
        "Content-Type": "application/json",
      },
      body: JSON.stringify({
        access_token: access,
        limit: 5
      }),
      cache: "no-store",
    })

    if (!mailResponse.ok) {
      const errorText = await mailResponse.text()
      return NextResponse.json({
        error: "Backend mail API error",
        status: mailResponse.status,
        details: errorText,
        access_token_length: access.length
      }, { status: 500 })
    }

    const data = await mailResponse.json()
    return NextResponse.json({
      success: true,
      backend_response: data,
      access_token_length: access.length,
      email: email
    })

  } catch (error) {
    console.error("Test mail endpoint error:", error)
    return NextResponse.json({
      error: "Test endpoint error",
      details: error instanceof Error ? error.message : String(error)
    }, { status: 500 })
  }
}
