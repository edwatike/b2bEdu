import { NextResponse } from "next/server"
import { cookies } from "next/headers"

export async function GET() {
  const cookieStore = await cookies()
  
  const yandexState = cookieStore.get("yandex_oauth_state")?.value
  const yandexStates = cookieStore.get("yandex_oauth_states")?.value
  const yandexAccess = cookieStore.get("yandex_oauth_access")?.value
  const yandexEmail = cookieStore.get("yandex_oauth_email")?.value
  
  let decodedStates = null
  let parsedStates = null
  
  if (yandexStates) {
    try {
      decodedStates = decodeURIComponent(yandexStates)
      parsedStates = JSON.parse(decodedStates)
    } catch (e) {
      decodedStates = `Error: ${e}`
      parsedStates = `Error: ${e}`
    }
  }
  
  return NextResponse.json({
    cookies: {
      yandex_oauth_state: yandexState,
      yandex_oauth_states: yandexStates,
      yandex_oauth_access: yandexAccess,
      yandex_oauth_email: yandexEmail
    },
    decoded: {
      yandex_oauth_states: decodedStates
    },
    parsed: {
      yandex_oauth_states: parsedStates
    }
  })
}
