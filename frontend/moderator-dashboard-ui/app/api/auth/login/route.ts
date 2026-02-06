import { NextRequest, NextResponse } from "next/server"

export async function POST(request: NextRequest) {
  return NextResponse.json(
    { error: "Only Yandex OAuth is supported" },
    { status: 404 }
  )
}
