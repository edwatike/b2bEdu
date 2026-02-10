import { NextRequest, NextResponse } from 'next/server'

export async function GET(request: NextRequest) {
  return NextResponse.json({ error: 'GitHub OAuth disabled' }, { status: 404 })
}
