"use client"

import { useEffect } from "react"
import { useRouter } from "next/navigation"

export default function RootLoginPage() {
  const router = useRouter()

  useEffect(() => {
    let mounted = true
    const check = async () => {
      try {
        const resp = await fetch("/api/auth/status")
        const data = await resp.json().catch(() => ({ authenticated: false }))
        if (!mounted) return
        if (resp.ok && data?.authenticated) {
          const canAccessModerator = Boolean(data?.user?.can_access_moderator)
          router.push(canAccessModerator ? "/moderator" : "/cabinet")
          return
        }
        router.replace("/login")
      } catch {
        if (!mounted) return
        router.replace("/login")
      }
    }
    void check()
    return () => {
      mounted = false
    }
  }, [router])

  return null
}
