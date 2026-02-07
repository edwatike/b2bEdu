import { NextResponse } from "next/server"
import { cookies } from "next/headers"

const mailListCache = new Map<string, { expiresAt: number; data: any }>()

// Функция для получения писем через Yandex Mail API
async function fetchYandexEmails(accessToken: string, email: string, limit = 20, folder = "INBOX") {
  try {
    const controller = new AbortController()
    const timeoutMs = 35000
    const timeoutId = setTimeout(() => controller.abort(), timeoutMs)

    // Используем бэкенд для доступа к почте через IMAP
    const mailResponse = await fetch("http://127.0.0.1:8000/api/mail/yandex/imap", {
      method: "POST",
      headers: {
        "Content-Type": "application/json",
      },
      body: JSON.stringify({
        access_token: accessToken,
        email,
        limit: limit,
        folder,
      }),
      cache: "no-store",
      signal: controller.signal,
    })

    clearTimeout(timeoutId)

    if (!mailResponse.ok) {
      const errorText = await mailResponse.text()
      throw new Error(`Backend mail API error: ${mailResponse.status} - ${errorText}`)
    }

    const data = await mailResponse.json()
    return data.messages || []
  } catch (error) {
    console.error("Error fetching emails via backend:", error)
    if (error instanceof Error && error.name === "AbortError") {
      throw new Error("Backend mail API timeout")
    }
    throw error
  }
}

async function refreshYandexAccessToken(refreshToken: string) {
  const clientId = process.env.YANDEX_CLIENT_ID
  const clientSecret = process.env.YANDEX_CLIENT_SECRET

  if (!clientId || !clientSecret) {
    throw new Error("Yandex OAuth is not configured")
  }

  const tokenResp = await fetch("https://oauth.yandex.ru/token", {
    method: "POST",
    headers: {
      "Content-Type": "application/x-www-form-urlencoded",
    },
    body: new URLSearchParams({
      grant_type: "refresh_token",
      refresh_token: refreshToken,
      client_id: clientId,
      client_secret: clientSecret,
    }).toString(),
    cache: "no-store",
  })

  const tokenData = (await tokenResp.json().catch(() => ({}))) as any
  if (!tokenResp.ok) {
    throw new Error(tokenData?.error_description || tokenData?.error || "Token refresh failed")
  }

  const accessToken = String(tokenData.access_token || "")
  const newRefreshToken = String(tokenData.refresh_token || "")
  const expiresIn = Number(tokenData.expires_in || 0)

  if (!accessToken) {
    throw new Error("Missing access_token")
  }

  return { accessToken, refreshToken: newRefreshToken || refreshToken, expiresIn }
}

// Функция для форматирования писем в нужный формат
function formatEmails(rawEmails: any[]): any[] {
  return rawEmails.map((email, index) => ({
    id: email.id || `email_${index}`,
    subject: email.subject || "(Без темы)",
    from_email: email.from_email || email.from || email.sender || "unknown@example.com",
    to_email: email.to_email || email.to || email.recipient || "me@example.com",
    date: email.date || email.timestamp || new Date().toISOString(),
    body: email.body || email.snippet || email.content || "",
    status: "received",
    attachments_count: email.attachments?.length || 0,
    is_read: typeof email.is_read === "boolean" ? email.is_read : Boolean(email.isRead || email.seen),
  }))
}

