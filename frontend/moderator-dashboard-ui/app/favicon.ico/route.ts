export function GET() {
  // Return empty favicon with 200 OK instead of 204
  const emptyIcon = Buffer.from("")
  return new Response(emptyIcon, {
    status: 200,
    headers: {
      "Content-Type": "image/x-icon",
      "Cache-Control": "public, max-age=3600",
    },
  })
}
