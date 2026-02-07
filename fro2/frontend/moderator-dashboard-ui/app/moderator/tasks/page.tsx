"use client"

import { useEffect, useState } from "react"
import { motion } from "framer-motion"
import { AuthGuard } from "@/components/auth-guard"
import { Navigation } from "@/components/navigation"
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card"
import { Badge } from "@/components/ui/badge"
import { Button } from "@/components/ui/button"
import { getModeratorTasks } from "@/lib/api"
import type { ModeratorTaskDTO } from "@/lib/api"

function statusBadgeClass(status: string) {
  const s = (status || "").toLowerCase()
  if (s === "done" || s === "completed") return "bg-emerald-500/20 text-emerald-200 border-emerald-500/30"
  if (s === "running" || s === "processing") return "bg-blue-500/20 text-blue-200 border-blue-500/30"
  return "bg-amber-500/20 text-amber-200 border-amber-500/30"
}

function ModeratorTasksPage() {
  const [tasks, setTasks] = useState<ModeratorTaskDTO[]>([])
  const [isLoading, setIsLoading] = useState(true)
  const [hasError, setHasError] = useState(false)

  const load = async () => {
    try {
      setIsLoading(true)
      setHasError(false)
      const list = await getModeratorTasks({ limit: 200, offset: 0 })
      setTasks(Array.isArray(list) ? list : [])
    } catch {
      setHasError(true)
    } finally {
      setIsLoading(false)
    }
  }

  useEffect(() => {
    void load()
  }, [])

  return (
    <div className="min-h-screen bg-gradient-to-br from-slate-50 to-blue-50/30">
      <Navigation />
      <motion.main
        initial={{ opacity: 0, y: 20 }}
        animate={{ opacity: 1, y: 0 }}
        transition={{ duration: 0.5 }}
        className="container mx-auto px-6 py-12 max-w-7xl"
      >
        <div className="flex items-start justify-between gap-4 mb-6">
          <div>
            <h1 className="text-3xl font-bold">Задачи</h1>
            <p className="text-sm text-muted-foreground">Заявки, отправленные в работу: задача + все запуски парсинга по ключам.</p>
          </div>
          <Button variant="outline" onClick={() => void load()} disabled={isLoading}>
            Обновить
          </Button>
        </div>

        <Card>
          <CardHeader>
            <CardTitle className="text-sm font-medium text-muted-foreground uppercase tracking-wide">Список задач</CardTitle>
          </CardHeader>
          <CardContent className="space-y-3">
            {hasError && <div className="text-sm text-red-600">Не удалось загрузить задачи.</div>}
            {isLoading && <div className="text-sm text-muted-foreground">Загрузка...</div>}
            {!isLoading && tasks.length === 0 && <div className="text-sm text-muted-foreground">Пока нет задач.</div>}

            {tasks.map((t) => (
              <div key={t.id} className="flex flex-col gap-3 rounded-lg border p-4 bg-white">
                <div className="flex items-start justify-between gap-3">
                  <div className="min-w-0">
                    <div className="font-semibold truncate">{t.title || "Заявка"}</div>
                    <div className="text-xs text-muted-foreground">Задача #{t.id} · request #{t.request_id}</div>
                  </div>
                  <Badge className={statusBadgeClass(t.status)}>{t.status || "new"}</Badge>
                </div>

                <div className="text-sm text-muted-foreground">{t.source} · depth {t.depth}</div>
                <div className="text-xs text-muted-foreground">Создана: {t.created_at ? new Date(t.created_at).toLocaleString("ru-RU") : "—"}</div>

                <div className="rounded-md border bg-slate-50 p-3">
                  <div className="text-xs font-medium text-slate-600 mb-2">Запуски парсинга</div>
                  {(!t.parsing_runs || t.parsing_runs.length === 0) && (
                    <div className="text-xs text-muted-foreground">Пока нет запусков.</div>
                  )}
                  {t.parsing_runs && t.parsing_runs.length > 0 && (
                    <div className="space-y-2">
                      {t.parsing_runs.map((r) => (
                        <div key={r.run_id} className="flex items-center justify-between gap-3">
                          <a
                            className="text-xs text-blue-700 underline truncate"
                            href={`/parsing-runs/${encodeURIComponent(String(r.run_id))}`}
                            target="_blank"
                            rel="noreferrer"
                          >
                            {(r.keyword && String(r.keyword).trim()) ? String(r.keyword) : r.run_id}
                          </a>
                          <div className="flex items-center gap-2">
                            <Badge className={statusBadgeClass(r.status)}>{r.status || "—"}</Badge>
                            <div className="text-[11px] text-muted-foreground">
                              {r.created_at ? new Date(r.created_at).toLocaleString("ru-RU") : ""}
                            </div>
                          </div>
                        </div>
                      ))}
                    </div>
                  )}
                </div>
              </div>
            ))}
          </CardContent>
        </Card>
      </motion.main>
    </div>
  )
}

export default function ModeratorTasksPageWithAuth() {
  return (
    <AuthGuard allowedRoles={["moderator"]}>
      <ModeratorTasksPage />
    </AuthGuard>
  )
}
