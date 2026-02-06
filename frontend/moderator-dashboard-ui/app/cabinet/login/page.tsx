"use client"

import { useEffect, useMemo } from "react"
import { useRouter } from "next/navigation"

export default function CabinetLoginPage() {
  const router = useRouter()

  const redirectPath = useMemo(() => {
    if (typeof window === "undefined") return "/cabinet"
    const urlParams = new URLSearchParams(window.location.search)
    return urlParams.get("redirect") || "/cabinet"
  }, [])

  useEffect(() => {
    const urlParams = new URLSearchParams(window.location.search)
    const redirect = urlParams.get("redirect") || "/cabinet"
    router.replace(`/login?redirect=${encodeURIComponent(redirect)}`)
    return
  }, [redirectPath, router])

  return null
}
