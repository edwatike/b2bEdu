"use client"

import Link from "next/link"
import { usePathname, useRouter } from "next/navigation"
import { useEffect, useState } from "react"
import { motion } from "framer-motion"
import { cn } from "@/lib/utils"
import { LayoutDashboard, FilePlus2, FileText, Settings, LogOut, Shield } from "lucide-react"
import { AnimatedLogo } from "./animated-logo"
import { toast } from "sonner"

const navItems = [
  { href: "/cabinet/overview", label: "Обзор", icon: LayoutDashboard, color: "from-blue-600 to-purple-600" },
  { href: "/cabinet/requests/all", label: "Заявки", icon: FilePlus2, color: "from-indigo-600 to-sky-600" },
  { href: "/cabinet/requests/drafts", label: "Черновики", icon: FileText, color: "from-amber-600 to-orange-600" },
  { href: "/cabinet/settings", label: "Настройки", icon: Settings, color: "from-slate-600 to-slate-800" },
]

export function UserNavigation() {
  const pathname = usePathname()
  const router = useRouter()
  const [role, setRole] = useState<string | null>(null)
  const [canAccessModerator, setCanAccessModerator] = useState(false)
  const [displayName, setDisplayName] = useState<string | null>(null)

  useEffect(() => {
    let mounted = true
    const load = async () => {
      try {
        const resp = await fetch("/api/auth/status")
        const data = await resp.json().catch(() => ({ authenticated: false }))
        if (!mounted) return
        if (resp.ok && data?.authenticated) {
          setRole(typeof data?.user?.role === "string" ? data.user.role : null)
          setCanAccessModerator(Boolean(data?.user?.can_access_moderator))
          const name =
            typeof data?.user?.display_name === "string"
              ? data.user.display_name
              : typeof data?.user?.username === "string"
                ? data.user.username
                : null
          setDisplayName(name)
        } else {
          setRole(null)
          setCanAccessModerator(false)
          setDisplayName(null)
        }
      } catch {
        if (!mounted) return
        setRole(null)
        setCanAccessModerator(false)
        setDisplayName(null)
      }
    }
    void load()
    return () => {
      mounted = false
    }
  }, [])

  async function handleLogout() {
    try {
      const response = await fetch("/api/auth/logout", {
        method: "POST",
      })

      if (response.ok) {
        toast.success("Выход выполнен успешно")
        router.push("/")
      } else {
        toast.error("Ошибка при выходе")
      }
    } catch (error) {
      toast.error("Ошибка соединения")
    }
  }

  return (
    <motion.nav
      initial={{ y: -100, opacity: 0 }}
      animate={{ y: 0, opacity: 1 }}
      transition={{ duration: 0.5, ease: "easeOut" }}
      className="border-b border-border bg-background/95 backdrop-blur supports-[backdrop-filter]:bg-background/60 sticky top-0 z-50 shadow-sm"
    >
      <div className="container mx-auto px-6">
        <div className="flex h-16 items-center justify-between">
          <motion.div whileHover={{ scale: 1.05 }} whileTap={{ scale: 0.95 }} className="flex items-center gap-3">
            <Link href="/cabinet" className="flex items-center gap-3">
              <AnimatedLogo />
              <motion.span
                className="text-xl font-semibold text-gradient"
                whileHover={{ scale: 1.1 }}
                transition={{ duration: 0.2 }}
              >
                Кабинет
              </motion.span>
            </Link>
          </motion.div>

          <div className="hidden md:flex items-center gap-1">
            {navItems.map((item, index) => {
              const Icon = item.icon
              const isActive = pathname === item.href

              return (
                <motion.div
                  key={item.href}
                  initial={{ opacity: 0, y: -20 }}
                  animate={{ opacity: 1, y: 0 }}
                  transition={{ duration: 0.3, delay: index * 0.1 }}
                >
                  <Link
                    href={item.href}
                    className={cn(
                      "flex items-center gap-2 px-4 py-2 rounded-lg text-sm font-medium transition-all duration-200",
                      isActive
                        ? "bg-gradient-to-r " + item.color + " text-white shadow-lg"
                        : "text-muted-foreground hover:text-foreground hover:bg-accent/50 hover:scale-105",
                    )}
                  >
                    <motion.div whileHover={{ rotate: 360 }} transition={{ duration: 0.5 }}>
                      <Icon className="h-4 w-4" />
                    </motion.div>
                    {item.label}
                  </Link>
                </motion.div>
              )
            })}
          </div>

          <motion.div className="hidden md:flex items-center gap-2">
            <motion.div whileHover={{ scale: 1.05 }} whileTap={{ scale: 0.95 }}>
              <button
                type="button"
                onClick={() => {
                  if (canAccessModerator) {
                    router.push("/moderator")
                    return
                  }
                  toast.error("Нет доступа к модераторской зоне")
                }}
                className={cn(
                  "flex items-center gap-2 px-3 py-2 rounded-lg text-sm font-medium shadow-lg transition-all duration-200",
                  canAccessModerator
                    ? "bg-gradient-to-r from-purple-600 to-indigo-600 text-white hover:shadow-xl"
                    : "bg-slate-800/40 text-slate-400 border border-slate-700/60 cursor-not-allowed",
                )}
                title={canAccessModerator ? "Перейти в модераторскую зону" : "Нет прав (can_access_moderator=false)"}
                disabled={!canAccessModerator}
              >
                <motion.div whileHover={{ rotate: 360 }} transition={{ duration: 0.5 }}>
                  <Shield className="h-4 w-4" />
                </motion.div>
                <span className="hidden sm:inline">Модератор</span>
              </button>
            </motion.div>

            {displayName && (
              <div className="hidden lg:flex items-center px-3 py-2 rounded-lg text-sm font-medium text-slate-200 bg-slate-900/40 border border-slate-700/60">
                {displayName}
              </div>
            )}
          </motion.div>

          <motion.button
            onClick={handleLogout}
            whileHover={{ scale: 1.05 }}
            whileTap={{ scale: 0.95 }}
            className="flex items-center gap-2 px-4 py-2 rounded-lg text-sm font-medium text-red-600 hover:text-red-700 hover:bg-red-50 transition-all duration-200"
          >
            <motion.div whileHover={{ rotate: 360 }} transition={{ duration: 0.5 }}>
              <LogOut className="h-4 w-4" />
            </motion.div>
            <span className="hidden sm:inline">Выход</span>
          </motion.button>
        </div>
      </div>
    </motion.nav>
  )
}
