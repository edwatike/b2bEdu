import { type NextRequest, NextResponse } from "next/server"

const API_BASE_URL = process.env.NEXT_PUBLIC_API_URL || "http://127.0.0.1:8000"

function buildProxyHeaders(request: NextRequest): Record<string, string> {
  const headers: Record<string, string> = {
    "ngrok-skip-browser-warning": "true",
  }

  const contentType = request.headers.get("content-type")
  if (contentType) {
    headers["Content-Type"] = contentType
  }

  const accept = request.headers.get("accept")
  if (accept) {
    headers["Accept"] = accept
  }

  const token = request.cookies.get("auth_token")?.value
  if (token) {
    headers["Authorization"] = `Bearer ${token}`
  }

  return headers
}

async function proxyFetch(request: NextRequest, url: string, method: string) {
  const headers = buildProxyHeaders(request)
  const hasBody = method !== "GET" && method !== "HEAD"
  const bodyBytes = hasBody ? await request.arrayBuffer() : null

  if (!hasBody) {
    delete headers["Content-Type"]
  }

  return fetch(url, {
    method,
    headers,
    body: hasBody && bodyBytes && bodyBytes.byteLength > 0 ? bodyBytes : undefined,
  })
}

export async function GET(request: NextRequest, { params }: { params: Promise<{ path: string[] }> }) {
  const { path } = await params
  const targetPath = "/" + path.join("/")
  const searchParams = request.nextUrl.searchParams.toString()
  const url = `${API_BASE_URL}${targetPath}${searchParams ? `?${searchParams}` : ""}`

  try {
    const response = await proxyFetch(request, url, "GET")

    if (!response.ok) {
      const errorText = await response.text()
      return NextResponse.json({ error: errorText }, { status: response.status })
    }

    const data = await response.json()
    return NextResponse.json(data)
  } catch (error) {
    console.error("[Proxy] Error:", error)
    return NextResponse.json({ error: "Failed to connect to backend" }, { status: 502 })
  }
}

export async function POST(request: NextRequest, { params }: { params: Promise<{ path: string[] }> }) {
  const { path } = await params
  const targetPath = "/" + path.join("/")
  const searchParams = request.nextUrl.searchParams.toString()
  const url = `${API_BASE_URL}${targetPath}${searchParams ? `?${searchParams}` : ""}`

  try {
    const response = await proxyFetch(request, url, "POST")

    if (!response.ok) {
      const errorText = await response.text()
      return NextResponse.json({ error: errorText }, { status: response.status })
    }

    const data = await response.json()
    return NextResponse.json(data)
  } catch (error) {
    console.error("[Proxy] Error:", error)
    return NextResponse.json({ error: "Failed to connect to backend" }, { status: 502 })
  }
}

export async function PUT(request: NextRequest, { params }: { params: Promise<{ path: string[] }> }) {
  const { path } = await params
  const targetPath = "/" + path.join("/")
  const searchParams = request.nextUrl.searchParams.toString()
  const url = `${API_BASE_URL}${targetPath}${searchParams ? `?${searchParams}` : ""}`

  try {
    const response = await proxyFetch(request, url, "PUT")

    if (!response.ok) {
      const errorText = await response.text()
      return NextResponse.json({ error: errorText }, { status: response.status })
    }

    const data = await response.json()
    return NextResponse.json(data)
  } catch (error) {
    console.error("[Proxy] Error:", error)
    return NextResponse.json({ error: "Failed to connect to backend" }, { status: 502 })
  }
}

export async function DELETE(request: NextRequest, { params }: { params: Promise<{ path: string[] }> }) {
  const { path } = await params
  const targetPath = "/" + path.join("/")
  const searchParams = request.nextUrl.searchParams.toString()
  const url = `${API_BASE_URL}${targetPath}${searchParams ? `?${searchParams}` : ""}`

  try {
    const response = await proxyFetch(request, url, "DELETE")

    if (response.status === 204) {
      return new NextResponse(null, { status: 204 })
    }

    if (!response.ok) {
      const errorText = await response.text()
      return NextResponse.json({ error: errorText }, { status: response.status })
    }

    const data = await response.json()
    return NextResponse.json(data)
  } catch (error) {
    console.error("[Proxy] Error:", error)
    return NextResponse.json({ error: "Failed to connect to backend" }, { status: 502 })
  }
}

export async function PATCH(request: NextRequest, { params }: { params: Promise<{ path: string[] }> }) {
  const { path } = await params
  const targetPath = "/" + path.join("/")
  const searchParams = request.nextUrl.searchParams.toString()
  const url = `${API_BASE_URL}${targetPath}${searchParams ? `?${searchParams}` : ""}`

  try {
    const response = await proxyFetch(request, url, "PATCH")

    if (!response.ok) {
      const errorText = await response.text()
      return NextResponse.json({ error: errorText }, { status: response.status })
    }

    const data = await response.json()
    return NextResponse.json(data)
  } catch (error) {
    console.error("[Proxy] Error:", error)
    return NextResponse.json({ error: "Failed to connect to backend" }, { status: 502 })
  }
}
