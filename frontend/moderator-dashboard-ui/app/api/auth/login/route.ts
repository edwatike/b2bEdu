import { NextRequest, NextResponse } from "next/server"

export async function POST(request: NextRequest) {
  try {
    const { username, password } = await request.json()

    // Валидация входных данных
    if (!username || !password) {
      return NextResponse.json(
        { error: "Username and password are required" },
        { status: 400 }
      )
    }

    // Отправляем запрос на backend для аутентификации
    const backendUrl = `${process.env.NEXT_PUBLIC_API_URL || "http://127.0.0.1:8000"}/api/auth/login`
    const backendResponse = await fetch(backendUrl, {
      method: "POST",
      headers: {
        "Content-Type": "application/json",
      },
      body: JSON.stringify({ username, password }),
    })

    if (!backendResponse.ok) {
      const errorData = await backendResponse.json()
      return NextResponse.json(
        { error: errorData.detail || "Authentication failed" },
        { status: backendResponse.status }
      )
    }

    const data = await backendResponse.json()

    // Создаем ответ с токеном
    const response = NextResponse.json({
      success: true,
      user: data.user,
    })

    // Устанавливаем токен в cookie
    response.cookies.set("auth_token", data.access_token, {
      httpOnly: true, // Предотвращает доступ через JavaScript
      secure: process.env.NODE_ENV === "production", // Только HTTPS в production
      sameSite: "lax", // Защита от CSRF
      maxAge: 30 * 24 * 60 * 60, // 30 дней
      path: "/",
    })

    return response

  } catch (error) {
    console.error("Login error:", error)
    return NextResponse.json(
      { error: "Internal server error" },
      { status: 500 }
    )
  }
}
