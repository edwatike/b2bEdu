import { NextResponse } from "next/server"
import type { NextRequest } from "next/server"

// Публичные пути, которые не требуют авторизации
const publicPaths = ["/", "/login", "/cabinet/login", "/api", "/webmail"]

function isCabinetPath(pathname: string): boolean {
  return pathname === "/cabinet" || pathname.startsWith("/cabinet/")
}

function isModeratorCabinetPath(pathname: string): boolean {
  return (
    pathname === "/moderator" ||
    pathname.startsWith("/moderator/") ||
    pathname === "/parsing-runs" ||
    pathname.startsWith("/parsing-runs/")
  )
}

type AuthMeResponse = {
  authenticated?: boolean
  user?: {
    role?: string
    can_access_moderator?: boolean
  }
}

async function getCurrentUser(request: NextRequest) {
  const token = request.cookies.get("auth_token")?.value

  const apiBase = process.env.NEXT_PUBLIC_API_URL || "http://127.0.0.1:8000"

  // No-auth mode support:
  // If backend is launched with auth bypass, it will return authenticated=true even without any token.
  // This makes Vercel frontend + ngrok backend usable without baking NEXT_PUBLIC_AUTH_BYPASS into Vercel env.
  if (!token) {
    try {
      const statusResp = await fetch(`${apiBase}/api/auth/status`, { cache: "no-store" })
      if (statusResp.ok) {
        const statusJson = (await statusResp.json().catch(() => null)) as AuthMeResponse | null
        if (statusJson?.authenticated) {
          return statusJson.user || { role: "admin", can_access_moderator: true }
        }
      }
    } catch {
      // ignore and fall through to unauthenticated
    }
    return null
  }

  const backendUrl = `${apiBase}/api/auth/me`
  try {
    const resp = await fetch(backendUrl, {
      headers: {
        Authorization: `Bearer ${token}`,
        "Content-Type": "application/json",
      },
      cache: "no-store",
    })

    if (!resp.ok) return null
    const data = (await resp.json().catch(() => null)) as AuthMeResponse | null
    if (!data?.authenticated) return null
    return data.user || null
  } catch {
    return null
  }
}

export async function proxy(request: NextRequest) {
  const host = request.headers.get("host") || ""
  const { pathname } = request.nextUrl
  if (host.startsWith("127.0.0.1:")) {
    // Do not canonicalize localhost/127.0.0.1 in middleware.
    // It breaks local tooling (MCP/browser automation) and can create redirect loops.
  }

  // Разрешаем публичные пути
  if (publicPaths.some((path) => pathname.startsWith(path))) {
    return NextResponse.next()
  }

  // Проверяем авторизацию (источник истины: backend)
  const user = await getCurrentUser(request)

  if (!user) {
    // Нет авторизации - перенаправляем на логин
    const loginUrl = new URL("/login", request.url)
    loginUrl.searchParams.set("redirect", pathname)
    return NextResponse.redirect(loginUrl)
  }

  const isCabinet = isCabinetPath(pathname)
  const role = String((user as any)?.role || "")
  const canAccessModerator = Boolean((user as any)?.can_access_moderator)

  // Обычные пользователи не могут попасть в модераторскую зону.
  // Модераторская зона — всё, что не /cabinet.
  if (!isCabinet && !canAccessModerator) {
    return NextResponse.redirect(new URL("/cabinet", request.url))
  }

  // В кабинет пускаем user и мастера-модератора.
  if (isCabinet && role !== "user" && !canAccessModerator) {
    return NextResponse.redirect(new URL("/cabinet", request.url))
  }

  // Пользователь авторизован - разрешаем доступ
  return NextResponse.next()
}

export const config = {
  matcher: [
    /*
     * Match all request paths except for the ones starting with:
     * - _next/static (static files)
     * - _next/image (image optimization files)
     * - favicon.ico (favicon file)
     * - public folder
     */
    "/((?!_next/static|_next/image|favicon.ico|public).*)",
  ],
}
