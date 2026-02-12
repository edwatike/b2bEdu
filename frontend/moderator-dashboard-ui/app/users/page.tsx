"use client"

import { useEffect, useMemo, useState } from "react"
import { motion } from "framer-motion"
import { Navigation } from "@/components/navigation"
import { AuthGuard } from "@/components/auth-guard"
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card"
import { Button } from "@/components/ui/button"
import { Checkbox } from "@/components/ui/checkbox"
import { Input } from "@/components/ui/input"
import { GlowSearchInput } from "@/components/ui/glow-search-input"
import { Dialog, DialogContent, DialogHeader, DialogTitle } from "@/components/ui/dialog"
import { Label } from "@/components/ui/label"
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
  organization_name?: string | null
}

function UsersPage() {
  const [users, setUsers] = useState<UserAccessDTO[]>([])
  const [loading, setLoading] = useState(true)
  const [search, setSearch] = useState("")
  const [savingId, setSavingId] = useState<number | null>(null)
  const [selectedIds, setSelectedIds] = useState<Set<number>>(new Set())
  const [showCreate, setShowCreate] = useState(false)
  const [createEmail, setCreateEmail] = useState("")
  const [createOrg, setCreateOrg] = useState("")
  const [creating, setCreating] = useState(false)

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

  const toggleSelect = (userId: number) => {
    setSelectedIds((prev) => {
      const next = new Set(prev)
      if (next.has(userId)) {
        next.delete(userId)
      } else {
        next.add(userId)
      }
      return next
    })
  }

  const toggleSelectAll = () => {
    if (selectedIds.size === filtered.length) {
      setSelectedIds(new Set())
    } else {
      setSelectedIds(new Set(filtered.map((u) => u.id)))
    }
  }

  const handleDeleteSelected = async () => {
    if (selectedIds.size === 0) return
    if (!confirm(`Удалить ${selectedIds.size} пользователей?`)) return
    try {
      for (const id of Array.from(selectedIds)) {
        const resp = await fetch(`/api/proxy/moderator/users/${encodeURIComponent(String(id))}`, {
          method: "DELETE",
        })
        if (!resp.ok && resp.status !== 204) {
          const data = (await resp.json().catch(() => null)) as any
          throw new Error(data?.detail || data?.error || `HTTP ${resp.status}`)
        }
      }
      toast.success("Пользователи удалены")
      setSelectedIds(new Set())
      await loadUsers()
    } catch (e) {
      const msg = e instanceof Error ? e.message : "Не удалось удалить пользователей"
      toast.error(msg)
    }
  }

  const handleCreateUser = async () => {
    if (creating) return
    const email = createEmail.trim()
    if (!email) {
      toast.error("Введите email")
      return
    }
    setCreating(true)
    try {
      const resp = await fetch("/api/proxy/moderator/users", {
        method: "POST",
        headers: {
          "Content-Type": "application/json",
        },
        body: JSON.stringify({ email, organization_name: createOrg.trim() || null }),
      })
      const data = (await resp.json().catch(() => null)) as any
      if (!resp.ok) {
        throw new Error(data?.detail || data?.error || `HTTP ${resp.status}`)
      }
      toast.success("Пользователь создан")
      setShowCreate(false)
      setCreateEmail("")
      setCreateOrg("")
      await loadUsers()
    } catch (e) {
      const msg = e instanceof Error ? e.message : "Не удалось создать пользователя"
      toast.error(msg)
    } finally {
      setCreating(false)
    }
  }

  const allSelected = filtered.length > 0 && selectedIds.size === filtered.length

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
              <GlowSearchInput
                value={search}
                onChange={(e) => setSearch(e.target.value)}
                placeholder="Поиск по username/email..."
                containerClassName="w-[314px]"
                className="bg-slate-900 text-white"
              />
              <Button variant="outline" onClick={loadUsers} disabled={loading}>
                Обновить
              </Button>
              <Button onClick={() => setShowCreate(true)}>Создать пользователя</Button>
            </div>
          </CardHeader>
          <CardContent className="space-y-3">
            {selectedIds.size > 0 && (
              <div className="flex items-center justify-between rounded-lg border border-slate-700/60 bg-slate-900/40 p-3">
                <div className="text-sm text-slate-200">Выбрано: {selectedIds.size}</div>
                <Button variant="destructive" onClick={handleDeleteSelected}>
                  Удалить выбранных
                </Button>
              </div>
            )}

            {loading ? (
              <div className="rounded-lg border border-slate-700/60 bg-slate-900/40 p-6 text-slate-300">Загрузка...</div>
            ) : filtered.length === 0 ? (
              <div className="rounded-lg border border-slate-700/60 bg-slate-900/40 p-6 text-slate-300">Нет данных</div>
            ) : (
              <div className="space-y-2">
                <div className="flex items-center gap-3 text-xs text-slate-400">
                  <Checkbox checked={allSelected} onCheckedChange={toggleSelectAll} />
                  <span>Выбрать все</span>
                </div>
                {filtered.map((u) => (
                  <div
                    key={u.id}
                    className="flex flex-col gap-3 rounded-lg border border-slate-700/60 bg-slate-900/40 p-4 md:flex-row md:items-center md:justify-between"
                  >
                    <div className="flex items-center gap-3 min-w-0">
                      <Checkbox checked={selectedIds.has(u.id)} onCheckedChange={() => toggleSelect(u.id)} />
                      <div className="min-w-0">
                        <div className="flex items-center gap-2 min-w-0">
                          <p className="text-sm font-semibold text-white truncate">{u.username}</p>
                          <Badge className="bg-slate-500/20 text-slate-200 border-slate-500/30">{u.role}</Badge>
                          {!u.is_active && (
                            <Badge className="bg-rose-500/20 text-rose-200 border-rose-500/30">inactive</Badge>
                          )}
                        </div>
                        <p className="text-xs text-slate-400 truncate">{u.email || "—"}</p>
                        {u.organization_name && (
                          <p className="text-xs text-slate-500 truncate">{u.organization_name}</p>
                        )}
                      </div>
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

      {showCreate && (
        <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/50">
          <div className="w-full max-w-md rounded-lg bg-slate-900 border border-slate-700 p-6">
            <h2 className="text-lg font-semibold text-white mb-4">Создать пользователя</h2>
            <div className="space-y-3">
              <Input
                value={createEmail}
                onChange={(e) => setCreateEmail(e.target.value)}
                placeholder="Email (для входа через Яндекс)"
                className="bg-slate-900 border-slate-700 text-white"
              />
              <Input
                value={createOrg}
                onChange={(e) => setCreateOrg(e.target.value)}
                placeholder="Название организации"
                className="bg-slate-900 border-slate-700 text-white"
              />
            </div>
            <div className="mt-6 flex items-center justify-end gap-2">
              <Button variant="outline" onClick={() => setShowCreate(false)} disabled={creating}>
                Отмена
              </Button>
              <Button onClick={handleCreateUser} disabled={creating}>
                Создать
              </Button>
            </div>
          </div>
        </div>
      )}
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
