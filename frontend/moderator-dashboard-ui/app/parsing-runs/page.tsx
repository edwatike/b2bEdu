"use client"

import { useState, useEffect } from "react"
import { toast } from "sonner"
import { motion, AnimatePresence } from "framer-motion"
import { useRouter } from "next/navigation"
import { Card } from "@/components/ui/card"
import { Button } from "@/components/ui/button"
import { GlowSearchInput } from "@/components/ui/glow-search-input"
import { Checkbox } from "@/components/ui/checkbox"
import { Badge } from "@/components/ui/badge"
import { Table, TableBody, TableCell, TableHead, TableHeader, TableRow } from "@/components/ui/table"
import { Navigation } from "@/components/navigation"
import { AuthGuard } from "@/components/auth-guard"
import { PageShell } from "@/components/ui/PageShell"
import {
  DataTable,
  DataTableHeader,
  DataTableRow,
  DataTableCell,
  DataTableEmpty,
  DataTableSkeleton,
} from "@/components/ui/data-table"
import { APIError, getParsingRuns, deleteParsingRun, deleteParsingRunsBulk } from "@/lib/api"
import { Search, Trash2, Clock, Calendar, ChevronRight, RefreshCw } from "lucide-react"
import { RunStatusBadge } from "@/components/run-status-badge"
import type { ParsingRunDTO } from "@/lib/types"

function ParsingRunsPage() {
  const router = useRouter()
  const [runs, setRuns] = useState<ParsingRunDTO[]>([])
  const [loading, setLoading] = useState(true)
  const [searchQuery, setSearchQuery] = useState("")
  const [selectedRuns, setSelectedRuns] = useState<Set<string>>(new Set())


  useEffect(() => {
    const handle = setTimeout(() => {
      void loadRuns()
    }, 300)
    return () => clearTimeout(handle)
  }, [searchQuery])

  async function loadRuns() {
    setLoading(true)
    try {
      const params: any = { limit: 100, sort: "created_at", order: "desc" }
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

  // Status badge rendering delegated to shared RunStatusBadge component

  return (
    <div className="min-h-screen bg-gradient-to-br from-slate-50 via-purple-50/30 to-indigo-50/20">
      <Navigation />
      <PageShell
        title="Запуски"
        description="История и управление запусками"
        icon={Clock}
        gradientFrom="from-purple-600"
        gradientTo="to-indigo-600"
      >
        {/* Filters */}
        <motion.div
          initial={{ opacity: 0, y: 20 }}
          animate={{ opacity: 1, y: 0 }}
          transition={{ duration: 0.6, delay: 0.1 }}
        >
          <Card className="p-4 bg-white/80 backdrop-blur-sm border-purple-100 shadow-sm">
            <div className="flex flex-col lg:flex-row gap-4">
              <div className="flex-1">
                <GlowSearchInput
                  id="parsing-search"
                  name="parsing-search"
                  autoComplete="off"
                  aria-label="Поиск по ключевому слову"
                  placeholder="Поиск по ключевому слову..."
                  value={searchQuery}
                  onChange={(e) => setSearchQuery(e.target.value)}
                  containerClassName="w-full"
                />
              </div>
              <Button
                variant="outline"
                size="sm"
                onClick={() => loadRuns()}
                className="border-purple-200 text-purple-700 hover:bg-purple-50"
              >
                <RefreshCw className="h-4 w-4 mr-2" />
                Обновить
              </Button>
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
                            <Clock className="h-4 w-4 text-purple-600" />
                          </div>
                          <span className="font-medium text-foreground truncate">{run.keyword}</span>
                        </div>
                      </DataTableCell>

                      <DataTableCell><RunStatusBadge status={run.status} /></DataTableCell>

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
      </PageShell>
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