// GET - получение писем
export async function GET(request: Request) {
  try {
    const cookieStore = await cookies()
    const access = cookieStore.get("yandex_oauth_access")?.value
    const email = cookieStore.get("yandex_oauth_email")?.value
    const refresh = cookieStore.get("yandex_oauth_refresh")?.value

    if (!access || !email) {
      return NextResponse.json(
        { error: "Yandex OAuth not connected" },
        { status: 401 }
      )
    }

    const { searchParams } = new URL(request.url)
    const limit = parseInt(searchParams.get("limit") || "20")
    const page = parseInt(searchParams.get("page") || "1")
    const folder = String(searchParams.get("folder") || "INBOX")

    const cacheKey = `${email}::${folder}::${limit}::${page}`
    const cached = mailListCache.get(cacheKey)
    if (cached && cached.expiresAt > Date.now()) {
      return NextResponse.json(cached.data)
    }

    // Получаем письма с Яндекс.Почты
    let rawEmails: any[] = []
    try {
      rawEmails = await fetchYandexEmails(access, email, limit, folder)
    } catch (e) {
      const message = e instanceof Error ? e.message : String(e)

      // If access token expired/revoked, try refresh once
      if (refresh && message.includes("401")) {
        const refreshed = await refreshYandexAccessToken(refresh)
        rawEmails = await fetchYandexEmails(refreshed.accessToken, email, limit, folder)

        const response = NextResponse.json({
          messages: formatEmails(Array.isArray(rawEmails) ? rawEmails : [rawEmails]),
          total: Array.isArray(rawEmails) ? rawEmails.length : 1,
          page,
          limit,
        })

        const isLocalhost = new URL(request.url).origin.includes("localhost") || new URL(request.url).origin.includes("127.0.0.1")

        response.cookies.set("yandex_oauth_access", refreshed.accessToken, {
          httpOnly: true,
          secure: process.env.NODE_ENV === "production" && !isLocalhost,
          sameSite: "lax",
          maxAge: refreshed.expiresIn > 0 ? refreshed.expiresIn : 60 * 60,
          path: "/",
        })
        response.cookies.set("yandex_oauth_refresh", refreshed.refreshToken, {
          httpOnly: true,
          secure: process.env.NODE_ENV === "production" && !isLocalhost,
          sameSite: "lax",
          maxAge: 30 * 24 * 60 * 60,
          path: "/",
        })

        return response
      }

      throw e
    }
    
    // Форматируем письма
    const formattedEmails = formatEmails(Array.isArray(rawEmails) ? rawEmails : [rawEmails])

    const payload = {
      messages: formattedEmails,
      total: formattedEmails.length,
      page,
      limit,
    }

    mailListCache.set(cacheKey, { expiresAt: Date.now() + 10_000, data: payload })
    return NextResponse.json(payload)
  } catch (error) {
    console.error("Error fetching Yandex emails:", error)
    const errorMessage = error instanceof Error ? error.message : String(error)

    return NextResponse.json({
      messages: [],
      total: 0,
      page: 1,
      limit: 20,
      demo: false,
      error: errorMessage,
    })
  }
}

// POST - отправка письма
export async function POST(request: Request) {
  try {
    const cookieStore = await cookies()
    const access = cookieStore.get("yandex_oauth_access")?.value
    const email = cookieStore.get("yandex_oauth_email")?.value

    if (!access || !email) {
      return NextResponse.json(
        { error: "Yandex OAuth not connected" },
        { status: 401 }
      )
    }

    const { to_email, subject, body } = await request.json()

    if (!to_email || !subject || !body) {
      return NextResponse.json(
        { error: "Missing required fields: to_email, subject, body" },
        { status: 400 }
      )
    }

    // Отправляем письмо через backend SMTP XOAUTH2 (надёжнее, чем неофициальные HTTP-эндпоинты)
    const smtpResponse = await fetch("http://127.0.0.1:8000/api/mail/yandex/smtp/send", {
      method: "POST",
      headers: {
        "Content-Type": "application/json",
      },
      body: JSON.stringify({
        access_token: access,
        email,
        to_email,
        subject,
        body,
      }),
    })

    if (!smtpResponse.ok) {
      const errorText = await smtpResponse.text().catch(() => "")
      return NextResponse.json(
        { error: `SMTP API error: ${smtpResponse.status} - ${errorText}` },
        { status: 502 }
      )
    }

    return NextResponse.json({
      success: true,
      status: "sent",
    })
  } catch (error) {
    console.error("Error sending Yandex email:", error)
    const errorMessage = error instanceof Error ? error.message : String(error)
    return NextResponse.json({ error: errorMessage }, { status: 500 })
  }
}
