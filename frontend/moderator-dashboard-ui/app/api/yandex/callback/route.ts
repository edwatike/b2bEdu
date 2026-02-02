import { NextRequest, NextResponse } from "next/server"
import { cookies } from "next/headers"

async function fetchYandexUserEmail(accessToken: string): Promise<string | null> {
  try {
    const resp = await fetch("https://login.yandex.ru/info?format=json", {
      headers: {
        Authorization: `OAuth ${accessToken}`,
      },
      cache: "no-store",
    })

    if (!resp.ok) return null
    const data = (await resp.json().catch(() => null)) as any
    const email = typeof data?.default_email === "string" ? data.default_email : null
    return email
  } catch {
    return null
  }
}

export async function GET(request: NextRequest) {
  const url = new URL(request.url)
  const code = url.searchParams.get("code")
  const state = url.searchParams.get("state")
  const error = url.searchParams.get("error")
  const errorDescription = url.searchParams.get("error_description")
  
  const isLocalhost = url.origin.includes('localhost') || url.origin.includes('127.0.0.1')

  const clientId = process.env.YANDEX_CLIENT_ID
  const clientSecret = process.env.YANDEX_CLIENT_SECRET
  const redirectUri = process.env.YANDEX_REDIRECT_URI || `${url.origin}/api/yandex/callback`

  if (!clientId || !clientSecret) {
    return NextResponse.json({ error: "Yandex OAuth is not configured" }, { status: 500 })
  }

  // Обработка OAuth ошибок от Яндекса
  if (error) {
    let userMessage = "Ошибка авторизации через Яндекс"
    
    switch (error) {
      case "invalid_scope":
        userMessage = "Приложению не хватает прав для доступа к почте. Обратитесь к администратору."
        break
      case "access_denied":
        userMessage = "Доступ запрещен. Вы отказали в предоставлении прав приложению."
        break
      case "unauthorized_client":
        userMessage = "Приложение не авторизовано. Проверьте настройки клиента."
        break
      case "unsupported_response_type":
        userMessage = "Неподдерживаемый тип ответа. Обратитесь к администратору."
        break
      case "server_error":
        userMessage = "Ошибка сервера Яндекса. Попробуйте позже."
        break
      case "temporarily_unavailable":
        userMessage = "Сервис временно недоступен. Попробуйте позже."
        break
      default:
        userMessage = `Ошибка OAuth: ${error}`
    }

    // Перенаправляем на единую страницу входа с параметром ошибки
    const loginUrl = new URL("/login", request.url)
    loginUrl.searchParams.set("error", "yandex_oauth_failed")
    loginUrl.searchParams.set("message", userMessage)
    if (errorDescription) {
      loginUrl.searchParams.set("details", decodeURIComponent(errorDescription))
    }
    
    return NextResponse.redirect(loginUrl.toString())
  }

  if (!code) {
    return NextResponse.json({ error: "Missing code" }, { status: 400 })
  }

  const cookieStore = await cookies()
  const expectedState = cookieStore.get("yandex_oauth_state")?.value
  const expectedStatesRaw = cookieStore.get("yandex_oauth_states")?.value
  let expectedStates: string[] = []
  if (expectedStatesRaw) {
    try {
      // Decode URL-encoded cookie value first
      const decodedStates = decodeURIComponent(expectedStatesRaw)
      const parsed = JSON.parse(decodedStates)
      if (Array.isArray(parsed)) {
        expectedStates = parsed.filter((v) => typeof v === "string")
      }
    } catch {
      expectedStates = []
    }
  }

  const stateOk = Boolean(state) && (expectedStates.includes(String(state)) || expectedState === state)
  if (!stateOk) {
    return NextResponse.json({ error: "Invalid state" }, { status: 400 })
  }

  // Consume matched state so old links can't be replayed and multi-tab remains stable
  if (state) {
    const nextStates = expectedStates.filter((s) => s !== state)
    cookieStore.set("yandex_oauth_states", JSON.stringify(nextStates), {
      httpOnly: true,
      secure: process.env.NODE_ENV === "production" && !isLocalhost,
      sameSite: "lax",
      maxAge: 10 * 60,
      path: "/",
    })
  }

  const tokenResp = await fetch("https://oauth.yandex.ru/token", {
    method: "POST",
    headers: {
      "Content-Type": "application/x-www-form-urlencoded",
    },
    body: new URLSearchParams({
      grant_type: "authorization_code",
      code,
      client_id: clientId,
      client_secret: clientSecret,
      redirect_uri: redirectUri,
    }).toString(),
  })

  const tokenData = (await tokenResp.json().catch(() => ({}))) as any
  if (!tokenResp.ok) {
    return NextResponse.json({ error: tokenData?.error_description || tokenData?.error || "Token exchange failed" }, { status: 500 })
  }

  const accessToken = String(tokenData.access_token || "")
  const refreshToken = String(tokenData.refresh_token || "")
  const expiresIn = Number(tokenData.expires_in || 0)

  if (!accessToken) {
    return NextResponse.json({ error: "Missing access_token" }, { status: 500 })
  }

  const email = await fetchYandexUserEmail(accessToken)

  if (!email) {
    return NextResponse.redirect(new URL("/login?error=yandex_oauth_failed&message=Не удалось получить email от Яндекса", request.url))
  }

  // Регистрируем/авторизуем пользователя в backend
  try {
    const backendResponse = await fetch(`${process.env.NEXT_PUBLIC_API_URL || "http://127.0.0.1:8000"}/api/auth/yandex-oauth`, {
      method: "POST",
      headers: {
        "Content-Type": "application/json",
      },
      body: JSON.stringify({
        email: email,
        yandex_access_token: accessToken,
        yandex_refresh_token: refreshToken,
        expires_in: expiresIn
      }),
    })

    if (!backendResponse.ok) {
      const errorData = await backendResponse.json().catch(() => ({}))
      const msg =
        (typeof (errorData as any)?.detail === "string" && (errorData as any).detail) ||
        (typeof (errorData as any)?.error === "string" && (errorData as any).error) ||
        "Ошибка регистрации пользователя"
      return NextResponse.redirect(new URL(`/login?error=yandex_oauth_failed&message=${encodeURIComponent(msg)}`, request.url))
    }

    const authData = await backendResponse.json()
    
    const masterEmail = (process.env.MODERATOR_MASTER_EMAIL || "edwatik@yandex.ru").trim().toLowerCase()
    const targetPath = email.trim().toLowerCase() === masterEmail ? "/moderator" : "/cabinet"

    // Создаем ответ с перенаправлением и устанавливаем JWT токен
    const response = NextResponse.redirect(new URL(targetPath, request.url))
    
    // Устанавливаем JWT токен от backend (AuthGuard ожидает cookie auth_token)
    if (authData.access_token) {
      const isLocalhost = url.origin.includes('localhost') || url.origin.includes('127.0.0.1')
      response.cookies.set("auth_token", authData.access_token, {
        httpOnly: true,
        secure: process.env.NODE_ENV === "production" && !isLocalhost,
        sameSite: "lax",
        maxAge: authData.expires_in ? authData.expires_in : 60 * 60,
        path: "/",
      })
    }

    // Очищаем OAuth state
    response.cookies.set("yandex_oauth_state", "", {
      httpOnly: true,
      secure: process.env.NODE_ENV === "production" && !isLocalhost,
      sameSite: "lax",
      maxAge: 0,
      path: "/",
    })

    // Сохраняем Яндекс токены для будущих запросов
    response.cookies.set("yandex_oauth_access", accessToken, {
      httpOnly: true,
      secure: process.env.NODE_ENV === "production" && !isLocalhost,
      sameSite: "lax",
      maxAge: expiresIn > 0 ? expiresIn : 60 * 60,
      path: "/",
    })

    if (refreshToken) {
      response.cookies.set("yandex_oauth_refresh", refreshToken, {
        httpOnly: true,
        secure: process.env.NODE_ENV === "production" && !isLocalhost,
        sameSite: "lax",
        maxAge: 30 * 24 * 60 * 60,
        path: "/",
      })
    }

    // Сохраняем email пользователя
    response.cookies.set("yandex_oauth_email", email, {
      httpOnly: true,
      secure: process.env.NODE_ENV === "production" && !isLocalhost,
      sameSite: "lax",
      maxAge: 30 * 24 * 60 * 60,
      path: "/",
    })

    return response

  } catch (error) {
    console.error("Yandex OAuth backend registration error:", error)
    return NextResponse.redirect(new URL("/login?error=yandex_oauth_failed&message=Ошибка подключения к серверу", request.url))
  }
}
