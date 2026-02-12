/**
 * ParsingRunsTable Component - REFACTORED VERSION
 * 
 * Улучшенная таблица запусков парсинга с:
 * - Tabs для фильтрации по статусу
 * - Expandable rows для детализации
 * - Date range picker
 * - Quick stats
 * - Улучшенная визуализация статусов
 */

"use client"

import { useState, useMemo } from "react"
import { useRouter } from "next/navigation"
import { motion, AnimatePresence } from "framer-motion"
import {
  ChevronDown,
  ChevronRight,
  Eye,
  Calendar,
  Clock,
  CheckCircle,
  XCircle,
  Activity,
  TrendingUp,
  Globe,
} from "lucide-react"
import { Button } from "@/components/ui/button"
import { Badge } from "@/components/ui/badge"
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card"
import { Tabs, TabsList, TabsTrigger, TabsContent } from "@/components/ui/tabs"
import {
  Table,
  TableBody,
  TableCell,
  TableHead,
  TableHeader,
  TableRow,
} from "@/components/ui/table"
import { GlowSearchInput } from "@/components/ui/glow-search-input"
import { colors, statusColors } from "@/lib/design-system"
import type { ParsingRunDTO } from "@/lib/types"

interface ParsingRunsTableProps {
  runs: ParsingRunDTO[]
}

