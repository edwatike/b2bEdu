import type { Metadata } from "next"
import "./globals.css"
import { Toaster } from "sonner"
import { WebVitalsMonitor } from "../components/web-vitals-monitor"
import { QueryProvider } from "../components/query-provider"

export const metadata: Metadata = {
  title: "B2B Platform - Moderator Dashboard",
  description: "B2B Platform supplier moderation and parsing system",
  generator: "v0.app",
  robots: {
    index: false,
    follow: false,
  },
  icons: {
    icon: "/icon-light-32x32.png",
    apple: "/apple-icon.png",
  },
}

export default function RootLayout({
  children,
}: {
  children: React.ReactNode
}) {
  return (
    <html lang="ru" suppressHydrationWarning>
      <body>
        <QueryProvider>
          {children}
          <Toaster position="top-right" />
          <WebVitalsMonitor />
        </QueryProvider>
      </body>
    </html>
  )
}
