"use client"

import { useEffect, useState } from "react"
import { useRouter } from "next/navigation"
import { motion } from "framer-motion"
import { Loader2 } from "lucide-react"

interface AuthGuardProps {
  children: React.ReactNode
  allowedRoles?: Array<"admin" | "moderator" | "user">
}

const AUTH_GUARD_BYPASS = String(process.env.NEXT_PUBLIC_AUTH_BYPASS || "").toLowerCase() === "1" ||
  String(process.env.NEXT_PUBLIC_AUTH_BYPASS || "").toLowerCase() === "true"

export function AuthGuard({ children, allowedRoles }: AuthGuardProps) {
  const router = useRouter()
  const [isLoading, setIsLoading] = useState(true)
  const [isAuthenticated, setIsAuthenticated] = useState(false)

  useEffect(() => {
    if (AUTH_GUARD_BYPASS) {
      setIsAuthenticated(true)
      setIsLoading(false)
      return
    }
    checkAuth()
  }, [])

  async function checkAuth() {
    try {
      const response = await fetch("/api/auth/status")
      const data = await response.json().catch(() => ({ authenticated: false }))
      if (response.ok && data.authenticated) {
        const role = (data?.user?.role as "admin" | "moderator" | "user" | undefined) || "user"
        const canAccessModerator = Boolean(data?.user?.can_access_moderator)

        // Extra permission gate for moderator-only routes.
        const isModeratorOnly = Boolean(allowedRoles && allowedRoles.length === 1 && allowedRoles[0] === "moderator")
        if (isModeratorOnly && !canAccessModerator) {
          const target = "/cabinet"
          if (window.location.pathname !== target) {
            router.push(target)
          }
          return
        }

        // Treat 'admin' as a superset role (can access both user and moderator areas).
        const isRoleAllowed =
          !allowedRoles || allowedRoles.length === 0 || role === "admin" || allowedRoles.includes(role)

        if (!isRoleAllowed) {
          const target = canAccessModerator ? "/moderator" : "/cabinet"
          // Avoid infinite loop if already on target
          if (window.location.pathname !== target) {
            router.push(target)
          }
          return
        }
        setIsAuthenticated(true)
      } else {
        // Сохраняем текущий путь для редиректа после логина
        const currentPath = window.location.pathname + window.location.search
        router.push(`/login?redirect=${encodeURIComponent(currentPath)}`)
      }
    } catch (error) {
      console.error("Auth check failed:", error)
      router.push("/login")
    } finally {
      setIsLoading(false)
    }
  }

  if (isLoading) {
    return (
      <div className="min-h-screen flex items-center justify-center bg-gradient-to-br from-slate-900 via-slate-800 to-slate-900">
        <motion.div
          initial={{ opacity: 0, scale: 0.8 }}
          animate={{ opacity: 1, scale: 1 }}
          transition={{ duration: 0.5 }}
          className="text-center"
        >
          <Loader2 className="h-12 w-12 animate-spin text-blue-500 mb-4" />
          <p className="text-white text-lg">Проверка авторизации...</p>
        </motion.div>
      </div>
    )
  }

  if (!isAuthenticated) {
    return (
      <div className="min-h-screen flex items-center justify-center bg-gradient-to-br from-slate-900 via-slate-800 to-slate-900">
        <motion.div
          initial={{ opacity: 0, scale: 0.8 }}
          animate={{ opacity: 1, scale: 1 }}
          transition={{ duration: 0.5 }}
          className="text-center"
        >
          <Loader2 className="h-12 w-12 animate-spin text-blue-500 mb-4" />
          <p className="text-white text-lg">Перенаправление на вход...</p>
        </motion.div>
      </div>
    )
  }

  return <>{children}</>
}
