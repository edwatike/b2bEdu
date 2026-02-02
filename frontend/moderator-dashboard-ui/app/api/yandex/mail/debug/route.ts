import { NextResponse } from "next/server"
import { cookies } from "next/headers"

export async function GET() {
  try {
    const cookieStore = await cookies()
    const access = cookieStore.get("yandex_oauth_access")?.value
    const email = cookieStore.get("yandex_oauth_email")?.value
    const refresh = cookieStore.get("yandex_oauth_refresh")?.value

    return NextResponse.json({
      cookies_found: {
        yandex_oauth_access: !!access,
        yandex_oauth_email: !!email,
        yandex_oauth_refresh: !!refresh,
        access_length: access?.length || 0,
        email_value: email || "not_found",
        all_cookies_count: cookieStore.getAll().length
      },
      all_cookies: cookieStore.getAll().map(c => ({ 
        name: c.name, 
        value: (c.value.length > 20 ? c.value.substring(0, 20) + "..." : c.value)
      }))
    })

  } catch (error) {
    return NextResponse.json({
      error: "Debug endpoint error",
      details: error instanceof Error ? error.message : String(error)
    }, { status: 500 })
  }
}
