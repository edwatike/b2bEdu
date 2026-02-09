"use client"

import { useState, useEffect } from "react"
import { motion } from "framer-motion"
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card"
import { Button } from "@/components/ui/button"
import { Input } from "@/components/ui/input"
import { Textarea } from "@/components/ui/textarea"
import { Label } from "@/components/ui/label"
import { Table, TableBody, TableCell, TableHead, TableHeader, TableRow } from "@/components/ui/table"
import { Navigation } from "@/components/navigation"
import { AuthGuard } from "@/components/auth-guard"
import { getBlacklist, addToBlacklist, removeFromBlacklist } from "@/lib/api"
import { getCachedBlacklist, setCachedBlacklist, invalidateBlacklistCache } from "@/lib/cache"
import { toast } from "sonner"
import { Plus, Trash2, Ban, Shield, AlertTriangle } from "lucide-react"
import type { BlacklistEntryDTO } from "@/lib/types"

function BlacklistPage() {
  const [entries, setEntries] = useState<BlacklistEntryDTO[]>([])
  const [loading, setLoading] = useState(true)
  const [newDomain, setNewDomain] = useState("")
  const [newReason, setNewReason] = useState("")
  const [addingDomain, setAddingDomain] = useState(false)

  useEffect(() => {
    loadBlacklist()
  }, [])

  async function loadBlacklist() {
    setLoading(true)
    try {
      // Проверяем кэш
      const cached = getCachedBlacklist()
      if (cached) {
        setEntries(cached)
        setLoading(false)
        // Загружаем в фоне для обновления кэша
        getBlacklist({ limit: 1000 })
          .then((data) => {
            setCachedBlacklist(data.entries)
            setEntries(data.entries)
          })
          .catch(() => {
            // Игнорируем ошибки фоновой загрузки
          })
      } else {
        const data = await getBlacklist({ limit: 1000 })
        setEntries(data.entries)
        setCachedBlacklist(data.entries)
      }
    } catch (error) {
      toast.error("Ошибка загрузки данных")
      console.error("Error loading blacklist:", error)
    } finally {
      setLoading(false)
    }
  }

  async function handleAdd() {
    if (!newDomain.trim()) {
      toast.error("Введите домен")
      return
    }

    setAddingDomain(true)
    try {
      await addToBlacklist({ 
        domain: newDomain.trim(),
        reason: newReason.trim() || null
      })
      invalidateBlacklistCache()
      toast.success(`Домен "${newDomain}" добавлен в blacklist`)
      setNewDomain("")
      setNewReason("")
      loadBlacklist()
    } catch (error) {
      toast.error("Ошибка добавления домена")
      console.error("Error adding to blacklist:", error)
    } finally {
      setAddingDomain(false)
    }
  }

  async function handleRemove(domain: string) {
    if (!confirm(`Удалить "${domain}" из blacklist?`)) return

    try {
      await removeFromBlacklist(domain)
      invalidateBlacklistCache()
      toast.success(`Домен "${domain}" удален из blacklist`)
      loadBlacklist()
    } catch (error) {
      toast.error("Ошибка удаления домена")
      console.error("Error removing from blacklist:", error)
    }
  }

  return (
    <div className="min-h-screen bg-gradient-to-br from-slate-50 to-red-50/30">
      <Navigation />
      <motion.main 
        initial={{ opacity: 0, y: 20 }}
        animate={{ opacity: 1, y: 0 }}
        transition={{ duration: 0.5 }}
        className="container mx-auto px-6 py-6 max-w-7xl"
      >
        <motion.div 
          initial={{ opacity: 0, y: -20 }}
          animate={{ opacity: 1, y: 0 }}
          transition={{ duration: 0.6 }}
          className="flex items-center gap-3 mb-6"
        >
          <div className="h-10 w-10 rounded-lg bg-gradient-to-br from-red-600 to-orange-600 flex items-center justify-center">
            <Shield className="h-5 w-5 text-white" />
          </div>
          <div>
            <h1 className="text-4xl font-bold text-gradient">Черный список доменов</h1>
            <p className="text-muted-foreground mt-1">Управление заблокированными доменами</p>
          </div>
        </motion.div>

        <motion.div
          initial={{ opacity: 0, y: 20 }}
          animate={{ opacity: 1, y: 0 }}
          transition={{ duration: 0.7, delay: 0.1 }}
          className="mb-6"
        >
          <Card className="card-hover bg-gradient-to-br from-white to-red-50 border-red-200 shadow-lg">
            <CardHeader>
              <CardTitle className="flex items-center gap-2 text-xl">
                <Plus className="h-5 w-5 text-red-600" />
                Добавить домен в черный список
              </CardTitle>
            </CardHeader>
            <CardContent>
              <div className="space-y-4">
                <div>
                  <Label htmlFor="domain-input" className="text-sm font-medium text-gray-700">Домен</Label>
                  <Input
                    id="domain-input"
                    name="domain"
                    autoComplete="off"
                    placeholder="example.com"
                    value={newDomain}
                    onChange={(e) => setNewDomain(e.target.value)}
                    onKeyDown={(e) => e.key === "Enter" && !e.shiftKey && handleAdd()}
                    className="mt-1 border-gray-300 focus:border-red-500 focus:ring-red-500"
                  />
                </div>
                <div>
                  <Label htmlFor="reason-input" className="text-sm font-medium text-gray-700">Причина добавления</Label>
                  <Textarea
                    id="reason-input"
                    name="reason"
                    autoComplete="off"
                    placeholder="Укажите причину добавления домена в черный список..."
                    value={newReason}
                    onChange={(e) => setNewReason(e.target.value)}
                    rows={3}
                    className="mt-1 border-gray-300 focus:border-red-500 focus:ring-red-500"
                  />
                </div>
                <motion.div whileHover={{ scale: 1.05 }} whileTap={{ scale: 0.95 }}>
                  <Button onClick={handleAdd} disabled={addingDomain} className="bg-gradient-to-r from-red-600 to-orange-600 hover:from-red-700 hover:to-orange-700 text-white">
                    <Plus className="mr-2 h-4 w-4" />
                    Добавить в blacklist
                  </Button>
                </motion.div>
              </div>
            </CardContent>
          </Card>
        </motion.div>

        {loading ? (
          <motion.div
            initial={{ opacity: 0, scale: 0.95 }}
            animate={{ opacity: 1, scale: 1 }}
            transition={{ duration: 0.5 }}
            className="text-center py-12"
          >
            <div className="h-16 w-16 rounded-full bg-red-100 flex items-center justify-center mx-auto mb-4">
              <AlertTriangle className="h-8 w-8 text-red-500 animate-pulse" />
            </div>
            <p className="text-lg text-muted-foreground">Загрузка...</p>
          </motion.div>
        ) : entries.length === 0 ? (
          <motion.div
            initial={{ opacity: 0, scale: 0.95 }}
            animate={{ opacity: 1, scale: 1 }}
            transition={{ duration: 0.5 }}
          >
            <Card className="bg-gradient-to-br from-gray-50 to-red-50 border-gray-200">
              <CardContent className="py-12 text-center text-muted-foreground">
                <div className="h-16 w-16 rounded-full bg-gray-200 flex items-center justify-center mx-auto mb-4">
                  <Ban className="h-8 w-8 text-gray-400" />
                </div>
                <p className="text-lg font-medium">Список пуст</p>
                <p className="text-sm mt-1">Добавьте домены в черный список для их блокировки</p>
              </CardContent>
            </Card>
          </motion.div>
        ) : (
          <motion.div
            initial={{ opacity: 0, y: 20 }}
            animate={{ opacity: 1, y: 0 }}
            transition={{ duration: 0.8, delay: 0.2 }}
          >
            <Card className="card-hover bg-gradient-to-br from-white to-red-50 border-red-200 shadow-lg">
              <CardContent className="p-6">
                <Table>
                  <TableHeader>
                    <TableRow className="border-red-100">
                      <TableHead className="text-red-700 font-semibold">Домен</TableHead>
                      <TableHead className="text-red-700 font-semibold">Причина</TableHead>
                      <TableHead className="text-red-700 font-semibold">Добавлен</TableHead>
                      <TableHead className="text-right text-red-700 font-semibold">Действия</TableHead>
                    </TableRow>
                  </TableHeader>
                  <TableBody>
                    {entries.map((entry, index) => (
                      <motion.tr
                        key={entry.domain}
                        initial={{ opacity: 0, x: -20 }}
                        animate={{ opacity: 1, x: 0 }}
                        transition={{ duration: 0.3, delay: index * 0.05 }}
                        className="table-row-hover border-red-50"
                      >
                        <TableCell className="font-mono font-medium text-red-700">{entry.domain}</TableCell>
                        <TableCell className="text-gray-600">{entry.reason || "—"}</TableCell>
                        <TableCell className="text-gray-600 text-sm">
                          {entry.addedAt ? new Date(entry.addedAt).toLocaleString("ru-RU") : "—"}
                        </TableCell>
                        <TableCell className="text-right">
                          <motion.div whileHover={{ scale: 1.1 }} whileTap={{ scale: 0.9 }}>
                            <Button 
                              variant="ghost" 
                              size="sm" 
                              onClick={() => handleRemove(entry.domain)}
                              className="text-red-600 hover:text-red-700 hover:bg-red-50"
                            >
                              <Trash2 className="h-4 w-4" />
                            </Button>
                          </motion.div>
                        </TableCell>
                      </motion.tr>
                    ))}
                  </TableBody>
                </Table>
              </CardContent>
            </Card>
          </motion.div>
        )}
      </motion.main>
    </div>
  )
}

export default function BlacklistPageWithAuth() {
  return (
    <AuthGuard allowedRoles={["moderator"]}>
      <BlacklistPage />
    </AuthGuard>
  )
}
