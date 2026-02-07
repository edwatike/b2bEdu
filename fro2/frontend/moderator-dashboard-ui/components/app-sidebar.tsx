"use client"

import Link from "next/link"
import { usePathname } from "next/navigation"
import { cn } from "@/lib/utils"
import {
  Package,
  Search,
  Ban,
  History,
  Play,
  Home,
} from "lucide-react"

const navigation = [
  { name: "Главная", href: "/", icon: Home },
  { name: "Поставщики", href: "/suppliers", icon: Package },
  { name: "Ключевые слова", href: "/keywords", icon: Search },
  { name: "Черный список", href: "/blacklist", icon: Ban },
  { name: "Запуски", href: "/parsing-runs", icon: History },
  { name: "Ручной парсинг", href: "/manual-parsing", icon: Play },
]

export function AppSidebar() {
  const pathname = usePathname()

  return (
    <div className="w-64 border-r bg-background">
      <div className="flex h-full flex-col">
        <div className="flex h-16 items-center border-b px-6">
          <h1 className="text-lg font-semibold">B2B Platform</h1>
        </div>
        <nav className="flex-1 space-y-1 px-3 py-4">
          {navigation.map((item) => {
            const isActive = pathname === item.href
            return (
              <Link
                key={item.name}
                href={item.href}
                className={cn(
                  "flex items-center gap-3 rounded-lg px-3 py-2 text-sm font-medium transition-colors",
                  isActive
                    ? "bg-primary text-primary-foreground"
                    : "text-muted-foreground hover:bg-accent hover:text-accent-foreground"
                )}
              >
                <item.icon className="h-5 w-5" />
                {item.name}
              </Link>
            )
          })}
        </nav>
      </div>
    </div>
  )
}
