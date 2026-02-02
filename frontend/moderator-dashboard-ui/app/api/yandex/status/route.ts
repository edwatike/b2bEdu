import { NextResponse } from "next/server"
import { cookies } from "next/headers"

export async function GET() {
  const cookieStore = await cookies()
  const access = cookieStore.get("yandex_oauth_access")?.value
  const email = cookieStore.get("yandex_oauth_email")?.value

  return NextResponse.json({
    connected: Boolean(access),
    email: email || null,
  })
}
