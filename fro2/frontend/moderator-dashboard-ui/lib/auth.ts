import { SignJWT, jwtVerify, JWTPayload } from "jose"
import { cookies } from "next/headers"
import { NextRequest, NextResponse } from "next/server"

const JWT_SECRET = new TextEncoder().encode(
  process.env.JWT_SECRET || "your-super-secret-jwt-key-change-in-production"
)

export interface UserPayload {
  id: string
  username: string
  role: "admin" | "moderator" | "user"
}

// Расширение JWTPayload для нашего типа
interface CustomJWTPayload extends JWTPayload {
  id: string
  username: string
  role: "admin" | "moderator" | "user"
}

// Проверка JWT токена (только верификация, создание теперь на backend)
export async function verifyToken(token: string): Promise<UserPayload | null> {
  try {
    const { payload } = await jwtVerify(token, JWT_SECRET) as { payload: CustomJWTPayload }
    return {
      id: payload.id,
      username: payload.username,
      role: payload.role
    }
  } catch (error) {
    return null
  }
}

// Удаление токена из cookie
export function deleteAuthCookie(response: NextResponse): void {
  response.cookies.set("auth_token", "", {
    httpOnly: true,
    secure: process.env.NODE_ENV === "production",
    sameSite: "lax",
    maxAge: 0,
    path: "/",
  })
}

// Получение токена из cookie
export async function getAuthToken(): Promise<string | null> {
  const cookieStore = await cookies()
  return cookieStore.get("auth_token")?.value || null
}

// Проверка авторизации на сервере
export async function getServerSession(): Promise<UserPayload | null> {
  const token = await getAuthToken()
  if (!token) return null
  
  return await verifyToken(token)
}

// Проверка авторизации в middleware
export async function verifyAuth(request: NextRequest): Promise<UserPayload | null> {
  const token = request.cookies.get("auth_token")?.value
  if (!token) return null
  
  return await verifyToken(token)
}
