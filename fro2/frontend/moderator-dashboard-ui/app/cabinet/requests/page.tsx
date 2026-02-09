"use client"

import { useEffect } from "react"
import { useRouter } from "next/navigation"

export default function CabinetRequestsRedirectPage() {
  const router = useRouter()

  useEffect(() => {
    router.replace("/cabinet/requests/all")
  }, [router])

  return null
}
