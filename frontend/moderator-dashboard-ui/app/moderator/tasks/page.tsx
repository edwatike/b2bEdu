"use client"

import { useEffect, useState, useMemo } from "react"
import { motion } from "framer-motion"
import { AuthGuard } from "@/components/auth-guard"
import { Navigation } from "@/components/navigation"
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card"
import { Badge } from "@/components/ui/badge"
import { Button } from "@/components/ui/button"
import { GlowSearchInput } from "@/components/ui/glow-search-input"
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from "@/components/ui/select"
import { Progress } from "@/components/ui/progress"
import { RefreshCw, Clock, CheckCircle, XCircle, PlayCircle, AlertCircle, Filter } from "lucide-react"
import { getModeratorTasks } from "@/lib/api"
import type { ModeratorTaskDTO } from "@/lib/api"

function normalizeStatus(status: string): "new" | "running" | "completed" | "failed" | "unknown" {
  const s = (status || "").toLowerCase()
  if (s === "new") return "new"
  if (s === "running" || s === "processing") return "running"
  if (s === "done" || s === "completed") return "completed"
  if (s === "failed" || s === "error") return "failed"
  return "unknown"
}

function statusLabelRu(status: string): string {
  switch (normalizeStatus(status)) {
    case "new":
      return "Новая"
    case "running":
      return "В работе"
    case "completed":
      return "Завершено"
    case "failed":
      return "Ошибка"
    default:
      return status || "—"
  }
}

function normalizeSourceLabel(source: string): string {
  const s = (source || "").trim().toLowerCase()
  if (s === "google") return "Google"
  if (s === "yandex") return "Яндекс"
  if (s === "both") return "Google + Яндекс"
  return source || "—"
}

function statusBadgeClass(status: string) {
  const s = (status || "").toLowerCase()
  if (s === "done" || s === "completed") return "bg-emerald-100 text-emerald-800 border-emerald-200 hover:bg-emerald-200 transition-colors"
  if (s === "running" || s === "processing") return "bg-blue-100 text-blue-800 border-blue-200 hover:bg-blue-200 transition-colors"
  if (s === "failed" || s === "error") return "bg-red-100 text-red-800 border-red-200 hover:bg-red-200 transition-colors"
  return "bg-amber-100 text-amber-800 border-amber-200 hover:bg-amber-200 transition-colors"
}

function statusIcon(status: string) {
  const s = (status || "").toLowerCase()
  if (s === "done" || s === "completed") return <CheckCircle className="w-3 h-3" />
  if (s === "running" || s === "processing") return <PlayCircle className="w-3 h-3" />
  if (s === "failed" || s === "error") return <XCircle className="w-3 h-3" />
  return <Clock className="w-3 h-3" />
}

function getStatusPriority(status: string): number {
  const s = (status || "").toLowerCase()
  if (s === "failed" || s === "error") return 1
  if (s === "new") return 2
  if (s === "running" || s === "processing") return 3
  if (s === "done" || s === "completed") return 4
  return 5
}

