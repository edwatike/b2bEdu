import { NextResponse } from "next/server"

export async function GET() {
  const clientId = process.env.YANDEX_CLIENT_ID
  const redirectUri = process.env.YANDEX_REDIRECT_URI || "http://localhost:3000/api/yandex/callback"
  
  // Разные варианты scope для тестирования
  const scopes = [
    "login:info login:email login:avatar",
    "login:info login:email", 
    "login:info",
    "mail:smtp mail:imap_full",
    "login:info login:email mail:smtp mail:imap_full"
  ]
  
  const urls = scopes.map((scope, index) => {
    const params = new URLSearchParams({
      response_type: "code",
      client_id: clientId || "",
      redirect_uri: redirectUri,
      scope: scope,
      state: `test_${index}`
    })
    
    return {
      index: index + 1,
      scope: scope,
      url: `https://oauth.yandex.ru/authorize?${params.toString()}`
    }
  })
  
  return NextResponse.json({
    current_config: {
      client_id: clientId,
      redirect_uri: redirectUri
    },
    test_urls: urls
  })
}
