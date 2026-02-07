import { NextResponse, NextRequest } from "next/server"
import { cookies } from "next/headers"

export async function GET(request: NextRequest) {
  try {
    const cookieStore = await cookies()
    const allCookies = cookieStore.getAll()
    
    // Проверяем все cookies
    const yandexCookies = allCookies.filter(c => c.name.includes('yandex'))
    const authCookie = allCookies.find(c => c.name === 'auth_token')
    
    return NextResponse.json({
      total_cookies: allCookies.length,
      yandex_cookies: yandexCookies.map(c => ({
        name: c.name,
        value: c.value.substring(0, 20) + "...",
        length: c.value.length
      })),
      auth_cookie: authCookie ? {
        name: authCookie.name,
        value: authCookie.value.substring(0, 20) + "...",
        length: authCookie.value.length
      } : null,
      all_cookie_names: allCookies.map(c => c.name)
    })
  } catch (error) {
    return NextResponse.json({
      error: "Cookie check failed",
      details: error instanceof Error ? error.message : String(error)
    }, { status: 500 })
  }
}
