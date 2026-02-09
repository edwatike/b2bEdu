"use client"

import { useState, useEffect } from "react"
import { useSearchParams } from "next/navigation"
import { useRouter } from "next/navigation"
import { motion, AnimatePresence } from "framer-motion"
import { Card } from "@/components/ui/card"
import { Button } from "@/components/ui/button"
import { Input } from "@/components/ui/input"
import { Badge } from "@/components/ui/badge"
import { Checkbox } from "@/components/ui/checkbox"
import { Navigation } from "@/components/navigation"
import { AuthGuard } from "@/components/auth-guard"
import {
  DataTable,
  DataTableHeader,
  DataTableRow,
  DataTableCell,
  DataTableEmpty,
  DataTableSkeleton,
} from "@/components/ui/data-table"
import { APIError, getParsingRuns, deleteParsingRun, deleteParsingRunsBulk } from "@/lib/api"
import { toast } from "sonner"
import { Search, Trash2, Clock, CheckCircle, XCircle, Activity, Calendar, ChevronRight, Sparkles } from "lucide-react"
import type { ParsingRunDTO } from "@/lib/types"

function ParsingRunsPage() {
  const router = useRouter()
  const searchParams = useSearchParams()
  const [runs, setRuns] = useState<ParsingRunDTO[]>([])
  const [loading, setLoading] = useState(true)
  const [statusFilter, setStatusFilter] = useState<string>("all")
  const [searchQuery, setSearchQuery] = useState("")
  const [selectedRuns, setSelectedRuns] = useState<Set<string>>(new Set())


  useEffect(() => {
    const status = searchParams.get("status")
    if (status && status !== statusFilter) {
      setStatusFilter(status)
    }
  }, [searchParams])
  useEffect(() => {
    loadRuns()
  }, [statusFilter])

  async function loadRuns() {
    setLoading(true)
    try {
      const params: any = { limit: 100, sort: "created_at", order: "desc" }
      if (statusFilter !== "all") {
        params.status = statusFilter
      }
      if (searchQuery) {
        params.keyword = searchQuery
      }

      const data = await getParsingRuns(params)
      setRuns(data.runs)
    } catch (error) {
      if (error instanceof APIError && error.status === 499) {
        return
      }
      toast.error("Ошибка загрузки данных")
      console.error("Error loading runs:", error)
    } finally {
      setLoading(false)
    }
  }

  async function handleDelete(runId: string) {
    if (!confirm("Удалить этот запуск парсинга?")) return

    try {
      await deleteParsingRun(runId)
      toast.success("Запуск удален")
      setSelectedRuns(new Set())
      loadRuns()
    } catch (error) {
      toast.error("Ошибка удаления")
      console.error("Error deleting run:", error)
    }
  }

  async function handleBulkDelete() {
    if (selectedRuns.size === 0) return
    if (!confirm(`Удалить ${selectedRuns.size} запусков парсинга?`)) return

    try {
      const runIds = Array.from(selectedRuns)
      const result = await deleteParsingRunsBulk(runIds)
      toast.success(`Удалено ${result.deleted} из ${result.total} запусков`)
      setSelectedRuns(new Set())
      loadRuns()
    } catch (error) {
      toast.error("Ошибка массового удаления")
      console.error("Error bulk deleting runs:", error)
    }
  }

  function toggleSelectRun(runId: string) {
    const newSelected = new Set(selectedRuns)
    if (newSelected.has(runId)) {
      newSelected.delete(runId)
    } else {
      newSelected.add(runId)
    }
    setSelectedRuns(newSelected)
  }

  function toggleSelectAll() {
    if (selectedRuns.size === runs.length) {
      setSelectedRuns(new Set())
    } else {
      const allRunIds = runs.map((run) => run.runId || run.run_id || "").filter(Boolean)
      setSelectedRuns(new Set(allRunIds))
    }
  }

  const allSelected = runs.length > 0 && selectedRuns.size === runs.length

  function getStatusBadge(status: string) {
    if (status === "completed")
      return (
        <Badge className="bg-emerald-500/10 text-emerald-600 border-emerald-500/20 hover:bg-emerald-500/20">
          <CheckCircle className="h-3 w-3 mr-1" />
          Завершен
        </Badge>
      )
    if (status === "running")
      return (
        <Badge className="bg-blue-500/10 text-blue-600 border-blue-500/20 hover:bg-blue-500/20">
          <Activity className="h-3 w-3 mr-1 animate-pulse" />
          Выполняется
        </Badge>
      )
    return (
      <Badge className="bg-red-500/10 text-red-600 border-red-500/20 hover:bg-red-500/20">
        <XCircle className="h-3 w-3 mr-1" />
        Ошибка
      </Badge>
    )
  }

  const statusButtons = [
    { value: "all", label: "Все", icon: Sparkles },
    { value: "running", label: "Выполняется", icon: Activity },
    { value: "completed", label: "Завершен", icon: CheckCircle },
    { value: "failed", label: "Ошибка", icon: XCircle },
  ]

  return (
    <div className="min-h-screen bg-gradient-to-br from-slate-50 via-purple-50/30 to-indigo-50/20">
      <Navigation />
      <motion.main
        initial={{ opacity: 0, y: 20 }}
        animate={{ opacity: 1, y: 0 }}
        transition={{ duration: 0.5 }}
        className="container mx-auto px-6 py-8 max-w-7xl"
      >
        {/* Header */}
        <motion.div
          initial={{ opacity: 0, y: -20 }}
          animate={{ opacity: 1, y: 0 }}
          transition={{ duration: 0.6 }}
          className="mb-8"
        >
          <div className="flex items-center gap-4 mb-2">
            <div className="h-12 w-12 rounded-2xl bg-gradient-to-br from-purple-600 to-indigo-600 flex items-center justify-center shadow-lg shadow-purple-500/25">
              <Clock className="h-6 w-6 text-white" />
            </div>
            <div>
              <h1 className="text-3xl font-bold bg-gradient-to-r from-purple-600 to-indigo-600 bg-clip-text text-transparent">
                Запуски
              </h1>
              <p className="text-muted-foreground">История и управление запусками</p>
            </div>
          </div>
        </motion.div>

        {/* Filters */}
        <motion.div
          initial={{ opacity: 0, y: 20 }}
          animate={{ opacity: 1, y: 0 }}
          transition={{ duration: 0.6, delay: 0.1 }}
          className="mb-6"
        >
          <Card className="p-4 bg-white/80 backdrop-blur-sm border-purple-100 shadow-sm">
            <div className="flex flex-col lg:flex-row gap-4">
              {/* Search */}
              <div className="relative flex-1">
                <Search className="absolute left-3 top-1/2 transform -translate-y-1/2 h-4 w-4 text-purple-400" />
                <Input
                  id="parsing-search"
                  name="parsing-search"
                  autoComplete="off"
                  aria-label="Поиск по ключевому слову"
                  placeholder="Поиск по ключевому слову..."
                  value={searchQuery}
                  onChange={(e) => setSearchQuery(e.target.value)}
                  onKeyDown={(e) => e.key === "Enter" && loadRuns()}
                  className="pl-10 border-purple-200 focus:border-purple-400 focus:ring-purple-400/20"
                />
              </div>

              {/* Status filter */}
              <div className="flex gap-2 flex-wrap">
                {statusButtons.map((btn) => {
                  const Icon = btn.icon
                  const isActive = statusFilter === btn.value
                  return (
                    <Button
                      key={btn.value}
                      variant={isActive ? "default" : "outline"}
                      size="sm"
                      onClick={() => setStatusFilter(btn.value)}
                      className={
                        isActive
                          ? "bg-gradient-to-r from-purple-600 to-indigo-600 text-white shadow-md shadow-purple-500/20"
                          : "border-purple-200 text-purple-700 hover:bg-purple-50"
                      }
                    >
                      <Icon className="h-4 w-4 mr-1.5" />
                      {btn.label}
                    </Button>
                  )
                })}
              </div>
            </div>

            {/* Bulk actions */}
            <AnimatePresence>
              {selectedRuns.size > 0 && (
                <motion.div
                  initial={{ opacity: 0, height: 0 }}
                  animate={{ opacity: 1, height: "auto" }}
                  exit={{ opacity: 0, height: 0 }}
                  className="mt-4 pt-4 border-t border-purple-100"
                >
                  <div className="flex items-center justify-between bg-gradient-to-r from-red-50 to-orange-50 p-3 rounded-xl border border-red-200">
                    <span className="text-sm text-red-700 font-medium">Выбрано: {selectedRuns.size}</span>
                    <Button
                      variant="destructive"
                      size="sm"
                      onClick={handleBulkDelete}
                      className="bg-gradient-to-r from-red-600 to-orange-600 hover:from-red-700 hover:to-orange-700"
                    >
                      <Trash2 className="h-4 w-4 mr-2" />
                      Удалить выбранные
                    </Button>
                  </div>
                </motion.div>
              )}
            </AnimatePresence>
          </Card>
        </motion.div>

        {/* Table */}
        <motion.div
          initial={{ opacity: 0, y: 20 }}
          animate={{ opacity: 1, y: 0 }}
          transition={{ duration: 0.7, delay: 0.2 }}
        >
          <DataTable>
            <DataTableHeader className="grid-cols-[40px_1fr_140px_180px_100px_60px]">
              <div className="flex items-center justify-center">
                <Checkbox checked={allSelected} onCheckedChange={toggleSelectAll} />
              </div>
              <div>Ключевое слово</div>
              <div>Статус</div>
              <div className="flex items-center gap-1">
                <Calendar className="h-4 w-4" />
                Дата
              </div>
              <div>Результаты</div>
              <div></div>
            </DataTableHeader>

            {loading ? (
              <DataTableSkeleton rows={5} columns={6} />
            ) : runs.length === 0 ? (
              <DataTableEmpty
                icon={<Search className="h-8 w-8 text-purple-300" />}
                title="Запуски не найдены"
                description="Попробуйте изменить фильтры или поиск"
              />
            ) : (
              <AnimatePresence mode="popLayout">
                {runs.map((run, index) => {
                  const runId = run.runId || run.run_id || ""
                  const createdAt = run.createdAt || run.created_at || ""
                  const isSelected = selectedRuns.has(runId)

                  return (
                    <DataTableRow
                      key={runId}
                      index={index}
                      isSelected={isSelected}
                      onClick={() => runId && router.push(`/parsing-runs/${runId}`)}
                      className="grid-cols-[40px_1fr_140px_180px_100px_60px]"
                    >
                      <DataTableCell className="flex items-center justify-center">
                        <div onClick={(e: any) => e.stopPropagation()}>
                          <Checkbox
                            checked={isSelected}
                            onCheckedChange={() => toggleSelectRun(runId)}
                            onClick={(e) => e.stopPropagation()}
                          />
                        </div>
                      </DataTableCell>

                      <DataTableCell>
                        <div className="flex items-center gap-3">
                          <div className="h-9 w-9 rounded-xl bg-gradient-to-br from-purple-100 to-indigo-100 flex items-center justify-center">
                            <Sparkles className="h-4 w-4 text-purple-600" />
                          </div>
                          <span className="font-medium text-foreground truncate">{run.keyword}</span>
                        </div>
                      </DataTableCell>

                      <DataTableCell>{getStatusBadge(run.status)}</DataTableCell>

                      <DataTableCell>
                        <span className="text-sm text-muted-foreground">
                          {createdAt ? (
                            <span suppressHydrationWarning>
                              {new Date(createdAt).toLocaleString("ru-RU")}
                            </span>
                          ) : "—"}
                        </span>
                      </DataTableCell>

                      <DataTableCell>
                        <Badge variant="outline" className="bg-purple-50 border-purple-200 text-purple-700">
                          {run.resultsCount ?? "—"}
                        </Badge>
                      </DataTableCell>

                      <DataTableCell className="flex items-center justify-end gap-1">
                        <Button
                          variant="ghost"
                          size="sm"
                          onClick={(e) => {
                            e.stopPropagation()
                            if (runId) handleDelete(runId)
                          }}
                          className="h-8 w-8 p-0 text-red-500 hover:text-red-600 hover:bg-red-50"
                        >
                          <Trash2 className="h-4 w-4" />
                        </Button>
                        <ChevronRight className="h-4 w-4 text-muted-foreground" />
                      </DataTableCell>
                    </DataTableRow>
                  )
                })}
              </AnimatePresence>
            )}
          </DataTable>
        </motion.div>
      </motion.main>
    </div>
  )
}

export default function ParsingRunsPageWithAuth() {
  return (
    <AuthGuard allowedRoles={["moderator"]}>
      <ParsingRunsPage />
    </AuthGuard>
  )
}
