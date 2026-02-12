import { type NextRequest, NextResponse } from "next/server"

const API_BASE_URL = process.env.NEXT_PUBLIC_API_URL || "http://127.0.0.1:8000"

export async function GET(request: NextRequest, context: { params: Promise<any> }) {
  const { id } = (await context.params) as { id: string }
  const url = `${API_BASE_URL}/attachments/${encodeURIComponent(id)}`

  const headers: Record<string, string> = {
    "ngrok-skip-browser-warning": "true",
  }

  const token = request.cookies.get("auth_token")?.value
  if (token) {
    headers["Authorization"] = `Bearer ${token}`
  }

  try {
    const response = await fetch(url, {
      method: "GET",
      headers,
    })

    const body = await response.arrayBuffer()

    const outHeaders = new Headers()
    const contentType = response.headers.get("content-type")
    if (contentType) outHeaders.set("content-type", contentType)

    const disposition = response.headers.get("content-disposition")
    if (disposition) outHeaders.set("content-disposition", disposition)

    return new NextResponse(body, {
      status: response.status,
      headers: outHeaders,
    })
  } catch (error) {
    console.error("[attachments proxy] error", error)
    return NextResponse.json({ error: "Failed to download attachment" }, { status: 502 })
  }
}
