import { NextResponse } from "next/server"
import { cookies } from "next/headers"

export async function GET() {
  try {
    const cookieStore = await cookies()
    const token = cookieStore.get("auth_token")?.value

    if (!token) {
      return NextResponse.json({ authenticated: false, user: null })
    }

    const backendUrl = `${process.env.NEXT_PUBLIC_API_URL || "http://127.0.0.1:8000"}/api/auth/me`
    const backendResp = await fetch(backendUrl, {
      headers: {
        Authorization: `Bearer ${token}`,
        "Content-Type": "application/json",
      },
      cache: "no-store",
    })

    if (!backendResp.ok) {
      return NextResponse.json({ authenticated: false, user: null })
    }

    const data = await backendResp.json().catch(() => ({ authenticated: false }))
    return NextResponse.json(data)
  } catch (error) {
    const detail =
      process.env.NODE_ENV === "development"
        ? (error instanceof Error
            ? { message: error.message, stack: error.stack }
            : { message: String(error) })
        : undefined
    return NextResponse.json({ authenticated: false, user: null, detail })
  }
}
