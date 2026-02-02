"use client"

import { useEffect, useMemo, useState } from "react"
import { motion } from "framer-motion"
import { Navigation } from "@/components/navigation"
import { AuthGuard } from "@/components/auth-guard"
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card"
import { Button } from "@/components/ui/button"
import { Input } from "@/components/ui/input"
import { Badge } from "@/components/ui/badge"
import { Switch } from "@/components/ui/switch"
import { toast } from "sonner"

type UserAccessDTO = {
  id: number
  username: string
  email?: string | null
  role: string
  is_active: boolean
  cabinet_access_enabled: boolean
}

function UsersPage() {
  const [users, setUsers] = useState<UserAccessDTO[]>([])
  const [loading, setLoading] = useState(true)
  const [search, setSearch] = useState("")
  const [savingId, setSavingId] = useState<number | null>(null)

  const loadUsers = async () => {
    setLoading(true)
    try {
      const resp = await fetch("/api/proxy/moderator/users", { cache: "no-store" })
      const data = (await resp.json().catch(() => null)) as any
      if (!resp.ok) {
        throw new Error(data?.error || data?.detail || `HTTP ${resp.status}`)
      }
      setUsers(Array.isArray(data) ? (data as UserAccessDTO[]) : [])
    } catch (e) {
      const msg = e instanceof Error ? e.message : "Не удалось загрузить пользователей"
      toast.error(msg)
    } finally {
      setLoading(false)
    }
  }

  useEffect(() => {
    void loadUsers()
  }, [])

  const filtered = useMemo(() => {
    const q = search.trim().toLowerCase()
    if (!q) return users
    return users.filter((u) =>
      String(u.username || "").toLowerCase().includes(q) || String(u.email || "").toLowerCase().includes(q),
    )
  }, [users, search])

  const toggleCabinetAccess = async (userId: number, enabled: boolean) => {
    if (savingId) return
    setSavingId(userId)
    try {
      const resp = await fetch(`/api/proxy/moderator/users/${encodeURIComponent(String(userId))}/cabinet-access`, {
        method: "PATCH",
        headers: {
          "Content-Type": "application/json",
        },
        body: JSON.stringify({ cabinet_access_enabled: enabled }),
      })
      const data = (await resp.json().catch(() => null)) as any
      if (!resp.ok) {
        throw new Error(data?.error || data?.detail || `HTTP ${resp.status}`)
      }
      setUsers((prev) => prev.map((u) => (u.id === userId ? { ...u, cabinet_access_enabled: enabled } : u)))
      toast.success(enabled ? "Доступ в ЛК включен" : "Доступ в ЛК отключен")
    } catch (e) {
      const msg = e instanceof Error ? e.message : "Не удалось обновить доступ"
      toast.error(msg)
      await loadUsers()
    } finally {
      setSavingId(null)
    }
  }

  return (
    <div className="min-h-screen bg-gradient-to-br from-slate-950 via-slate-900 to-slate-950 text-white">
      <Navigation />
      <motion.main
        initial={{ opacity: 0, y: 30 }}
        animate={{ opacity: 1, y: 0 }}
        transition={{ duration: 0.6, ease: "easeOut" }}
        className="container mx-auto px-6 py-10"
      >
        <div className="flex flex-col gap-2 mb-8">
          <h1 className="text-3xl font-semibold">Пользователи</h1>
          <p className="text-slate-300">Управление доступом в личный кабинет пользователей (cabinet_access_enabled).</p>
        </div>

        <Card className="bg-slate-900/60 border-slate-700">
          <CardHeader className="flex flex-col gap-3 md:flex-row md:items-center md:justify-between">
            <CardTitle className="text-white">Список пользователей</CardTitle>
            <div className="flex items-center gap-2">
              <Input
                value={search}
                onChange={(e) => setSearch(e.target.value)}
                placeholder="Поиск по username/email..."
                className="w-72 bg-slate-900 border-slate-700 text-white"
              />
              <Button variant="outline" onClick={loadUsers} disabled={loading}>
                Обновить
              </Button>
            </div>
          </CardHeader>
          <CardContent className="space-y-3">
            {loading ? (
              <div className="rounded-lg border border-slate-700/60 bg-slate-900/40 p-6 text-slate-300">Загрузка...</div>
            ) : filtered.length === 0 ? (
              <div className="rounded-lg border border-slate-700/60 bg-slate-900/40 p-6 text-slate-300">Нет данных</div>
            ) : (
              <div className="space-y-2">
                {filtered.map((u) => (
                  <div
                    key={u.id}
                    className="flex flex-col gap-3 rounded-lg border border-slate-700/60 bg-slate-900/40 p-4 md:flex-row md:items-center md:justify-between"
                  >
                    <div className="min-w-0">
                      <div className="flex items-center gap-2 min-w-0">
                        <p className="text-sm font-semibold text-white truncate">{u.username}</p>
                        <Badge className="bg-slate-500/20 text-slate-200 border-slate-500/30">{u.role}</Badge>
                        {!u.is_active && (
                          <Badge className="bg-rose-500/20 text-rose-200 border-rose-500/30">inactive</Badge>
                        )}
                      </div>
                      <p className="text-xs text-slate-400 truncate">{u.email || "—"}</p>
                    </div>

                    <div className="flex items-center gap-3">
                      <div className="flex items-center gap-2">
                        <span className="text-xs text-slate-300">Доступ в ЛК</span>
                        <Switch
                          checked={Boolean(u.cabinet_access_enabled)}
                          onCheckedChange={(val) => void toggleCabinetAccess(u.id, Boolean(val))}
                          disabled={savingId === u.id}
                        />
                      </div>
                    </div>
                  </div>
                ))}
              </div>
            )}
          </CardContent>
        </Card>
      </motion.main>
    </div>
  )
}

export default function UsersPageWithAuth() {
  return (
    <AuthGuard allowedRoles={["moderator", "admin"]}>
      <UsersPage />
    </AuthGuard>
  )
}
