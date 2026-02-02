import { NextRequest, NextResponse } from "next/server"

export async function POST(request: NextRequest) {
  try {
    const { email } = await request.json()

    if (!email) {
      return NextResponse.json({ error: "Email is required" }, { status: 400 })
    }

    const backendResponse = await fetch("http://127.0.0.1:8000/api/auth/otp/request", {
      method: "POST",
      headers: {
        "Content-Type": "application/json",
      },
      body: JSON.stringify({ email }),
    })

    const data = await backendResponse.json().catch(() => ({}))

    if (!backendResponse.ok) {
      return NextResponse.json(
        { error: data.detail || "OTP request failed" },
        { status: backendResponse.status },
      )
    }

    return NextResponse.json({ success: true })
  } catch (error) {
    console.error("OTP request error:", error)
    return NextResponse.json({ error: "Internal server error" }, { status: 500 })
  }
}
