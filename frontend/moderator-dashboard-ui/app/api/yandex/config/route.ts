import { NextResponse } from "next/server"

export async function GET() {
  const clientId = process.env.YANDEX_CLIENT_ID
  const clientSecret = process.env.YANDEX_CLIENT_SECRET
  
  // Проверяем, настроен ли Яндекс OAuth
  const isConfigured = Boolean(clientId && clientSecret && clientId.trim() !== "" && clientSecret.trim() !== "")
  
  return NextResponse.json({
    yandexOAuthEnabled: isConfigured
  })
}
