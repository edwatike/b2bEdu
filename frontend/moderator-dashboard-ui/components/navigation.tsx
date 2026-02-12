"use client"

import Link from "next/link"
import { usePathname, useRouter } from "next/navigation"
import { useEffect, useState } from "react"
import { motion } from "framer-motion"
import { cn } from "@/lib/utils"
import { LayoutDashboard, Play, Users, Ban, Key, Settings, Menu, LogOut, User, ListChecks, Sun, Moon } from "lucide-react"
import { AnimatedLogo } from "./animated-logo"
import { toast } from "sonner"
import { Button } from "@/components/ui/button"
import { useTheme } from "next-themes"

const navItems = [
  { href: "/moderator", label: "Дашборд", icon: LayoutDashboard, color: "from-blue-600 to-purple-600" },
  { href: "/moderator/tasks", label: "Задачи", icon: ListChecks, color: "from-orange-600 to-amber-600" },
  { href: "/parsing-runs", label: "Запуски", icon: Play, color: "from-purple-600 to-indigo-600" },
  { href: "/moderator/suppliers", label: "Поставщики", icon: Users, color: "from-green-600 to-emerald-600" },
  { href: "/moderator/users", label: "Пользователи", icon: Users, color: "from-teal-600 to-cyan-600" },
  { href: "/keywords", label: "Ключи", icon: Key, color: "from-blue-600 to-cyan-600" },
  { href: "/blacklist", label: "Черный список", icon: Ban, color: "from-red-600 to-orange-600" },
  { href: "/settings", label: "Настройки", icon: Settings, color: "from-slate-600 to-slate-800" },
]

export function Navigation() {
  const pathname = usePathname()
  const router = useRouter()
  const [role, setRole] = useState<string | null>(null)
  const [canAccessModerator, setCanAccessModerator] = useState(false)
  const { theme, setTheme } = useTheme()
  const [themeMounted, setThemeMounted] = useState(false)

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
        } else {
          setRole(null)
          setCanAccessModerator(false)
        }
      } catch {
        if (!mounted) return
        setRole(null)
        setCanAccessModerator(false)
      }
    }
    void load()
    return () => {
      mounted = false
    }
  }, [])

  useEffect(() => {
    setThemeMounted(true)
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
            <Link href="/" className="flex items-center gap-3">
              <AnimatedLogo />
              <motion.span
                className="text-xl font-semibold text-gradient -ml-1"
                whileHover={{ scale: 1.1 }}
                transition={{ duration: 0.2 }}
              >
                Модератор
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

          {/* Temporary toggle to user cabinet */}
          <motion.div className="hidden md:flex items-center gap-2">
            <motion.div whileHover={{ scale: 1.05 }} whileTap={{ scale: 0.95 }}>
              <Button
                type="button"
                variant="ghost"
                size="icon"
                aria-label="Переключить тему"
                title="Переключить тему"
                onClick={() => {
                  const next = (theme === "dark") ? "light" : "dark"
                  setTheme(next)
                }}
                disabled={!themeMounted}
              >
                {themeMounted && theme === "dark" ? <Sun className="h-4 w-4" /> : <Moon className="h-4 w-4" />}
              </Button>
            </motion.div>
            <motion.div whileHover={{ scale: 1.05 }} whileTap={{ scale: 0.95 }}>
              {canAccessModerator ? (
                <Link
                  href="/cabinet"
                  title="Кабинет"
                  className="flex items-center gap-2 px-3 py-2 rounded-lg text-sm font-medium bg-gradient-to-r from-teal-600 to-cyan-600 text-white shadow-lg hover:shadow-xl transition-all duration-200"
                >
                  <motion.div whileHover={{ rotate: 360 }} transition={{ duration: 0.5 }}>
                    <User className="h-4 w-4" />
                  </motion.div>
                  <span className="hidden sm:inline">Кабинет</span>
                </Link>
              ) : null}
            </motion.div>
          </motion.div>

          {/* Logout button */}
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

          {/* Mobile menu button */}
          <div className="md:hidden">
            <motion.button
              whileHover={{ scale: 1.1 }}
              whileTap={{ scale: 0.9 }}
              aria-label="Меню"
              className="p-2 rounded-lg hover:bg-accent/50"
            >
              <Menu className="h-5 w-5" />
            </motion.button>
          </div>
        </div>
      </div>
    </motion.nav>
  )
}
