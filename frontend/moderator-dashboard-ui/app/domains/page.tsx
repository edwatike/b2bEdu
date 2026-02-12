"use client"

import React, { useEffect, useMemo, useState, useCallback } from "react"
import { useRouter } from "next/navigation"
import { motion, AnimatePresence } from "framer-motion"
import { Navigation } from "@/components/navigation"
import { AuthGuard } from "@/components/auth-guard"
import { PageShell } from "@/components/ui/PageShell"
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card"
import { Button } from "@/components/ui/button"
import { Checkbox } from "@/components/ui/checkbox"
import { GlowSearchInput } from "@/components/ui/glow-search-input"
import { Badge } from "@/components/ui/badge"
import { addToBlacklist, clearPendingDomains, enrichPendingDomain, getPendingDomains, startDomainParserBatch, getDomainHistory, learnManualInn, type DomainLogEntry } from "@/lib/api"
import { extractRootDomain } from "@/lib/utils-domain"
import { toast } from "sonner"
import { Activity, FileSearch, ChevronDown, ChevronRight, Globe, Search, AlertTriangle, CheckCircle2, XCircle, ExternalLink, Zap, Brain, GraduationCap, Clock, Copy } from "lucide-react"
import { useLearningStatistics } from "@/hooks/queries/learning"
import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogFooter,
  DialogHeader,
  DialogTitle,
} from "@/components/ui/dialog"
import { Label } from "@/components/ui/label"
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from "@/components/ui/select"
import { ManualLearnDialog } from "@/components/manual-learn-dialog"
import { LearningStatsBar } from "@/components/learning-stats-bar"

const PAGE_SIZE = 50

type ExtractionLogEntry = {
  url?: string
  inn?: string
  emails?: string[]
  error?: string
}

type EnrichResult = {
  inn?: string | null
  emails?: string[]
  status: string
  error?: string | null
  supplierType?: "supplier" | "needs_moderation" | null
  hasChecko?: boolean
  sourceUrls?: string[]
  extractionLog?: ExtractionLogEntry[]
  dataStatus?: string | null
  reason?: string | null
  history?: DomainLogEntry[]
}

function StatusBadge({ type, hasChecko }: { type: "supplier" | "reseller" | "needs_moderation" | null | undefined; hasChecko?: boolean }) {
  if (!type) return null
  const config = {
    supplier: { bg: "bg-emerald-50", text: "text-emerald-700", border: "border-emerald-200", icon: "🏢", label: "Поставщик" },
    reseller: { bg: "bg-purple-50", text: "text-purple-700", border: "border-purple-200", icon: "🔄", label: "Реселлер" },
    needs_moderation: { bg: "bg-amber-50", text: "text-amber-700", border: "border-amber-200", icon: "⚠️", label: "Треб. модерация" },
  }
  const cfg = config[type]
  return (
    <Badge variant="outline" className={`${cfg.bg} ${cfg.text} ${cfg.border} border text-xs font-medium h-6 px-2`}>
      <span className="mr-1">{cfg.icon}</span>
      {cfg.label}
      {(type === "supplier" || type === "reseller") && hasChecko ? <span className="ml-1">🛡 CHECKO</span> : null}
    </Badge>
  )
}

export default function PendingDomainsPage() {
  return (
    <AuthGuard allowedRoles={["moderator"]}>
      <PendingDomainsPageInner />
    </AuthGuard>
  )
}