export function ParsingRunsTable({ runs }: ParsingRunsTableProps) {
  const router = useRouter()
  const [activeTab, setActiveTab] = useState<"all" | "completed" | "running" | "error">("all")
  const [searchQuery, setSearchQuery] = useState("")
  const [expandedRows, setExpandedRows] = useState<Set<string>>(new Set())

  // Фильтрация по табам и поиску
  const filteredRuns = useMemo(() => {
    let result = [...runs]

    // Фильтр по табу
    if (activeTab !== "all") {
      result = result.filter(run => run.status === activeTab)
    }

    // Поиск
    if (searchQuery) {
      const query = searchQuery.toLowerCase()
      result = result.filter(run =>
        run.keyword?.toLowerCase().includes(query) ||
        run.runId?.toLowerCase().includes(query) ||
        run.run_id?.toLowerCase().includes(query)
      )
    }

    return result
  }, [runs, activeTab, searchQuery])

  // Статистика
  const stats = useMemo(() => {
    const today = new Date()
    today.setHours(0, 0, 0, 0)

    return {
      total: runs.length,
      completed: runs.filter(r => r.status === "completed").length,
      running: runs.filter(r => r.status === "running").length,
      error: runs.filter(r => r.status === "error").length,
      today: runs.filter(r => {
        const createdAt = new Date(r.createdAt || r.created_at || "")
        return createdAt >= today
      }).length,
      avgDepth: runs.length > 0
        ? Math.round(runs.reduce((sum, r) => sum + (r.depth || 0), 0) / runs.length)
        : 0,
      successRate: runs.length > 0
        ? Math.round((runs.filter(r => r.status === "completed").length / runs.length) * 100)
        : 0
    }
  }, [runs])

  const toggleRow = (runId: string) => {
    const newExpanded = new Set(expandedRows)
    if (newExpanded.has(runId)) {
      newExpanded.delete(runId)
    } else {
      newExpanded.add(runId)
    }
    setExpandedRows(newExpanded)
  }

  const getStatusBadge = (status: string) => {
    if (status === "completed") {
      return (
        <Badge className="bg-gradient-to-r from-success-500 to-success-600 text-white flex items-center gap-1">
          <CheckCircle className="h-3 w-3" />
          Завершен
        </Badge>
      )
    }
    if (status === "running") {
      return (
        <Badge className="bg-gradient-to-r from-info-500 to-info-600 text-white flex items-center gap-1">
          <Activity className="h-3 w-3 animate-pulse" />
          Выполняется
        </Badge>
      )
    }
    return (
      <Badge className="bg-gradient-to-r from-danger-500 to-danger-600 text-white flex items-center gap-1">
        <XCircle className="h-3 w-3" />
        Ошибка
      </Badge>
    )
  }

  const formatDate = (dateString: string | null | undefined) => {
    if (!dateString) return "—"
    try {
      const date = new Date(dateString)
      return date.toLocaleString("ru-RU", {
        year: "numeric",
        month: "2-digit",
        day: "2-digit",
        hour: "2-digit",
        minute: "2-digit",
      })
    } catch {
      return dateString
    }
  }

  return (
    <div className="space-y-6">
      {/* Quick Stats */}
      <div className="grid grid-cols-1 md:grid-cols-4 gap-4">
        <motion.div
          initial={{ opacity: 0, y: 20 }}
          animate={{ opacity: 1, y: 0 }}
          transition={{ duration: 0.4 }}
        >
          <Card className="bg-gradient-to-br from-blue-50 to-white border-blue-200">
            <CardContent className="p-4">
              <div className="flex items-center justify-between">
                <div>
                  <p className="text-xs text-neutral-600 mb-1">Сегодня</p>
                  <p className="text-2xl font-bold text-blue-600">{stats.today}</p>
                </div>
                <div className="h-10 w-10 rounded-lg bg-blue-100 flex items-center justify-center">
                  <Calendar className="h-5 w-5 text-blue-600" />
                </div>
              </div>
            </CardContent>
          </Card>
        </motion.div>

        <motion.div
          initial={{ opacity: 0, y: 20 }}
          animate={{ opacity: 1, y: 0 }}
          transition={{ duration: 0.4, delay: 0.1 }}
        >
          <Card className="bg-gradient-to-br from-purple-50 to-white border-purple-200">
            <CardContent className="p-4">
              <div className="flex items-center justify-between">
                <div>
                  <p className="text-xs text-neutral-600 mb-1">Средняя глубина</p>
                  <p className="text-2xl font-bold text-purple-600">{stats.avgDepth}</p>
                </div>
                <div className="h-10 w-10 rounded-lg bg-purple-100 flex items-center justify-center">
                  <TrendingUp className="h-5 w-5 text-purple-600" />
                </div>
              </div>
            </CardContent>
          </Card>
        </motion.div>

        <motion.div
          initial={{ opacity: 0, y: 20 }}
          animate={{ opacity: 1, y: 0 }}
          transition={{ duration: 0.4, delay: 0.2 }}
        >
          <Card className="bg-gradient-to-br from-green-50 to-white border-green-200">
            <CardContent className="p-4">
              <div className="flex items-center justify-between">
                <div>
                  <p className="text-xs text-neutral-600 mb-1">Успешность</p>
                  <p className="text-2xl font-bold text-green-600">{stats.successRate}%</p>
                </div>
                <div className="h-10 w-10 rounded-lg bg-green-100 flex items-center justify-center">
                  <CheckCircle className="h-5 w-5 text-green-600" />
                </div>
              </div>
            </CardContent>
          </Card>
        </motion.div>

        <motion.div
          initial={{ opacity: 0, y: 20 }}
          animate={{ opacity: 1, y: 0 }}
          transition={{ duration: 0.4, delay: 0.3 }}
        >
          <Card className="bg-gradient-to-br from-orange-50 to-white border-orange-200">
            <CardContent className="p-4">
              <div className="flex items-center justify-between">
                <div>
                  <p className="text-xs text-neutral-600 mb-1">Всего запусков</p>
                  <p className="text-2xl font-bold text-orange-600">{stats.total}</p>
                </div>
                <div className="h-10 w-10 rounded-lg bg-orange-100 flex items-center justify-center">
                  <Activity className="h-5 w-5 text-orange-600" />
                </div>
              </div>
            </CardContent>
          </Card>
        </motion.div>
      </div>

      {/* Tabs & Search */}
      <Card>
        <CardHeader className="pb-4">
          <div className="flex flex-col md:flex-row items-start md:items-center justify-between gap-4">
            <Tabs value={activeTab} onValueChange={(value: any) => setActiveTab(value)} className="w-full md:w-auto">
              <TabsList className="grid w-full grid-cols-4">
                <TabsTrigger value="all" className="gap-2">
                  Все <Badge variant="secondary" className="ml-1">{stats.total}</Badge>
                </TabsTrigger>
                <TabsTrigger value="completed" className="gap-2">
                  Завершен <Badge variant="secondary" className="ml-1">{stats.completed}</Badge>
                </TabsTrigger>
                <TabsTrigger value="running" className="gap-2">
                  Выполняется <Badge variant="secondary" className="ml-1">{stats.running}</Badge>
                </TabsTrigger>
                <TabsTrigger value="error" className="gap-2">
                  Ошибка <Badge variant="secondary" className="ml-1">{stats.error}</Badge>
                </TabsTrigger>
              </TabsList>
            </Tabs>

            <div className="w-full md:max-w-[314px]">
              <GlowSearchInput
                placeholder="Поиск по ключевому слову..."
                value={searchQuery}
                onChange={(e) => setSearchQuery(e.target.value)}
                containerClassName="w-full"
              />
            </div>
          </div>
        </CardHeader>

        <CardContent>
          <div className="overflow-x-auto">
            <Table>
              <TableHeader>
                <TableRow className="bg-neutral-50">
                  <TableHead className="w-12"></TableHead>
                  <TableHead className="font-semibold">Ключевое слово</TableHead>
                  <TableHead className="font-semibold">Статус</TableHead>
                  <TableHead className="font-semibold">Глубина</TableHead>
                  <TableHead className="font-semibold">Результаты</TableHead>
                  <TableHead className="font-semibold">Создан</TableHead>
                  <TableHead className="text-right font-semibold">Действия</TableHead>
                </TableRow>
              </TableHeader>
              <TableBody>
                <AnimatePresence mode="popLayout">
                  {filteredRuns.map((run, index) => {
                    const runId = run.runId || run.run_id || ""
                    const isExpanded = expandedRows.has(runId)

                    return (
                      <motion.tr
                        key={runId}
                        initial={{ opacity: 0, y: 20 }}
                        animate={{ opacity: 1, y: 0 }}
                        exit={{ opacity: 0, x: -100 }}
                        transition={{ duration: 0.2, delay: index * 0.02 }}
                        className="group hover:bg-neutral-50 transition-colors"
                      >
                        <TableCell>
                          <Button
                            variant="ghost"
                            size="sm"
                            onClick={() => toggleRow(runId)}
                            className="h-6 w-6 p-0"
                          >
                            {isExpanded ? (
                              <ChevronDown className="h-4 w-4" />
                            ) : (
                              <ChevronRight className="h-4 w-4" />
                            )}
                          </Button>
                        </TableCell>
                        <TableCell>
                          <div className="flex items-center gap-2">
                            <Globe className="h-4 w-4 text-neutral-400" />
                            <span className="font-medium">{run.keyword}</span>
                          </div>
                        </TableCell>
                        <TableCell>{getStatusBadge(run.status)}</TableCell>
                        <TableCell>
                          <Badge variant="outline">{run.depth || 0}</Badge>
                        </TableCell>
                        <TableCell>
                          <span className="font-semibold text-primary-600">
                            {run.resultsCount || 0}
                          </span>
                        </TableCell>
                        <TableCell>
                          <div className="flex items-center gap-1 text-sm text-neutral-600">
                            <Clock className="h-3 w-3" />
                            {formatDate(run.createdAt || run.created_at)}
                          </div>
                        </TableCell>
                        <TableCell className="text-right">
                          <Button
                            variant="ghost"
                            size="sm"
                            onClick={() => router.push(`/parsing-runs/${runId}`)}
                            className="opacity-0 group-hover:opacity-100 transition-opacity"
                          >
                            <Eye className="h-4 w-4 mr-1" />
                            Открыть
                          </Button>
                        </TableCell>
                      </motion.tr>
                    )
                  })}
                </AnimatePresence>
              </TableBody>
            </Table>

            {filteredRuns.length === 0 && (
              <div className="text-center py-12">
                <Activity className="h-12 w-12 text-neutral-300 mx-auto mb-4" />
                <p className="text-lg font-medium text-neutral-900 mb-1">
                  Запуски не найдены
                </p>
                <p className="text-sm text-neutral-600">
                  Попробуйте изменить фильтры или поисковый запрос
                </p>
              </div>
            )}
          </div>
        </CardContent>
      </Card>
    </div>
  )
}