function ModeratorTasksPage() {
  const [tasks, setTasks] = useState<ModeratorTaskDTO[]>([])
  const [isLoading, setIsLoading] = useState(true)
  const [hasError, setHasError] = useState(false)
  const [searchQuery, setSearchQuery] = useState("")
  const [statusFilter, setStatusFilter] = useState<string>("all")
  const [sortBy, setSortBy] = useState<string>("date-desc")
  const [expandedTaskIds, setExpandedTaskIds] = useState<Record<number, boolean>>({})

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

  // Автообновление каждые 30 секунд
  useEffect(() => {
    let cancelled = false
    let timeoutId: ReturnType<typeof setTimeout> | null = null

    const tick = () => {
      if (cancelled) return
      if (!isLoading) void load()
      timeoutId = setTimeout(tick, 30000)
    }

    timeoutId = setTimeout(tick, 30000)

    return () => {
      cancelled = true
      if (timeoutId) clearTimeout(timeoutId)
    }
  }, [isLoading])

  // Фильтрация и сортировка
  const filteredAndSortedTasks = useMemo(() => {
    let filtered = tasks

    // Поиск
    if (searchQuery.trim()) {
      const query = searchQuery.toLowerCase()
      filtered = filtered.filter(task => 
        task.title?.toLowerCase().includes(query) ||
        task.id.toString().includes(query) ||
        task.request_id.toString().includes(query) ||
        task.parsing_runs?.some(run => 
          run.keyword?.toLowerCase().includes(query)
        )
      )
    }

    // Фильтр по статусу
    if (statusFilter !== "all") {
      filtered = filtered.filter(task => 
        normalizeStatus(task.status || "new") === normalizeStatus(statusFilter)
      )
    }

    // Сортировка
    const sorted = [...filtered].sort((a, b) => {
      switch (sortBy) {
        case "date-desc":
          return new Date(b.created_at || 0).getTime() - new Date(a.created_at || 0).getTime()
        case "date-asc":
          return new Date(a.created_at || 0).getTime() - new Date(b.created_at || 0).getTime()
        case "status-priority":
          return getStatusPriority(a.status || "new") - getStatusPriority(b.status || "new")
        case "id-desc":
          return b.id - a.id
        default:
          return 0
      }
    })

    return sorted
  }, [tasks, searchQuery, statusFilter, sortBy])

  // Статистика
  const stats = useMemo(() => {
    const total = tasks.length
    const completed = tasks.filter(t => normalizeStatus(t.status) === "completed").length
    const running = tasks.filter(t => normalizeStatus(t.status) === "running").length
    const failed = tasks.filter(t => normalizeStatus(t.status) === "failed").length
    const newTasks = tasks.filter(t => normalizeStatus(t.status) === "new").length
    
    return { total, completed, running, failed, newTasks }
  }, [tasks])

  return (
    <div className="min-h-screen bg-gradient-to-br from-slate-50 to-blue-50/30">
      <Navigation />
      <motion.main
        initial={{ opacity: 0, y: 20 }}
        animate={{ opacity: 1, y: 0 }}
        transition={{ duration: 0.5 }}
        className="container mx-auto px-6 py-8 max-w-7xl"
      >
        {/* Заголовок и статистика */}
        <div className="mb-8">
          <div className="flex items-start justify-between gap-4 mb-6">
            <div>
              <h1 className="text-4xl font-bold text-gray-900 mb-2">Задачи</h1>
              <p className="text-gray-600">Все задачи модерации с запусками парсинга по ключевым словам.</p>
            </div>
            <Button 
              onClick={() => void load()} 
              disabled={isLoading}
              className="gap-2 hover:bg-blue-600 transition-colors"
            >
              <RefreshCw className={`w-4 h-4 ${isLoading ? 'animate-spin' : ''}`} />
              Обновить
            </Button>
          </div>

          {/* Статистика */}
          <div className="grid grid-cols-2 md:grid-cols-5 gap-4 mb-6">
            <Card className="bg-white/80 backdrop-blur-sm border-gray-200">
              <CardContent className="p-4">
                <div className="text-2xl font-bold text-gray-900">{stats.total}</div>
                <div className="text-sm text-gray-600">Всего задач</div>
              </CardContent>
            </Card>
            <Card className="bg-amber-50/80 backdrop-blur-sm border-amber-200">
              <CardContent className="p-4">
                <div className="text-2xl font-bold text-amber-700">{stats.newTasks}</div>
                <div className="text-sm text-amber-600">Новые</div>
              </CardContent>
            </Card>
            <Card className="bg-blue-50/80 backdrop-blur-sm border-blue-200">
              <CardContent className="p-4">
                <div className="text-2xl font-bold text-blue-700">{stats.running}</div>
                <div className="text-sm text-blue-600">В работе</div>
              </CardContent>
            </Card>
            <Card className="bg-emerald-50/80 backdrop-blur-sm border-emerald-200">
              <CardContent className="p-4">
                <div className="text-2xl font-bold text-emerald-700">{stats.completed}</div>
                <div className="text-sm text-emerald-600">Завершено</div>
              </CardContent>
            </Card>
            <Card className="bg-red-50/80 backdrop-blur-sm border-red-200">
              <CardContent className="p-4">
                <div className="text-2xl font-bold text-red-700">{stats.failed}</div>
                <div className="text-sm text-red-600">Ошибки</div>
              </CardContent>
            </Card>
          </div>

          {/* Фильтры и поиск */}
          <div className="flex flex-col md:flex-row gap-4 mb-6">
            <div className="flex-1 max-w-md">
              <GlowSearchInput
                placeholder="Поиск по названию, ID, ключевым словам..."
                value={searchQuery}
                onChange={(e) => setSearchQuery(e.target.value)}
                containerClassName="w-full"
              />
            </div>
            <Select value={statusFilter} onValueChange={setStatusFilter}>
              <SelectTrigger className="w-full md:w-48 bg-white/80 backdrop-blur-sm border-gray-200">
                <Filter className="w-4 h-4 mr-2" />
                <SelectValue placeholder="Статус" />
              </SelectTrigger>
              <SelectContent>
                <SelectItem value="all">Все статусы</SelectItem>
                <SelectItem value="new">Новые</SelectItem>
                <SelectItem value="running">В работе</SelectItem>
                <SelectItem value="completed">Завершено</SelectItem>
                <SelectItem value="failed">С ошибкой</SelectItem>
              </SelectContent>
            </Select>
            <Select value={sortBy} onValueChange={setSortBy}>
              <SelectTrigger className="w-full md:w-48 bg-white/80 backdrop-blur-sm border-gray-200">
                <SelectValue placeholder="Сортировка" />
              </SelectTrigger>
              <SelectContent>
                <SelectItem value="date-desc">Сначала новые</SelectItem>
                <SelectItem value="date-asc">Сначала старые</SelectItem>
                <SelectItem value="status-priority">По приоритету</SelectItem>
                <SelectItem value="id-desc">По ID (убыв.)</SelectItem>
              </SelectContent>
            </Select>
          </div>
        </div>

        {/* Список задач */}
        <div className="space-y-6">
          {hasError && (
            <Card className="border-red-200 bg-red-50">
              <CardContent className="p-6">
                <div className="flex items-center gap-3 text-red-800">
                  <AlertCircle className="w-5 h-5" />
                  <span>Не удалось загрузить задачи. Попробуйте обновить страницу.</span>
                </div>
              </CardContent>
            </Card>
          )}
          
          {isLoading && (
            <div className="flex justify-center py-12">
              <div className="flex items-center gap-3 text-gray-600">
                <RefreshCw className="w-5 h-5 animate-spin" />
                <span>Загрузка задач...</span>
              </div>
            </div>
          )}
          
          {!isLoading && !hasError && filteredAndSortedTasks.length === 0 && (
            <Card className="border-gray-200 bg-gray-50">
              <CardContent className="p-12 text-center">
                <div className="text-gray-600">
                  {searchQuery || statusFilter !== "all" ? "Задачи не найдены по выбранным критериям." : "Пока нет задач."}
                </div>
              </CardContent>
            </Card>
          )}

          {!isLoading && !hasError && filteredAndSortedTasks.map((t, index) => (
            <motion.div
              key={t.id}
              initial={{ opacity: 0, y: 20 }}
              animate={{ opacity: 1, y: 0 }}
              transition={{ duration: 0.3, delay: index * 0.05 }}
            >
              <Card className="bg-white/90 backdrop-blur-sm border-gray-200 hover:shadow-lg transition-all duration-300 hover:border-blue-300">
                <CardContent className="p-6">
                  {/* Заголовок задачи */}
                  <div className="flex items-start justify-between gap-4 mb-4">
                    <div className="flex-1 min-w-0">
                      <div className="flex items-center gap-3 mb-2">
                        <h3 className="text-lg font-semibold text-gray-900 truncate">
                          {t.title || "Заявка"}
                        </h3>
                        <Badge className={statusBadgeClass(t.status)}>
                          <span className="flex items-center gap-1">
                            {statusIcon(t.status)}
                            <span title={t.status || ""}>{statusLabelRu(t.status || "new")}</span>
                          </span>
                        </Badge>
                      </div>
                      <div className="text-sm text-gray-600">
                        Задача #{t.id} · Заявка #{t.request_id}
                      </div>
                    </div>
                  </div>

                  {/* Метаданные */}
                  <div className="flex flex-wrap items-center gap-4 mb-4 text-sm text-gray-600">
                    <div className="flex items-center gap-1">
                      <span className="font-medium">Источник:</span> {normalizeSourceLabel(t.source)}
                    </div>
                    <div className="flex items-center gap-1">
                      <span className="font-medium">Глубина:</span> {t.depth}
                    </div>
                    <div className="flex items-center gap-1">
                      <Clock className="w-4 h-4" />
                      {t.created_at ? new Date(t.created_at).toLocaleString("ru-RU", {
                        day: 'numeric',
                        month: 'short',
                        hour: '2-digit',
                        minute: '2-digit'
                      }) : "—"}
                    </div>
                  </div>

                  {/* Прогресс запусков */}
                  {t.parsing_runs && t.parsing_runs.length > 0 && (
                    <div className="mb-4">
                      {(() => {
                        const completedCount = t.parsing_runs.filter(r => normalizeStatus(r.status || "") === "completed").length
                        const totalCount = t.parsing_runs.length
                        const percent = totalCount > 0 ? (completedCount / totalCount) * 100 : 0
                        return (
                          <>
                      <div className="flex items-center justify-between mb-2">
                        <span className="text-sm font-medium text-gray-700">
                          Прогресс запусков ({completedCount}/{totalCount})
                        </span>
                        <span className="text-xs text-gray-500">
                          {Math.round(percent)}%
                        </span>
                      </div>
                      <Progress 
                        value={percent}
                        className="h-2"
                      />
                          </>
                        )
                      })()}
                    </div>
                  )}

                  {/* Запуски парсинга */}
                  <div className="bg-gray-50 rounded-lg p-4">
                    <div className="flex items-center justify-between mb-3">
                      <div className="text-sm font-medium text-gray-700">
                        Запуски парсинга {t.parsing_runs && `(${t.parsing_runs.length})`}
                      </div>
                      {t.parsing_runs && t.parsing_runs.length > 3 && (
                        <Button
                          variant="ghost"
                          size="sm"
                          className="text-xs"
                          onClick={() =>
                            setExpandedTaskIds(prev => ({ ...prev, [t.id]: !prev[t.id] }))
                          }
                        >
                          {expandedTaskIds[t.id] ? "Свернуть" : "Показать все"}
                        </Button>
                      )}
                    </div>
                    {(!t.parsing_runs || t.parsing_runs.length === 0) && (
                      <div className="text-sm text-gray-500 italic">Пока нет запусков.</div>
                    )}
                    {t.parsing_runs && t.parsing_runs.length > 0 && (
                      <div className="space-y-2">
                        {(expandedTaskIds[t.id] ? t.parsing_runs : t.parsing_runs.slice(0, 3)).map((r) => (
                          <div key={r.run_id} className="flex items-center justify-between gap-3 p-2 bg-white rounded-md border border-gray-200 hover:border-blue-200 transition-colors">
                            <a
                              className="text-sm text-blue-700 hover:text-blue-900 hover:underline truncate flex-1"
                              href={`/parsing-runs/${encodeURIComponent(String(r.run_id))}`}
                              target="_blank"
                              rel="noreferrer"
                            >
                              {(r.keyword && String(r.keyword).trim()) ? String(r.keyword) : r.run_id}
                            </a>
                            <div className="flex items-center gap-2">
                              <Badge className={statusBadgeClass(r.status)} variant="outline">
                                <span className="flex items-center gap-1">
                                  {statusIcon(r.status)}
                                  <span title={r.status || ""}>{statusLabelRu(r.status || "")}</span>
                                </span>
                              </Badge>
                              <div className="text-xs text-gray-500">
                                {r.created_at ? new Date(r.created_at).toLocaleString("ru-RU", {
                                  hour: '2-digit',
                                  minute: '2-digit'
                                }) : ""}
                              </div>
                            </div>
                          </div>
                        ))}
                        {!expandedTaskIds[t.id] && t.parsing_runs.length > 3 && (
                          <div className="text-center text-sm text-gray-500 pt-1">
                            ... и еще {t.parsing_runs.length - 3} запусков
                          </div>
                        )}
                      </div>
                    )}
                  </div>
                </CardContent>
              </Card>
            </motion.div>
          ))}
        </div>
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