function PendingDomainsPageInner() {
  const router = useRouter()
  const [entries, setEntries] = useState<Array<{ domain: string; occurrences: number; last_seen_at?: string | null }>>([])
  const [total, setTotal] = useState(0)
  const [loading, setLoading] = useState(true)
  const [search, setSearch] = useState("")
  const [page, setPage] = useState(0)
  const [selected, setSelected] = useState<Set<string>>(new Set())
  const [bulkRunning, setBulkRunning] = useState(false)
  const [bulkProgress, setBulkProgress] = useState({ total: 0, done: 0, current: "" })
  const [enrichResults, setEnrichResults] = useState<Map<string, EnrichResult>>(new Map())
  const [parsingRunning, setParsingRunning] = useState(false)
  const [parsingProgress, setParsingProgress] = useState({ total: 0, done: 0, current: "" })
  const { data: learningStats } = useLearningStatistics()
  const [filterStatus, setFilterStatus] = useState<"all" | "supplier" | "needs_moderation" | "error" | "unprocessed">("all")

  // Manual Learning State
  const [manualLearnDialogOpen, setManualLearnDialogOpen] = useState(false)
  const [manualLearnDomain, setManualLearnDomain] = useState("")
  const [manualLearnInn, setManualLearnInn] = useState("")
  const [manualLearnSourceUrl, setManualLearnSourceUrl] = useState("")
  const [manualLearnEmail, setManualLearnEmail] = useState("")
  const [manualLearnEmailSourceUrl, setManualLearnEmailSourceUrl] = useState("")
  const [manualLearnSupplierType, setManualLearnSupplierType] = useState<"supplier" | "reseller">("supplier")
  const [manualLearnSubmitting, setManualLearnSubmitting] = useState(false)

  async function loadDomains(nextPage: number = page, searchTerm: string = search) {
    setLoading(true)
    try {
      const query = searchTerm.trim()
      const data = await getPendingDomains({
        limit: PAGE_SIZE,
        offset: nextPage * PAGE_SIZE,
        search: query ? query : undefined,
      })
      setEntries(Array.isArray(data.entries) ? data.entries : [])
      setTotal(Number(data.total || 0))
      setPage(nextPage)
    } catch (e) {
      toast.error("Ошибка загрузки доменов")
    } finally {
      setLoading(false)
    }
  }

  useEffect(() => {
    const handle = setTimeout(() => {
      setSelected(new Set())
      void loadDomains(0, search)
    }, 300)
    return () => clearTimeout(handle)
  }, [search])

  const normalizedEntries = useMemo(() => {
    const map = new Map<string, { domain: string; occurrences: number; last_seen_at?: string | null }>()
    for (const e of entries) {
      const rootRaw = extractRootDomain(e.domain)
      const root = (rootRaw || "").trim().toLowerCase()
      if (!root) continue
      const existing = map.get(root)
      if (!existing) {
        map.set(root, { domain: root, occurrences: e.occurrences || 0, last_seen_at: e.last_seen_at ?? null })
        continue
      }
      const lastSeen =
        existing.last_seen_at && e.last_seen_at
          ? (new Date(existing.last_seen_at) > new Date(e.last_seen_at) ? existing.last_seen_at : e.last_seen_at)
          : (existing.last_seen_at || e.last_seen_at || null)
      map.set(root, {
        domain: root,
        occurrences: (existing.occurrences || 0) + (e.occurrences || 0),
        last_seen_at: lastSeen,
      })
    }
    return Array.from(map.values())
  }, [entries])

  const filtered = normalizedEntries

  const pageCount = Math.max(1, Math.ceil(total / PAGE_SIZE))
  const allSelected = filtered.length > 0 && filtered.every((e) => selected.has(e.domain))

  const toggleSelectAll = (value: boolean) => {
    if (!value) {
      const next = new Set(selected)
      for (const e of filtered) next.delete(e.domain)
      setSelected(next)
      return
    }
    const next = new Set(selected)
    for (const e of filtered) next.add(e.domain)
    setSelected(next)
  }

  const toggleSelectOne = (domain: string, value: boolean) => {
    const next = new Set(selected)
    if (!value) {
      next.delete(domain)
    } else {
      next.add(domain)
    }
    setSelected(next)
  }

  const enrichMetrics = useMemo(() => {
    const supplierCount = Array.from(enrichResults.values()).filter(r => r.supplierType === "supplier").length
    const moderationCount = Array.from(enrichResults.values()).filter(r => r.supplierType === "needs_moderation").length
    const errorCount = Array.from(enrichResults.values()).filter(r => r.status === "failed" || r.error).length
    const totalProcessed = enrichResults.size
    return { supplierCount, moderationCount, errorCount, totalProcessed }
  }, [enrichResults])

  const [expandedDomains, setExpandedDomains] = useState<Set<string>>(new Set())

  const toggleExpanded = useCallback(async (domain: string) => {
    setExpandedDomains(prev => {
      const next = new Set(prev)
      if (next.has(domain)) {
        next.delete(domain)
        return next
      }
      next.add(domain)
      return next
    })

    // Fetch history when expanding if not already present
    if (!expandedDomains.has(domain)) {
      try {
        const hist = await getDomainHistory(domain)
        setEnrichResults(prev => {
          const next = new Map(prev)
          const current = next.get(domain) || { status: "unknown" }
          next.set(domain, { ...current, history: hist.logs })
          return next
        })
      } catch (e) {
        console.error("Failed to fetch history for", domain, e)
      }
    }
  }, [expandedDomains])

  const openManualLearnDialog = (domain: string) => {
    setManualLearnDomain(domain)
    const result = enrichResults.get(domain)
    setManualLearnInn(result?.inn || "")
    setManualLearnEmail(result?.emails?.[0] || "")
    setManualLearnSourceUrl(result?.sourceUrls?.[0] || "")
    setManualLearnEmailSourceUrl("")
    setManualLearnSupplierType("supplier")
    setManualLearnDialogOpen(true)
  }

  const handleManualLearnSubmit = async () => {
    if (!manualLearnDomain || !manualLearnInn || !manualLearnSourceUrl) {
      toast.error("Заполните обязательные поля (Домен, ИНН, Ссылка)")
      return
    }
    setManualLearnSubmitting(true)
    try {
      // Use a generic run ID for manual learning from this page
      const runId = "manual-learning-pending-page"
      await learnManualInn(
        runId,
        manualLearnDomain,
        manualLearnInn,
        manualLearnSourceUrl,
        `manual-${new Date().toISOString().split("T")[0]}`,
      )
      toast.success("Парсер успешно обучен! Паттерн сохранен.")
      setManualLearnDialogOpen(false)
      // Refresh logs
      await toggleExpanded(manualLearnDomain)
    } catch (e: any) {
      toast.error(e.message || "Ошибка обучения")
    } finally {
      setManualLearnSubmitting(false)
    }
  }

  async function handleBulkEnrich() {
    const domains = Array.from(selected)
    if (domains.length === 0) return
    setBulkRunning(true)
    setBulkProgress({ total: domains.length, done: 0, current: "" })
    const newResults = new Map(enrichResults)
    const newExpanded = new Set(expandedDomains)
    try {
      let done = 0
      for (const domain of domains) {
        setBulkProgress({ total: domains.length, done, current: domain })
        try {
          const result = await enrichPendingDomain(domain)
          const hasInn = Boolean(result.inn)
          const hasEmail = Boolean(result.emails && result.emails.length > 0)
          const supplierType: "supplier" | "needs_moderation" | null =
            result.status === "completed" && hasInn && hasEmail
              ? "supplier"
              : result.status === "completed"
                ? "needs_moderation"
                : null
          newResults.set(domain, {
            inn: result.inn,
            emails: result.emails,
            status: result.status,
            error: result.error,
            supplierType,
            hasChecko: supplierType === "supplier" && (result.dataStatus === "complete" || result.dataStatus === "needs_checko"),
            sourceUrls: result.sourceUrls || [],
            extractionLog: (result.extractionLog || []) as ExtractionLogEntry[],
            dataStatus: result.dataStatus,
            reason: result.reason,
          })
          newExpanded.add(domain)
          setEnrichResults(new Map(newResults))
          setExpandedDomains(new Set(newExpanded))
          if (result.status !== "completed") {
            toast.error(`Не удалось получить данные: ${domain}`)
          }
        } catch {
          newResults.set(domain, { status: "failed", error: "Ошибка запроса", supplierType: null, sourceUrls: [], extractionLog: [], reason: "Ошибка сети" })
          newExpanded.add(domain)
          setEnrichResults(new Map(newResults))
          setExpandedDomains(new Set(newExpanded))
          toast.error(`Ошибка получения данных: ${domain}`)
        } finally {
          done += 1
          setBulkProgress({ total: domains.length, done, current: domain })
        }
      }
      const suppliers = Array.from(newResults.values()).filter(r => r.supplierType === "supplier").length
      const moderation = Array.from(newResults.values()).filter(r => r.supplierType === "needs_moderation").length
      toast.success(`Готово: ${done} доменов (🏢 ${suppliers} поставщиков, ⚠️ ${moderation} треб. модерация)`)
      setSelected(new Set())
      await loadDomains(0, search)
    } finally {
      setBulkRunning(false)
    }
  }

  async function handleClearAll() {
    setLoading(true)
    try {
      const result = await clearPendingDomains()
      toast.success(`Удалено: ${result.deleted}`)
      setSelected(new Set())
      setEnrichResults(new Map())
      await loadDomains(0, search)
    } catch {
      toast.error("Ошибка очистки списка")
    } finally {
      setLoading(false)
    }
  }

  async function handleStartParsing() {
    const domains = Array.from(selected)
    if (domains.length === 0) return
    setParsingRunning(true)
    setParsingProgress({ total: domains.length, done: 0, current: "" })
    try {
      const runId = crypto.randomUUID()
      const result = await startDomainParserBatch(runId, domains, false)
      toast.success(`Парсинг запущен: ${domains.length} доменов в обработке (Run: ${result.parserRunId.slice(0, 8)})`)
      setSelected(new Set())
      await loadDomains(0, search)
    } catch (error: any) {
      toast.error(error.message || "Ошибка запуска парсинга")
    } finally {
      setParsingRunning(false)
    }
  }

  return (
    <div className="min-h-screen bg-gradient-to-br from-slate-50 via-purple-50/30 to-indigo-50/20">
      <Navigation />
      <PageShell
        title="Домены в очереди"
        description="Домены, которые еще не стали поставщиками и не в blacklist"
        icon={Globe}
        gradientFrom="from-emerald-600"
        gradientTo="to-teal-600"
        actions={
          <div className="flex items-center gap-2">
            <div className="w-full max-w-[314px]">
              <GlowSearchInput
                placeholder="Поиск домена..."
                value={search}
                onChange={(e) => setSearch(e.target.value)}
                containerClassName="w-full"
              />
            </div>
            <Button variant="outline" size="sm" onClick={() => loadDomains(page, search)} disabled={loading} className="border-emerald-200 text-emerald-700 hover:bg-emerald-50">
              Обновить
            </Button>
          </div>
        }
      >
        {/* Actions bar */}
        <motion.div
          initial={{ opacity: 0, y: 20 }}
          animate={{ opacity: 1, y: 0 }}
          transition={{ duration: 0.5, delay: 0.1 }}
        >
          <Card className="p-4 bg-white/80 backdrop-blur-sm border-emerald-100 shadow-sm">
            <div className="flex items-center justify-between flex-wrap gap-2">
              <div className="flex items-center gap-2 flex-wrap">
                <Select value={filterStatus} onValueChange={(v) => setFilterStatus(v as any)}>
                  <SelectTrigger className="w-[180px] h-8 text-xs">
                    <SelectValue placeholder="Фильтр" />
                  </SelectTrigger>
                  <SelectContent>
                    <SelectItem value="all">Все домены</SelectItem>
                    <SelectItem value="supplier">Поставщики</SelectItem>
                    <SelectItem value="needs_moderation">Требуют модерации</SelectItem>
                    <SelectItem value="error">Ошибки</SelectItem>
                    <SelectItem value="unprocessed">Не обработаны</SelectItem>
                  </SelectContent>
                </Select>
                <Button
                  size="sm"
                  variant="outline"
                  onClick={() => toggleSelectAll(!allSelected)}
                  disabled={filtered.length === 0}
                  className="h-8 text-xs border-purple-300 text-purple-700 hover:bg-purple-50 bg-transparent"
                >
                  {allSelected ? "Отменить все" : `Выбрать все (${filtered.length})`}
                </Button>
                {selected.size > 0 && (
                  <Badge variant="outline" className="bg-purple-50 border-purple-200 text-purple-700">
                    Выбрано: {selected.size}
                  </Badge>
                )}
                <Button
                  size="sm"
                  onClick={handleBulkEnrich}
                  disabled={bulkRunning || parsingRunning || selected.size === 0}
                  className="bg-gradient-to-r from-blue-600 to-cyan-600 hover:from-blue-700 hover:to-cyan-700 text-white shadow-md shadow-blue-500/20"
                >
                  <FileSearch className="h-3.5 w-3.5 mr-1" />
                  {bulkRunning ? "Получаем..." : selected.size > 0 ? `Получить данные (${selected.size})` : "Получить данные"}
                </Button>
                <Button
                  size="sm"
                  onClick={handleStartParsing}
                  disabled={parsingRunning || bulkRunning || selected.size === 0}
                  className="bg-gradient-to-r from-purple-600 to-indigo-600 hover:from-purple-700 hover:to-indigo-700 text-white shadow-md shadow-purple-500/20"
                >
                  <Zap className="h-3.5 w-3.5 mr-1" />
                  {parsingRunning ? "Парсим..." : selected.size > 0 ? `Запустить парсинг (${selected.size})` : "Запустить парсинг"}
                </Button>
              </div>
              <Button variant="destructive" size="sm" onClick={handleClearAll} disabled={loading || bulkRunning} className="bg-gradient-to-r from-red-600 to-orange-600 hover:from-red-700 hover:to-orange-700">
                Очистить список
              </Button>
            </div>
          </Card>
        </motion.div>

        {/* Learning Statistics */}
        {learningStats && <LearningStatsBar stats={learningStats} variant="banner" />}

        {/* === Блок метрик: Извлечение ИНН/Email (как в parsing run) === */}
        {enrichResults.size > 0 && (
          <motion.div
            initial={{ opacity: 0, y: 20 }}
            animate={{ opacity: 1, y: 0 }}
            transition={{ duration: 0.5, delay: 0.15 }}
            className="rounded-lg border border-slate-200 bg-white/80 backdrop-blur-sm shadow-sm overflow-hidden">
            <div className="flex items-center justify-between px-3 py-2 bg-slate-50 border-b border-slate-200">
              <span className="text-sm font-semibold text-slate-700">Извлечение ИНН / Email</span>
              <div className="flex items-center gap-1.5 text-xs">
                <span className="px-2 py-0.5 rounded-full bg-emerald-50 text-emerald-700 border border-emerald-200 font-medium">🏢 {enrichMetrics.supplierCount}</span>
                <span className="px-2 py-0.5 rounded-full bg-amber-50 text-amber-700 border border-amber-200 font-medium">⚠️ {enrichMetrics.moderationCount}</span>
                {enrichMetrics.errorCount > 0 && (
                  <span className="px-2 py-0.5 rounded-full bg-red-50 text-red-700 border border-red-200 font-medium">❌ {enrichMetrics.errorCount}</span>
                )}
                <span className="text-slate-400">/ {enrichMetrics.totalProcessed} обработано</span>
              </div>
            </div>
            {enrichMetrics.totalProcessed > 0 && (
              <div className="w-full bg-slate-100 h-1.5 flex">
                {enrichMetrics.supplierCount > 0 && (
                  <div className="bg-emerald-500 h-1.5 transition-all duration-500" style={{ width: `${(enrichMetrics.supplierCount / enrichMetrics.totalProcessed) * 100}%` }} />
                )}
                {enrichMetrics.moderationCount > 0 && (
                  <div className="bg-amber-400 h-1.5 transition-all duration-500" style={{ width: `${(enrichMetrics.moderationCount / enrichMetrics.totalProcessed) * 100}%` }} />
                )}
                {enrichMetrics.errorCount > 0 && (
                  <div className="bg-red-400 h-1.5 transition-all duration-500" style={{ width: `${(enrichMetrics.errorCount / enrichMetrics.totalProcessed) * 100}%` }} />
                )}
              </div>
            )}
            {!bulkRunning && enrichMetrics.totalProcessed > 0 && (
              <div className="px-3 py-2">
                <div className="flex items-center gap-2 text-xs text-emerald-700 bg-emerald-50 rounded-md px-2 py-1.5 border border-emerald-200">
                  <span className="text-base">✅</span>
                  <span className="font-semibold">Обработано {enrichMetrics.totalProcessed} доменов</span>
                  <span className="text-slate-500 ml-2">🏢 {enrichMetrics.supplierCount} поставщиков • ⚠️ {enrichMetrics.moderationCount} треб. модерация</span>
                </div>
              </div>
            )}
          </motion.div>
        )}

        {/* === Прогресс обработки (во время работы) === */}
        {bulkRunning && (
          <motion.div
            initial={{ opacity: 0, scale: 0.98 }}
            animate={{ opacity: 1, scale: 1 }}
            transition={{ duration: 0.3 }}
            className="rounded-lg border border-blue-100 bg-blue-50/80 backdrop-blur-sm px-4 py-3">
            <div className="flex items-center justify-between text-sm text-blue-800">
              <div className="flex items-center gap-2">
                <Activity className="h-4 w-4 animate-spin" />
                <span className="font-semibold">Обработка: {bulkProgress.done}/{bulkProgress.total}</span>
              </div>
              <span className="truncate max-w-[50%] text-blue-600">🔍 {bulkProgress.current}</span>
            </div>
            <div className="mt-2 w-full bg-blue-200 rounded-full h-2">
              <div
                className="bg-blue-600 h-2 rounded-full transition-all duration-300"
                style={{ width: `${bulkProgress.total ? (bulkProgress.done / bulkProgress.total) * 100 : 0}%` }}
              />
            </div>
          </motion.div>
        )}

        <AnimatePresence>
        {selected.size > 0 && !bulkRunning && (
          <motion.div
            initial={{ opacity: 0, height: 0 }}
            animate={{ opacity: 1, height: "auto" }}
            exit={{ opacity: 0, height: 0 }}
            className="flex items-center justify-between gap-4 rounded-lg border border-amber-200 bg-amber-50/80 backdrop-blur-sm px-4 py-3">
            <div className="text-sm text-amber-900">
              Выбрано доменов: <strong>{selected.size}</strong>
            </div>
            <div className="flex items-center gap-2">
              <Button variant="outline" size="sm" onClick={() => setSelected(new Set())} disabled={bulkRunning}>
                Снять выбор
              </Button>
              <Button
                size="sm"
                onClick={handleBulkEnrich}
                disabled={bulkRunning}
                className="bg-gradient-to-r from-blue-600 to-cyan-600 hover:from-blue-700 hover:to-cyan-700 text-white shadow-md shadow-blue-500/20"
              >
                <FileSearch className="h-3.5 w-3.5 mr-1" />
                Получить данные
              </Button>
            </div>
          </motion.div>
        )}
        </AnimatePresence>

        <motion.div
          initial={{ opacity: 0, y: 20 }}
          animate={{ opacity: 1, y: 0 }}
          transition={{ duration: 0.7, delay: 0.2 }}
        >
        <Card className="bg-white/80 backdrop-blur-sm border-emerald-100 shadow-sm">
          <CardHeader>
            <CardTitle className="flex items-center gap-2">
              <Globe className="h-5 w-5 text-emerald-600" />
              Список доменов
              <Badge variant="outline" className="ml-2 bg-emerald-50 border-emerald-200 text-emerald-700">{total}</Badge>
            </CardTitle>
          </CardHeader>
          <CardContent>
            {loading ? (
              <div className="flex items-center justify-center py-12 text-muted-foreground">
                <Activity className="h-5 w-5 animate-spin mr-2" />
                Загрузка...
              </div>
            ) : filtered.length === 0 ? (
              <div className="flex flex-col items-center justify-center py-16 text-center">
                <div className="h-16 w-16 rounded-2xl bg-emerald-50 flex items-center justify-center mb-4">
                  <Globe className="h-8 w-8 text-emerald-300" />
                </div>
                <h3 className="text-lg font-semibold text-foreground mb-1">Нет данных</h3>
                <p className="text-sm text-muted-foreground">Домены не найдены. Попробуйте изменить поиск.</p>
              </div>
            ) : (() => {
              const displayRows = filtered.filter((row) => {
                const result = enrichResults.get(row.domain)
                if (filterStatus === "all") return true
                if (filterStatus === "supplier") return result?.supplierType === "supplier"
                if (filterStatus === "needs_moderation") return result?.supplierType === "needs_moderation"
                if (filterStatus === "error") return result?.status === "failed" || !!result?.error
                if (filterStatus === "unprocessed") return !result
                return true
              })

              if (displayRows.length === 0) {
                return (
                  <div className="text-center py-12 text-muted-foreground">
                    Нет доменов с выбранным фильтром
                  </div>
                )
              }

              return (
                <div className="w-full">
                  <div className="border rounded-md overflow-hidden">
                    <div className="flex items-center gap-3 px-3 py-2 bg-slate-50 border-b flex-wrap">
                      <span className="font-semibold text-sm">Результаты</span>
                      <div className="flex gap-1.5 text-xs">
                        {enrichMetrics.supplierCount > 0 && (
                          <Badge className="bg-emerald-100 text-emerald-700 border-emerald-200">🏢 {enrichMetrics.supplierCount}</Badge>
                        )}
                        {enrichMetrics.moderationCount > 0 && (
                          <Badge className="bg-amber-100 text-amber-700 border-amber-200">⚠️ {enrichMetrics.moderationCount}</Badge>
                        )}
                        {enrichMetrics.errorCount > 0 && (
                          <Badge variant="destructive" className="text-xs">❌ {enrichMetrics.errorCount}</Badge>
                        )}
                        <span className="text-slate-400">/ {enrichMetrics.totalProcessed} обработано</span>
                      </div>
                    </div>

                    <table className="w-full text-xs">
                      <thead className="bg-white">
                        <tr className="border-b">
                          <th className="py-2 px-2 w-8">
                            <Checkbox
                              checked={displayRows.length > 0 && displayRows.every((r) => selected.has(r.domain))}
                              onCheckedChange={() => {
                                const allSel = displayRows.every((r) => selected.has(r.domain))
                                if (allSel) {
                                  const next = new Set(selected)
                                  for (const r of displayRows) next.delete(r.domain)
                                  setSelected(next)
                                } else {
                                  const next = new Set(selected)
                                  for (const r of displayRows) next.add(r.domain)
                                  setSelected(next)
                                }
                              }}
                            />
                          </th>
                          <th className="text-left py-2 px-3 font-semibold text-slate-600">Домен</th>
                          <th className="text-left py-2 px-3 font-semibold text-slate-600">Статус</th>
                          <th className="text-left py-2 px-3 font-semibold text-slate-600">ИНН</th>
                          <th className="text-left py-2 px-3 font-semibold text-slate-600">Email</th>
                          <th className="text-left py-2 px-3 font-semibold text-slate-600">Проверено URL</th>
                          <th className="text-left py-2 px-3 font-semibold text-slate-600">Действия</th>
                        </tr>
                      </thead>
                      <tbody>
                        {displayRows.map((row, index) => {
                          const result = enrichResults.get(row.domain)
                          const isProcessing = bulkRunning && bulkProgress.current === row.domain
                          const isExpanded = expandedDomains.has(row.domain)
                          const hasLog = result && (result.extractionLog?.length || result.sourceUrls?.length || result.reason)

                          return (
                            <React.Fragment key={row.domain}>
                              <tr className={`border-b border-slate-100 ${selected.has(row.domain) ? "bg-purple-50/60" : index % 2 === 0 ? "bg-white" : "bg-slate-50/50"}`}>
                                <td className="py-1.5 px-2 w-8">
                                  <Checkbox
                                    checked={selected.has(row.domain)}
                                    onCheckedChange={() => toggleSelectOne(row.domain, !selected.has(row.domain))}
                                  />
                                </td>
                                <td className="py-1.5 px-3">
                                  <div className="flex items-center gap-1.5">
                                    {hasLog ? (
                                      <button onClick={() => toggleExpanded(row.domain)} className="p-0.5 rounded hover:bg-slate-200 transition-colors">
                                        {isExpanded ? <ChevronDown className="h-3.5 w-3.5 text-slate-500" /> : <ChevronRight className="h-3.5 w-3.5 text-slate-400" />}
                                      </button>
                                    ) : (
                                      <span className="w-5" />
                                    )}
                                    <a href={`https://${row.domain}`} target="_blank" rel="noreferrer" className="font-mono text-blue-700 hover:underline">
                                      {row.domain}
                                    </a>
                                  </div>
                                </td>
                                <td className="py-1.5 px-3">
                                  {isProcessing ? (
                                    <Badge variant="outline" className="bg-blue-50 text-blue-700 border-blue-200 text-xs h-6 px-2">
                                      <Activity className="h-3 w-3 mr-1 animate-spin" /> Парсинг...
                                    </Badge>
                                  ) : result ? (
                                    <StatusBadge type={result.supplierType} hasChecko={result.hasChecko} />
                                  ) : (
                                    <span className="text-slate-400">Не обработан</span>
                                  )}
                                </td>
                                <td className="py-1.5 px-3">
                                  {result?.inn ? (
                                    <div className="flex items-center gap-1">
                                      <span className="text-blue-700 font-medium">{result.inn}</span>
                                      <button
                                        type="button"
                                        className="text-slate-400 hover:text-blue-600 transition-colors"
                                        title="Копировать ИНН"
                                        onClick={() => {
                                          navigator.clipboard.writeText(result.inn || "")
                                          toast.success(`ИНН ${result.inn} скопирован`)
                                        }}
                                      >
                                        <Copy className="h-3 w-3" />
                                      </button>
                                    </div>
                                  ) : result ? (
                                    <span className="text-red-400">не найден</span>
                                  ) : (
                                    <span className="text-slate-400">—</span>
                                  )}
                                </td>
                                <td className="py-1.5 px-3">
                                  {result?.emails && result.emails.length > 0 ? (
                                    <div className="flex items-center gap-1">
                                      <span className="text-emerald-700 truncate max-w-[180px]">{result.emails.join(", ")}</span>
                                      <button
                                        type="button"
                                        className="text-slate-400 hover:text-emerald-600 transition-colors"
                                        title="Копировать Email"
                                        onClick={() => {
                                          navigator.clipboard.writeText((result.emails || []).join(", "))
                                          toast.success("Email скопирован")
                                        }}
                                      >
                                        <Copy className="h-3 w-3" />
                                      </button>
                                    </div>
                                  ) : result ? (
                                    <span className="text-red-400">не найден</span>
                                  ) : (
                                    <span className="text-slate-400">—</span>
                                  )}
                                </td>
                                <td className="py-1.5 px-3">
                                  {result?.extractionLog && result.extractionLog.length > 0 ? (
                                    <span className="text-slate-500">
                                      {result.extractionLog.length} стр.
                                      {result.extractionLog.filter(e => e.inn).length > 0 && <span className="text-blue-600 ml-1">•📋{result.extractionLog.filter(e => e.inn).length}</span>}
                                      {result.extractionLog.filter(e => e.emails && e.emails.length > 0).length > 0 && <span className="text-emerald-600 ml-1">•📧{result.extractionLog.filter(e => e.emails && e.emails.length > 0).length}</span>}
                                    </span>
                                  ) : result?.sourceUrls && result.sourceUrls.length > 0 ? (
                                    <span className="text-slate-500">{result.sourceUrls.length} стр.</span>
                                  ) : (
                                    <span className="text-slate-400">—</span>
                                  )}
                                </td>
                                <td className="py-1.5 px-3">
                                  <div className="flex items-center gap-1">
                                    <Button variant="outline" size="sm" className="h-6 text-[10px] px-2" onClick={() => openManualLearnDialog(row.domain)}>
                                      <GraduationCap className="h-3 w-3 mr-0.5" />
                                      Обучить
                                    </Button>
                                    <Button variant="outline" size="sm" className="h-6 text-[10px] px-2" onClick={async () => {
                                      try {
                                        await addToBlacklist({ domain: row.domain, reason: "Добавлено модератором из очереди доменов", addedBy: "moderator" })
                                        toast.success("Домен добавлен в blacklist")
                                        await loadDomains(page, search)
                                      } catch { toast.error("Ошибка добавления в blacklist") }
                                    }}>
                                      BL
                                    </Button>
                                    <Button size="sm" className="h-6 text-[10px] px-2" onClick={() => router.push(`/suppliers/new?domain=${encodeURIComponent(row.domain)}`)}>
                                      +
                                    </Button>
                                  </div>
                                </td>
                              </tr>
                              {/* Expanded enrichment log */}
                              {isExpanded && result && (
                                <tr>
                                  <td colSpan={7} className="bg-slate-50 border-b border-slate-200 px-4 py-3">
                                    {/* Summary card */}
                                    <div className={`rounded-lg border p-3 mb-3 ${
                                      result.supplierType === "supplier" ? "bg-emerald-50 border-emerald-200" :
                                      result.status === "failed" ? "bg-red-50 border-red-200" :
                                      "bg-amber-50 border-amber-200"
                                    }`}>
                                      <div className="flex items-start gap-2">
                                        {result.supplierType === "supplier" ? (
                                          <CheckCircle2 className="h-4 w-4 text-emerald-600 mt-0.5 shrink-0" />
                                        ) : result.status === "failed" ? (
                                          <XCircle className="h-4 w-4 text-red-600 mt-0.5 shrink-0" />
                                        ) : (
                                          <AlertTriangle className="h-4 w-4 text-amber-600 mt-0.5 shrink-0" />
                                        )}
                                        <div>
                                          <div className={`text-sm font-semibold ${
                                            result.supplierType === "supplier" ? "text-emerald-800" :
                                            result.status === "failed" ? "text-red-800" : "text-amber-800"
                                          }`}>
                                            {result.supplierType === "supplier" ? "Поставщик найден" :
                                             result.status === "failed" ? "Ошибка обработки" : "Требуется модерация"}
                                          </div>
                                          {result.reason && <div className="text-xs mt-0.5 text-slate-600"><strong>Причина:</strong> {result.reason}</div>}
                                          {result.error && <div className="text-xs mt-0.5 text-red-600"><strong>Ошибка:</strong> {result.error}</div>}
                                        </div>
                                      </div>
                                    </div>

                                    {/* History */}
                                    {result.history && result.history.length > 0 && (
                                      <div className="rounded-lg border border-slate-200 bg-white overflow-hidden mb-3">
                                        <div className="px-3 py-2 bg-slate-100 border-b border-slate-200 flex items-center gap-1.5">
                                          <Clock className="h-3.5 w-3.5 text-slate-500" />
                                          <span className="text-xs font-semibold text-slate-700">История парсинга</span>
                                          <span className="text-xs text-slate-400 ml-auto">{result.history.length} записей</span>
                                        </div>
                                        <div className="divide-y divide-slate-100 max-h-48 overflow-y-auto">
                                          {result.history.map((log) => (
                                            <div key={log.id} className="px-3 py-2 text-xs flex flex-col gap-1 hover:bg-slate-50">
                                              <div className="flex items-center justify-between">
                                                <span className={`font-semibold ${
                                                  log.action === "completed" || log.action === "supplier" ? "text-emerald-700" :
                                                  log.action === "failed" || log.action === "error" ? "text-red-600" : "text-blue-700"
                                                }`}>{log.action}</span>
                                                <span className="text-slate-400">{log.created_at ? new Date(log.created_at).toLocaleString("ru-RU") : "—"}</span>
                                              </div>
                                              {log.message && <div className="text-slate-600">{log.message}</div>}
                                            </div>
                                          ))}
                                        </div>
                                      </div>
                                    )}

                                    {/* Extraction log */}
                                    {result.extractionLog && result.extractionLog.length > 0 && (
                                      <div className="rounded-lg border border-slate-200 bg-white overflow-hidden">
                                        <div className="px-3 py-2 bg-slate-100 border-b border-slate-200 flex items-center gap-1.5">
                                          <Search className="h-3.5 w-3.5 text-slate-500" />
                                          <span className="text-xs font-semibold text-slate-700">Лог парсинга</span>
                                          <span className="text-xs text-slate-400 ml-auto">{result.extractionLog.length} URL</span>
                                        </div>
                                        <div className="divide-y divide-slate-100 max-h-48 overflow-y-auto">
                                          {result.extractionLog.map((log, i) => (
                                            <div key={i} className="px-3 py-2 text-xs flex items-start gap-2 hover:bg-slate-50">
                                              <span className="shrink-0 mt-0.5">
                                                {log.error ? <XCircle className="h-3.5 w-3.5 text-red-400" /> :
                                                 log.inn || (log.emails && log.emails.length > 0) ? <CheckCircle2 className="h-3.5 w-3.5 text-emerald-500" /> :
                                                 <Search className="h-3.5 w-3.5 text-slate-400" />}
                                              </span>
                                              <div className="min-w-0 flex-1">
                                                <a href={log.url} target="_blank" rel="noreferrer" className="text-blue-600 hover:underline truncate block">{log.url}</a>
                                                <div className="flex items-center gap-3 mt-0.5">
                                                  {log.inn && <span className="text-emerald-700"><strong>ИНН:</strong> {log.inn}</span>}
                                                  {log.emails && log.emails.length > 0 && <span className="text-blue-700"><strong>Email:</strong> {log.emails.join(", ")}</span>}
                                                  {log.error && <span className="text-red-500"><strong>Ошибка:</strong> {log.error}</span>}
                                                  {!log.inn && !log.error && (!log.emails || log.emails.length === 0) && <span className="text-slate-400 italic">ничего не найдено</span>}
                                                </div>
                                              </div>
                                            </div>
                                          ))}
                                        </div>
                                      </div>
                                    )}

                                    {/* Source URLs fallback */}
                                    {(!result.extractionLog || result.extractionLog.length === 0) && result.sourceUrls && result.sourceUrls.length > 0 && (
                                      <div className="rounded-lg border border-slate-200 bg-white overflow-hidden">
                                        <div className="px-3 py-2 bg-slate-100 border-b border-slate-200 flex items-center gap-1.5">
                                          <Globe className="h-3.5 w-3.5 text-slate-500" />
                                          <span className="text-xs font-semibold text-slate-700">Источники данных</span>
                                        </div>
                                        <div className="px-3 py-2 space-y-1">
                                          {result.sourceUrls.map((url, i) => (
                                            <a key={i} href={url} target="_blank" rel="noreferrer" className="text-xs text-blue-600 hover:underline flex items-center gap-1">
                                              {url} <ExternalLink className="h-3 w-3 text-slate-400" />
                                            </a>
                                          ))}
                                        </div>
                                      </div>
                                    )}
                                  </td>
                                </tr>
                              )}
                            </React.Fragment>
                          )
                        })}
                      </tbody>
                    </table>
                  </div>
                </div>
              )
            })()}
          </CardContent>
        </Card>
        </motion.div>

        <motion.div
          initial={{ opacity: 0, y: 20 }}
          animate={{ opacity: 1, y: 0 }}
          transition={{ duration: 0.5, delay: 0.3 }}
          className="flex items-center justify-between"
        >
          <div className="text-sm text-muted-foreground">
            Страница {page + 1} из {pageCount} • всего {total}
          </div>
          <div className="flex items-center gap-2">
            <Button variant="outline" disabled={page <= 0 || loading} onClick={() => loadDomains(page - 1, search)}>
              Назад
            </Button>
            <Button
              variant="outline"
              disabled={page >= pageCount - 1 || loading}
              onClick={() => loadDomains(page + 1, search)}
            >
              Вперёд
            </Button>
          </div>
        </motion.div>

        {/* Manual Learning Dialog */}
        <ManualLearnDialog
          open={manualLearnDialogOpen}
          onOpenChange={setManualLearnDialogOpen}
          domain={manualLearnDomain}
          inn={manualLearnInn}
          email={manualLearnEmail}
          innSourceUrl={manualLearnSourceUrl}
          submitting={manualLearnSubmitting}
          onSubmit={(data) => {
            setManualLearnInn(data.inn)
            setManualLearnSourceUrl(data.sourceUrl)
            handleManualLearnSubmit()
          }}
        />
      </PageShell>
    </div>
  )
}
