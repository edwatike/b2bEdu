import { NextResponse } from "next/server"
import { deleteAuthCookie } from "@/lib/auth"

function clearCookie(response: NextResponse, name: string) {
  response.cookies.set(name, "", {
    httpOnly: true,
    secure: process.env.NODE_ENV === "production",
    sameSite: "lax",
    maxAge: 0,
    path: "/",
  })
}

export async function POST() {
  try {
    // Создаем ответ и удаляем cookie
    const response = NextResponse.json({
      success: true,
      message: "Logged out successfully",
    })

    deleteAuthCookie(response)

    clearCookie(response, "yandex_oauth_access")
    clearCookie(response, "yandex_oauth_refresh")
    clearCookie(response, "yandex_oauth_email")
    clearCookie(response, "yandex_oauth_state")

    return response

  } catch (error) {
    console.error("Logout error:", error)
    return NextResponse.json(
      { error: "Internal server error" },
      { status: 500 }
    )
  }
}
