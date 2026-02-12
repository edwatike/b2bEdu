"use client"

import React, { useState, useEffect, useRef } from "react"
import { useRouter, useParams } from "next/navigation"
import { motion } from "framer-motion"
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card"
import { FlinstonesProgressBar } from "@/components/flintstones-wheel"
import { SupplierIcon } from "@/components/supplier-icon"
import { Checkbox } from "@/components/ui/checkbox"
import { GlowSearchInput } from "@/components/ui/glow-search-input"
import { Button } from "@/components/ui/button"
import { Badge } from "@/components/ui/badge"
import { Accordion, AccordionContent, AccordionItem, AccordionTrigger } from "@/components/ui/accordion"
import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogFooter,
  DialogHeader,
  DialogTitle,
} from "@/components/ui/dialog"
import { Input } from "@/components/ui/input"
import { Textarea } from "@/components/ui/textarea"
import { Label } from "@/components/ui/label"
import { Progress } from "@/components/ui/progress"
import { Navigation } from "@/components/navigation"
import { CheckoInfoDialog } from "@/components/checko-info-dialog"
import { DomainHistoryDialog } from "@/components/parsing/DomainHistoryDialog"
import { AuthGuard } from "@/components/auth-guard"
import {
  getParsingRun,
  getDomainsQueue,
  getBlacklist,
  addToBlacklist,
  createSupplier,
  attachDomainToSupplier,
  updateSupplier,
  getSuppliers,
  getParsingLogs,
  getCheckoData,
  startDomainParserBatch,
  getDomainParserStatus,
  getDomainModerationDomains,
  learnManualInn,
  pauseDomainParserWorker,
  resumeDomainParserWorker,
  getDomainParserWorkerStatus,
  APIError,
  type LearnedItem,
  type LearningStatistics,
  type DomainParserWorkerStatus,
} from "@/lib/api"
import { useDomainParserStatus, useParsingLogs as useParsingLogsQuery } from "@/hooks/queries/parsing"
import {
  groupByDomain,
  extractRootDomain,
  collectDomainSources,
  normalizeUrl,
  getLatestUrlCreatedAt,
} from "@/lib/utils-domain"
import {
  getCachedSuppliers,
  setCachedSuppliers,
  setCachedBlacklist,
  invalidateSuppliersCache,
  invalidateBlacklistCache,
} from "@/lib/cache"
import { toast } from "sonner"
import {
  ExternalLink,
  Copy,
  FileSearch,
  Clock,
  Activity,
  CheckCircle,
  XCircle,
  Globe,
  Target,
  GraduationCap,
  Layers,
  Search,
} from "lucide-react"
import type {
  ParsingDomainGroup,
  ParsingRunDTO,
  SupplierDTO,
  DomainParserResult,
  DomainParserStatusResponse,
} from "@/lib/types"

// </CHANGE> Removed 'use' import, using useParams instead for client component
function ParsingRunDetailsPage() {
  const router = useRouter()
  // </CHANGE> Using useParams() hook instead of use(params) for client component
  const params = useParams()
  const runId = params.runId as string
  const [run, setRun] = useState<ParsingRunDTO | null>(null)
  const [groups, setGroups] = useState<ParsingDomainGroup[]>([])
  const [loading, setLoading] = useState(true)
  const [refreshKey, setRefreshKey] = useState(0) // Ключ для принудительного обновления
  const [supplierDialogOpen, setSupplierDialogOpen] = useState(false)
  const [blacklistDialogOpen, setBlacklistDialogOpen] = useState(false)
  const [blacklistDomain, setBlacklistDomain] = useState("")
  const [blacklistReason, setBlacklistReason] = useState("")
  const [addingToBlacklist, setAddingToBlacklist] = useState(false)
  const [selectedDomain, setSelectedDomain] = useState("")
  const [editingSupplierId, setEditingSupplierId] = useState<number | null>(null) // ID существующего поставщика для редактирования
  const [supplierForm, setSupplierForm] = useState({
    name: "",
    inn: "",
    email: "",
    domain: "",
    address: "",
    type: "supplier" as "supplier" | "reseller",
    // Checko fields
    ogrn: "",
    kpp: "",
    okpo: "",
    companyStatus: "",
    registrationDate: "",
    legalAddress: "",
    phone: "",
    website: "",
    vk: "",
    telegram: "",
    authorizedCapital: null as number | null,
    revenue: null as number | null,
    profit: null as number | null,
    financeYear: null as number | null,
    legalCasesCount: null as number | null,
    legalCasesSum: null as number | null,
    legalCasesAsPlaintiff: null as number | null,
    legalCasesAsDefendant: null as number | null,
    checkoData: null as string | null,
  })
  const [innConflict, setInnConflict] = useState<{
    existingSupplierId: number
    existingSupplierName?: string
    existingSupplierDomains?: string[]
    existingSupplierEmails?: string[]
  } | null>(null)
  const [searchQuery, setSearchQuery] = useState("")
  const [filterStatus, setFilterStatus] = useState<"all" | "supplier" | "reseller" | "needs_moderation">("all")
  const [filterMenuOpen, setFilterMenuOpen] = useState(false)
  const [parsingLogs, setParsingLogs] = useState<{
    google?: {
      total_links: number
      pages_processed: number
      last_links: string[]
      links_by_page?: Record<number, number>
    }
    yandex?: {
      total_links: number
      pages_processed: number
      last_links: string[]
      links_by_page?: Record<number, number>
    }
  } | null>(null)
  const [accordionValue, setAccordionValue] = useState<string[]>([]) // Состояние аккордеона для логов парсинга
  const [selectedDomains, setSelectedDomains] = useState<Set<string>>(new Set()) // Выбранные домены для Domain Parser

  const [parserRunId, setParserRunId] = useState<string | null>(null)
  const [parserStatus, setParserStatus] = useState<DomainParserStatusResponse | null>(null)
  const [parserLoading, setParserLoading] = useState(false)
  const [parserResultsMap, setParserResultsMap] = useState<Map<string, DomainParserResult>>(new Map())
  const [parserUpdatedAtMap, setParserUpdatedAtMap] = useState<Map<string, string>>(new Map())
  const [blacklistedRoots, setBlacklistedRoots] = useState<Set<string>>(new Set())

  // Learning state
  const [learningLoading, setLearningLoading] = useState(false)
  const [learnedItems, setLearnedItems] = useState<LearnedItem[]>([])
  const [learningStats, setLearningStats] = useState<LearningStatistics | null>(null)

  const [manualLearnDialogOpen, setManualLearnDialogOpen] = useState(false)
  const [manualLearnDomain, setManualLearnDomain] = useState("")
  const [manualLearnInn, setManualLearnInn] = useState("")
  const [manualLearnSourceUrl, setManualLearnSourceUrl] = useState("")
  const [manualLearnSourceUrlsText, setManualLearnSourceUrlsText] = useState("")
  const [manualLearnSubmitting, setManualLearnSubmitting] = useState(false)
  const [manualLearnInnDisabled, setManualLearnInnDisabled] = useState(false)

  const [expandedCheckedUrls, setExpandedCheckedUrls] = useState<Record<string, boolean>>({})

  const [historyDialogOpen, setHistoryDialogOpen] = useState(false)
  const [historyDomain, setHistoryDomain] = useState("")

  // Worker pause/resume state
  const [workerPaused, setWorkerPaused] = useState(false)
  const [workerToggling, setWorkerToggling] = useState(false)
  const [workerCurrentRun, setWorkerCurrentRun] = useState<DomainParserWorkerStatus["currentRun"]>(null)

  const suppliersByDomainRef = useRef<Map<string, SupplierDTO>>(new Map())
  const parserAutofillDoneRef = useRef<Set<string>>(new Set())
  const parserAutoSaveProcessedRef = useRef<boolean>(false)

  // Функция для определения источников URL на основе parsing_logs и source из БД
  // Используем parsing_logs как основной источник, но fallback на source из БД
  const getUrlSources = (url: string, urlSource?: string | null): string[] => {
    const normalizedUrl = normalizeUrl(url)
    const sources: string[] = []

    // Используем parsing_logs как основной источник информации
    if (parsingLogs) {
      // Проверяем Google
      if (parsingLogs.google?.last_links) {
        const foundInGoogle = parsingLogs.google.last_links.some((link) => normalizeUrl(link) === normalizedUrl)
        if (foundInGoogle) {
          sources.push("google")
        }
      }

      // Проверяем Yandex
      if (parsingLogs.yandex?.last_links) {
        const foundInYandex = parsingLogs.yandex.last_links.some((link) => normalizeUrl(link) === normalizedUrl)
        if (foundInYandex) {
          sources.push("yandex")
        }
      }
    }

    // Fallback: если не нашли в parsing_logs, используем source из domains_queue
    // Это важно, так как parsing_logs может содержать не все URL
    if (sources.length === 0 && urlSource) {
      if (urlSource === "both") {
        sources.push("google", "yandex")
      } else if (urlSource === "google") {
        sources.push("google")
      } else if (urlSource === "yandex") {
        sources.push("yandex")
      }
    }

    return sources
  }

  useEffect(() => {
    if (runId) {
      loadData()
    }
  }, [runId, refreshKey]) // Добавляем refreshKey для принудительной перезагрузки

  // Fetch worker pause/resume status on mount and poll every 10s
  useEffect(() => {
    let cancelled = false
    const fetchWorkerStatus = async () => {
      try {
        const ws = await getDomainParserWorkerStatus()
        if (!cancelled) {
          setWorkerPaused(ws.paused)
          setWorkerCurrentRun(ws.currentRun)
        }
      } catch {
        // ignore
      }
    }
    fetchWorkerStatus()
    const interval = setInterval(fetchWorkerStatus, 10_000)
    return () => { cancelled = true; clearInterval(interval) }
  }, [])

  const handleToggleWorkerPause = async () => {
    setWorkerToggling(true)
    try {
      if (workerPaused) {
        const res = await resumeDomainParserWorker()
        setWorkerPaused(res.paused)
        toast.success("Извлечение ИНН/email возобновлено")
      } else {
        const res = await pauseDomainParserWorker()
        setWorkerPaused(res.paused)
        toast.info("Извлечение ИНН/email остановлено. Текущий домен будет завершён.")
      }
    } catch (error) {
      toast.error("Ошибка управления воркером")
      console.error(error)
    } finally {
      setWorkerToggling(false)
    }
  }

  // Old INN extraction cache removed - using Domain Parser now

  useEffect(() => {
    if (!runId) return
    try {
      const parserCached = localStorage.getItem(`parser-results-${runId}`)
      if (parserCached) {
        const cachedMap = new Map<string, DomainParserResult>(JSON.parse(parserCached))
        setParserResultsMap(cachedMap)
      }
      const cachedParserRunId = localStorage.getItem(`parser-run-${runId}`)
      if (cachedParserRunId) {
        setParserRunId(cachedParserRunId)
      }
      const cachedUpdated = localStorage.getItem(`parser-updated-${runId}`)
      if (cachedUpdated) {
        const cachedMap = new Map<string, string>(JSON.parse(cachedUpdated))
        setParserUpdatedAtMap(cachedMap)
      }
    } catch (error) {
      // ignore
    }
  }, [runId])

  // Old INN extraction localStorage save removed - using Domain Parser now

  useEffect(() => {
    if (!runId || parserResultsMap.size === 0) return
    try {
      const serialized = JSON.stringify(Array.from(parserResultsMap.entries()))
      localStorage.setItem(`parser-results-${runId}`, serialized)
    } catch {
      // ignore
    }
  }, [parserResultsMap, runId])

  useEffect(() => {
    if (!runId || parserUpdatedAtMap.size === 0) return
    try {
      const serialized = JSON.stringify(Array.from(parserUpdatedAtMap.entries()))
      localStorage.setItem(`parser-updated-${runId}`, serialized)
    } catch {
      // ignore
    }
  }, [parserUpdatedAtMap, runId])

  useEffect(() => {
    if (!runId || !parserRunId) return
    try {
      localStorage.setItem(`parser-run-${runId}`, parserRunId)
    } catch {
      // ignore
    }
  }, [parserRunId, runId])

  // React Query: Domain Parser status polling (replaces manual setTimeout)
  const { data: rqParserStatus } = useDomainParserStatus(parserRunId ?? "", !!parserRunId)

  // Sync React Query data → local state
  useEffect(() => {
    if (!rqParserStatus) return
    setParserStatus(rqParserStatus)
    if (rqParserStatus.results && rqParserStatus.results.length > 0) {
      setParserResultsMap((prev) => {
        const next = new Map(prev)
        for (const r of rqParserStatus.results) {
          const domain = String(r.domain || "").trim()
          if (!domain) continue
          next.set(domain, r)
          next.set(extractRootDomain(domain).toLowerCase(), r)
        }
        return next
      })

      setParserUpdatedAtMap((prev) => {
        const next = new Map(prev)
        const now = new Date().toISOString()
        for (const r of rqParserStatus.results) {
          const domain = String(r.domain || "").trim()
          if (!domain) continue
          next.set(extractRootDomain(domain).toLowerCase(), now)
        }
        return next
      })
    }
  }, [rqParserStatus])

  useEffect(() => {
    if (!parserResultsMap || parserResultsMap.size === 0) return
    setGroups((prev) =>
      prev.map((g) => {
        const pr =
          parserResultsMap.get(g.domain) ||
          parserResultsMap.get(extractRootDomain(g.domain).toLowerCase()) ||
          parserResultsMap.get(g.domain.toLowerCase())
        if (!pr) return g
        return {
          ...g,
          extractionLog: (pr as any)?.extractionLog || (g as any).extractionLog,
          inn: (pr as any)?.inn ?? (g as any).inn ?? null,
          emails: (pr as any)?.emails ?? (g as any).emails ?? [],
          sourceUrls: (pr as any)?.sourceUrls ?? (g as any).sourceUrls ?? [],
        }
      }),
    )
  }, [parserResultsMap, parserUpdatedAtMap])

  useEffect(() => {
    if (!parserStatus?.results?.length) return
    const moderationRoots = new Set<string>()
    for (const r of parserStatus.results) {
      const root = extractRootDomain(String(r.domain || "")).toLowerCase()
      if (!root) continue
      const reason = String((r as any).reason || "")
      const hasData = Boolean(r.inn) || Boolean(r.emails && r.emails.length > 0)
      if (!hasData && reason !== "supplier_exists") {
        moderationRoots.add(root)
      }
    }
    if (moderationRoots.size === 0) return
    setGroups((prev) =>
      prev.map((group) => {
        if (group.supplierType === "supplier" || group.supplierType === "reseller") return group
        const root = extractRootDomain(group.domain).toLowerCase()
        if (!moderationRoots.has(root)) return group
        return { ...group, supplierType: "needs_moderation" }
      }),
    )
  }, [parserStatus])

  useEffect(() => {
    if (!runId || !parserRunId) return
    try {
      localStorage.setItem(`parser-run-${runId}`, parserRunId)
    } catch {
      // ignore
    }
  }, [parserRunId, runId])

  // (Domain Parser status polling handled by useDomainParserStatus above)

  // Автоматическое сохранение доменов с ИНН+email после Domain Parser
  // С ЗАЩИТОЙ ОТ ДУБЛИКАТОВ через проверку существования по домену
  useEffect(() => {
    if (!runId || !parserRunId || !parserStatus) return
    if (parserStatus.status !== "completed") return
    if (!parserResultsMap || parserResultsMap.size === 0) return

    // Проверяем, не обработали ли мы уже этот parserRunId
    if (parserAutoSaveProcessedRef.current) {
      console.log("[Domain Parser AutoSave] Already processed, skipping")
      return
    }

    // Автоматически сохраняем домены с ИНН и Email
    const autoSaveDomains = async () => {
      console.log("[Domain Parser AutoSave] Starting auto-save for domains with INN+Email")

      // КРИТИЧНО: Загружаем актуальный список поставщиков из БД перед началом
      let currentSuppliers: Map<string, SupplierDTO>
      try {
        const { suppliers } = await getSuppliers({ limit: 1000 })

        // Устанавливаем флаг ТОЛЬКО после успешной загрузки поставщиков,
        // иначе 401/403 (разлогин) заблокирует автосейв навсегда.
        parserAutoSaveProcessedRef.current = true

        currentSuppliers = new Map()
        for (const s of suppliers) {
          if (s.domain) {
            currentSuppliers.set(s.domain.toLowerCase(), s)
          }
        }
        console.log(`[Domain Parser AutoSave] Loaded ${currentSuppliers.size} existing suppliers from DB`)
      } catch (e) {
        if (e instanceof APIError && (e.status === 401 || e.status === 403)) {
          // Не считаем ошибкой: пользователь разлогинен/сессия истекла.
          // Сбрасываем флаг, чтобы после повторного логина автосейв мог выполниться.
          parserAutoSaveProcessedRef.current = false
          console.warn("[Domain Parser AutoSave] Not authenticated, skipping auto-save")
          return
        }
        console.error("[Domain Parser AutoSave] Failed to load suppliers, aborting:", e)
        toast.error("Ошибка загрузки списка поставщиков")
        return
      }

      let savedCount = 0
      let skippedCount = 0

      for (const [domain, result] of parserResultsMap.entries()) {
        // Пропускаем домены с ошибками или без ИНН
        if (result.error || !result.inn || !result.emails || result.emails.length === 0) {
          console.log(`[Domain Parser AutoSave] Skipping ${domain}: missing INN or email`)
          skippedCount++
          continue
        }

        const rootDomain = extractRootDomain(domain).toLowerCase()

        // КРИТИЧНО: Проверяем существование в актуальном списке из БД
        const existing = currentSuppliers.get(rootDomain)

        if (existing) {
          console.log(`[Domain Parser AutoSave] Skipping ${domain}: already exists as supplier (ID: ${existing.id})`)
          skippedCount++
          continue
        }

        const inn = result.inn
        const email = result.emails && result.emails.length > 0 ? result.emails[0] : null

        console.log(`[Domain Parser AutoSave] Auto-saving ${domain}: INN=${inn}, Email=${email || "-"}`)

        try {
          // ОБЯЗАТЕЛЬНО загружаем данные из Checko
          let checko: any = null
          try {
            console.log(`[Domain Parser AutoSave] Fetching Checko data for INN: ${inn}`)
            checko = await getCheckoData(inn, false)
            console.log(`[Domain Parser AutoSave] Checko data received:`, checko ? "success" : "null")
          } catch (e) {
            console.error(`[Domain Parser AutoSave] Failed to fetch Checko data:`, e)
            // Продолжаем без Checko данных
          }

          const baseName = (checko?.name && String(checko.name).trim()) || rootDomain

          // Создаем поставщика сразу со всеми данными из Checko
          const supplierData: any = {
            name: baseName,
            inn,
            email,
            domain: rootDomain,
            emails: email ? [email] : null,
            domains: rootDomain ? [rootDomain] : null,
            type: "supplier",
          }

          // Добавляем данные из Checko если есть
          if (checko) {
            supplierData.ogrn = checko.ogrn || null
            supplierData.kpp = checko.kpp || null
            supplierData.okpo = checko.okpo || null
            // Обрезаем до лимитов БД
            supplierData.companyStatus = checko.companyStatus ? checko.companyStatus.substring(0, 50) : null
            supplierData.registrationDate = checko.registrationDate || null
            supplierData.legalAddress = checko.legalAddress || null
            supplierData.address = checko.legalAddress || null
            supplierData.phone = checko.phone ? checko.phone.substring(0, 50) : null
            supplierData.website = checko.website || null
            supplierData.vk = checko.vk || null
            supplierData.telegram = checko.telegram || null
            // Числовые поля:确保传递 number | null
            supplierData.authorizedCapital =
              checko.authorizedCapital !== undefined && checko.authorizedCapital !== null
                ? Number(checko.authorizedCapital)
                : null
            supplierData.revenue =
              checko.revenue !== undefined && checko.revenue !== null ? Number(checko.revenue) : null
            supplierData.profit = checko.profit !== undefined && checko.profit !== null ? Number(checko.profit) : null
            supplierData.financeYear =
              checko.financeYear !== undefined && checko.financeYear !== null ? Number(checko.financeYear) : null
            supplierData.legalCasesCount =
              checko.legalCasesCount !== undefined && checko.legalCasesCount !== null
                ? Number(checko.legalCasesCount)
                : null
            supplierData.legalCasesSum =
              checko.legalCasesSum !== undefined && checko.legalCasesSum !== null ? Number(checko.legalCasesSum) : null
            supplierData.legalCasesAsPlaintiff =
              checko.legalCasesAsPlaintiff !== undefined && checko.legalCasesAsPlaintiff !== null
                ? Number(checko.legalCasesAsPlaintiff)
                : null
            supplierData.legalCasesAsDefendant =
              checko.legalCasesAsDefendant !== undefined && checko.legalCasesAsDefendant !== null
                ? Number(checko.legalCasesAsDefendant)
                : null
            supplierData.checkoData = checko.checkoData || null
            supplierData.dataStatus = "complete"
          } else {
            supplierData.dataStatus = "needs_checko"
          }

          const saved = await createSupplier(supplierData)

          console.log(`[Domain Parser AutoSave] Created supplier with Checko data:`, saved)

          // Добавляем в локальный список чтобы избежать повторного создания
          currentSuppliers.set(rootDomain, saved)

          toast.success(`✅ ${domain}: сохранен как поставщик`)
          savedCount++

          // Небольшая пауза между сохранениями
          await new Promise((resolve) => setTimeout(resolve, 500))
        } catch (error: any) {
          // Handle 409 Conflict (INN already exists) gracefully
          const status = error?.status || error?.response?.status
          const msg = String(error?.message || error || "")
          if (status === 409 || msg.includes("409") || msg.includes("conflict") || msg.includes("inn_conflict")) {
            console.log(`[Domain Parser AutoSave] Skipping ${domain}: INN already exists in DB (409 conflict)`)
            skippedCount++
            // Extract existing supplier ID from error if available
            try {
              const detail = JSON.parse(msg.match(/\{[\s\S]*\}/)?.[0] || "{}")
              const existingId = detail?.existingSupplierId || detail?.detail?.existingSupplierId
              if (existingId) {
                currentSuppliers.set(rootDomain, { id: existingId } as any)
              }
            } catch { /* ignore parse errors */ }
          } else {
            console.error(`[Domain Parser AutoSave] Error saving ${domain}:`, error)
            toast.error(`Ошибка сохранения ${domain}`)
          }
        }
      }

      console.log(`[Domain Parser AutoSave] Completed: saved=${savedCount}, skipped=${skippedCount}`)

      // Перезагружаем список поставщиков
      if (savedCount > 0) {
        try {
          const { suppliers } = await getSuppliers({ limit: 1000 })
          const newMap = new Map<string, SupplierDTO>()
          for (const s of suppliers) {
            if (s.domain) {
              newMap.set(s.domain.toLowerCase(), s)
            }
          }
          suppliersByDomainRef.current = newMap
          invalidateSuppliersCache()
          console.log("[Domain Parser AutoSave] Suppliers list refreshed")
          toast.success(`Автосохранение завершено: ${savedCount} новых поставщиков`)
        } catch (e) {
          console.error("[Domain Parser AutoSave] Failed to refresh suppliers:", e)
        }
      }
    }

    autoSaveDomains()
  }, [runId, parserRunId, parserStatus, parserResultsMap])

  // Загрузка логов парсера (один раз при загрузке run, даже если парсинг завершен)
  useEffect(() => {
    if (!runId || !run) return

    const fetchLogs = async () => {
      try {
        const logsData = await getParsingLogs(runId)
        if (logsData.parsing_logs && Object.keys(logsData.parsing_logs).length > 0) {
          setParsingLogs(logsData.parsing_logs)
        } else {
          // Если логов нет, очищаем состояние (на случай, если они были удалены)
          setParsingLogs(null)
        }
      } catch (error: unknown) {
        // Игнорируем ошибки 404, если run еще не создан в БД или логов еще нет
        // Это нормальная ситуация сразу после запуска парсинга
        if (error instanceof APIError && error.status === 404) {
          // Run не найден - это может быть временная ситуация, не показываем ошибку
          // Просто возвращаемся, не логируя ошибку
          return
        }
        // Для других ошибок используем debug, чтобы не засорять консоль
        // Но не показываем их как ошибки, так как это может быть временная ситуация
        console.debug("Could not fetch parsing logs:", error)
      }
    }

    // Загружаем логи один раз при загрузке run (для завершенных парсингов)
    // И при изменении статуса (когда парсинг завершается)
    fetchLogs()
  }, [runId, run])

  // React Query: Parsing logs polling (replaces manual setTimeout)
  const isRunning = run?.status === "running" || run?.status === "starting"
  const { data: rqLogsData } = useParsingLogsQuery(runId ?? "", isRunning)

  // Sync React Query logs data → local state
  useEffect(() => {
    if (!rqLogsData) return
    const logs = (rqLogsData as any).parsing_logs
    if (logs && Object.keys(logs).length > 0) {
      setParsingLogs(logs)
    }
  }, [rqLogsData])

  async function loadData() {
    if (!runId) return
    setLoading(true)
    try {
      const [suppliersData, blacklistData, runData, domainsData, logsData, moderationData] = await Promise.all([
        getSuppliers({ limit: 1000 }),
        getBlacklist({ limit: 1000 }),
        getParsingRun(runId),
        getDomainsQueue({ parsingRunId: runId, limit: 1000 }),
        getParsingLogs(runId).catch(() => ({ parsing_logs: {} })),
        getDomainModerationDomains(10000).catch(() => ({ domains: [], total: 0 })),
      ])

      setCachedSuppliers((suppliersData as any).suppliers)
      setCachedBlacklist((blacklistData as any).entries)

      try {
        const nextMap = new Map<string, SupplierDTO>()
        for (const s of (suppliersData as any).suppliers || []) {
          if ((s as any)?.domain) {
            const root = extractRootDomain(String((s as any).domain)).toLowerCase()
            nextMap.set(root, s as SupplierDTO)
          }
        }
        suppliersByDomainRef.current = nextMap
      } catch {
        // ignore
      }

      setRun(runData)

      // Restore Domain Parser results from process_log
      let restoredParserMap: Map<string, DomainParserResult> | null = null
      try {
        const hasLocalParserRun = !!localStorage.getItem(`parser-run-${runId}`)
        // Treat empty/invalid cache as missing so refresh can restore persisted results
        const hasLocalParserResults = (() => {
          try {
            const raw = localStorage.getItem(`parser-results-${runId}`)
            if (!raw) return false
            const parsed = JSON.parse(raw)
            return Array.isArray(parsed) && parsed.length > 0
          } catch {
            return false
          }
        })()

        // Read localStorage directly into restoredParserMap so groups get data immediately
        // (React state from useEffect may not have updated yet when loadData runs)
        if (hasLocalParserResults) {
          try {
            const raw = localStorage.getItem(`parser-results-${runId}`)
            if (raw) {
              const parsed = JSON.parse(raw)
              if (Array.isArray(parsed) && parsed.length > 0) {
                const map = new Map<string, DomainParserResult>(parsed)
                restoredParserMap = map
              }
            }
          } catch { /* ignore */ }
        }
        const pl: any = (runData as any)?.processLog || (runData as any)?.process_log
        const dpAuto: any = pl?.domain_parser_auto
        const runs: any = pl?.domain_parser?.runs

        // Prefer latest batch run that actually contains results (this is the persisted source of truth).
        // Auto worker parserRunId may point to a different in-memory run with empty results.
        try {
          if (runs && typeof runs === "object") {
            const ids = Object.keys(runs).sort()
            let bestId: string | null = null
            for (let i = ids.length - 1; i >= 0; i--) {
              const id = ids[i]
              const r = runs[id]
              const hasResults = Array.isArray(r?.results) && r.results.length > 0
              const hasProcessed = Number(r?.processed || 0) > 0
              if (hasResults || hasProcessed) {
                bestId = id
                break
              }
            }

            if (bestId) {
              setParserRunId(bestId)
              const best = runs[bestId]
              if (!hasLocalParserResults && Array.isArray(best?.results)) {
                const map = new Map<string, DomainParserResult>()
                for (const rr of best.results) {
                  if (rr?.domain) {
                    const domain = String(rr.domain)
                    map.set(domain, rr as DomainParserResult)
                    map.set(extractRootDomain(domain).toLowerCase(), rr as DomainParserResult)
                  }
                }
                restoredParserMap = map
                setParserResultsMap(map)
                setParserStatus({
                  runId,
                  parserRunId: bestId,
                  status: (best.status || "completed") as any,
                  processed: Number(best.processed || map.size),
                  total: Number(best.total || map.size),
                  currentDomain: null,
                  currentSourceUrls: [],
                  results: Array.from(map.values()),
                })
              }
            }
          }
        } catch {
          // ignore
        }

        // Fallback: pick auto parserRunId from process_log when available.
        if (dpAuto?.parserRunId) {
          const fromLog = String(dpAuto.parserRunId)
          setParserRunId((prev) => (prev ? prev : fromLog))
        }
        // Show at least synthetic live status from process_log even before first parser result appears.
        if (dpAuto && dpAuto.parserRunId) {
          setParserStatus((prev) => {
            if (prev && prev.parserRunId === String(dpAuto.parserRunId) && prev.results && prev.results.length > 0) {
              return prev
            }
            return {
              runId,
              parserRunId: String(dpAuto.parserRunId),
              status: (String(dpAuto.status || "running") as any),
              processed: Number(dpAuto.processed || 0),
              total: Number(dpAuto.total || dpAuto.domains || 0),
              currentDomain: dpAuto.lastDomain ? String(dpAuto.lastDomain) : null,
              currentSourceUrls: [],
              results: prev?.results || [],
            }
          })
        }

        // Legacy/batch restore: process_log.domain_parser.runs[parserRunId].results
        if ((!hasLocalParserRun || !hasLocalParserResults) && runs && typeof runs === "object") {
          const ids = Object.keys(runs).sort()
          const latestId = ids[ids.length - 1]
          const latest = latestId ? runs[latestId] : null
          if (latestId && latest && Array.isArray(latest.results)) {
            if (!hasLocalParserRun) {
              setParserRunId(latestId)
            }
            if (!hasLocalParserResults) {
              const map = new Map<string, DomainParserResult>()
              for (const r of latest.results) {
                if (r?.domain) {
                  const domain = String(r.domain)
                  map.set(domain, r as DomainParserResult)
                  map.set(extractRootDomain(domain).toLowerCase(), r as DomainParserResult)
                }
              }
              restoredParserMap = map
              setParserResultsMap(map)
              setParserStatus({
                runId,
                parserRunId: latestId,
                status: (latest.status || "completed") as any,
                processed: Number(latest.processed || map.size),
                total: Number(latest.total || map.size),
                currentDomain: null,
                currentSourceUrls: [],
                results: Array.from(map.values()),
              })
            }
          }
        }
      } catch {
        // ignore restore errors
      }

      // Загружаем логи сразу при загрузке данных (даже если парсинг завершен)
      if (logsData.parsing_logs && Object.keys(logsData.parsing_logs).length > 0) {
        setParsingLogs(logsData.parsing_logs)
      }

      // Нормализуем домены для справочной маркировки/фильтрации в UI.
      // Важно: не выкидываем их заранее, иначе при статусе "Все" список может стать пустым
      // при ненулевом resultsCount.
      const blacklistedDomains = new Set<string>(((blacklistData as any).entries || []).map((e: any) => extractRootDomain(String(e.domain || "")).toLowerCase()))
      setBlacklistedRoots(blacklistedDomains)
      const supplierDomains = new Set<string>()
      ;((suppliersData as any).suppliers || []).forEach((supplier: any) => {
        if (supplier.domain) {
          supplierDomains.add(extractRootDomain(supplier.domain).toLowerCase())
        }
        if (Array.isArray(supplier.domains)) {
          supplier.domains.forEach((d: string) => {
            if (d) supplierDomains.add(extractRootDomain(d).toLowerCase())
          })
        }
      })
      const normalizedEntries = domainsData.entries.map((entry) => ({
        ...entry,
        createdAt: entry.createdAt || (entry as { created_at?: string | null }).created_at || entry.createdAt,
      }))

      const filtered = normalizedEntries.filter((entry) => {
        const d = extractRootDomain(entry.domain).toLowerCase()
        return !blacklistedDomains.has(d)
      })
      const moderationDomains = new Set(
        ((moderationData as any)?.domains || []).map((d: string) => extractRootDomain(String(d)).toLowerCase()),
      )

      // Создать Map для быстрого поиска поставщиков по домену
      // ВАЖНО: Используем toLowerCase для обоих доменов для корректного сопоставления
      const suppliersMap = new Map<string, { type: "supplier" | "reseller"; id: number; hasChecko: boolean }>()
      ;((suppliersData as any).suppliers || []).forEach((supplier: any) => {
        const s: any = supplier as any
        const hasChecko = Boolean(
          s.dataStatus === "complete" ||
          s.data_status === "complete" ||
          s.checkoData ||
          s.checko_data ||
          s.ogrn ||
          s.kpp ||
          s.okpo ||
          s.companyStatus ||
          s.company_status ||
          s.registrationDate ||
          s.registration_date ||
          s.legalAddress ||
          s.legal_address
        )
        if (supplier.domain) {
          const rootDomain = extractRootDomain(supplier.domain).toLowerCase()
          suppliersMap.set(rootDomain, { type: supplier.type, id: supplier.id, hasChecko })
        }
        if (Array.isArray(supplier.domains)) {
          for (const d of supplier.domains) {
            if (!d) continue
            const rootDomain = extractRootDomain(String(d)).toLowerCase()
            suppliersMap.set(rootDomain, { type: supplier.type, id: supplier.id, hasChecko })
          }
        }
      })

      // Группировка с добавлением информации о поставщиках и источниках
      // Используем parsing_logs для точного определения источников каждого домена
      const parsingLogsForSources =
        logsData.parsing_logs && Object.keys(logsData.parsing_logs).length > 0 ? logsData.parsing_logs : null

      let grouped = groupByDomain(filtered).map((group) => {
        const groupDomainLower = group.domain.toLowerCase()
        const supplierInfo = suppliersMap.get(groupDomainLower)
        const parserMapForGrouping = restoredParserMap || parserResultsMap
        const parserResult = parserMapForGrouping.get(group.domain) || parserMapForGrouping.get(extractRootDomain(group.domain).toLowerCase())
        const needsModeration = Boolean(
          !supplierInfo && moderationDomains.has(groupDomainLower),
        )
        const nextSupplierType: "supplier" | "reseller" | "needs_moderation" | null = supplierInfo
          ? (supplierInfo.type as "supplier" | "reseller")
          : needsModeration
            ? "needs_moderation"
            : null

        // Вычисляем источники для домена на основе всех его URL используя parsing_logs
        const sources = collectDomainSources(group.urls, parsingLogsForSources)

        const parserUpdatedAt = parserUpdatedAtMap.get(groupDomainLower)
        const lastUpdate = (parserUpdatedAt || getLatestUrlCreatedAt(group.urls)) || undefined

        return {
          ...group,
          supplierType: nextSupplierType,
          supplierId: supplierInfo?.id || null, // ID поставщика для редактирования
          hasChecko: supplierInfo?.hasChecko || parserResult?.dataStatus === "complete",
          sources: sources, // Источники, которые нашли этот домен
          lastUpdate,
          extractionLog: (parserResult as any)?.extractionLog,
          inn: (parserResult as any)?.inn ?? null,
          emails: (parserResult as any)?.emails ?? [],
          sourceUrls: (parserResult as any)?.sourceUrls ?? [],
        }
      })

      // Сортировка
      grouped = grouped.sort((a, b) => {
        const byUrls = b.totalUrls - a.totalUrls
        if (byUrls !== 0) return byUrls
        return a.domain.localeCompare(b.domain)
      })

      setGroups(grouped)
    } catch (error) {
      toast.error("Ошибка загрузки данных")
      console.error("Error loading data:", error)
    } finally {
      setLoading(false)
    }
  }

  function openManualLearnDialog(domain: string, inn?: string) {
    setManualLearnDomain(domain)
    setManualLearnInn(inn || "")
    setManualLearnSourceUrl("")
    setManualLearnSourceUrlsText("")
    setManualLearnInnDisabled(Boolean(inn))
    setManualLearnDialogOpen(true)
  }

  const handleManualLearnSubmit = async () => {
    if (!runId) {
      toast.error("runId не найден")
      return
    }
    if (!manualLearnDomain || !manualLearnInn) {
      toast.error("Не указан домен или ИНН")
      return
    }
    const sourceUrls = manualLearnSourceUrlsText
      .split(/\r?\n/)
      .map((s) => s.trim())
      .filter(Boolean)
    if (!manualLearnSourceUrl.trim() && sourceUrls.length === 0) {
      toast.error("Укажите ссылку, где найден ИНН")
      return
    }

    setManualLearnSubmitting(true)
    try {
      const learningSessionId = `manual_learning_${Date.now()}`
      const response = await learnManualInn(
        runId,
        manualLearnDomain,
        manualLearnInn,
        manualLearnSourceUrl.trim(),
        learningSessionId,
        sourceUrls,
      )

      if (response.learnedItems.length > 0 || (response.statistics?.totalLearned || 0) > 0) {
        setLearnedItems((prev) => [...response.learnedItems, ...prev])
        setLearningStats(response.statistics)
        const learnedCount = response.learnedItems.length || 1
        toast.success(`🎓 Обучение сохранено: ${learnedCount} паттернов`)
      } else {
        toast.info("Нечему учиться по этой ссылке")
      }

      setManualLearnDialogOpen(false)
    } catch (error) {
      console.error("[Manual Learning] Error:", error)
      if (error instanceof APIError) {
        toast.error(`Ошибка обучения: ${error.message}`)
      } else {
        toast.error(error instanceof Error ? error.message : "Ошибка обучения парсера")
      }
    } finally {
      setManualLearnSubmitting(false)
    }
  }

  function openBlacklistDialog(domain: string) {
    setBlacklistDomain(domain)
    setBlacklistReason("")
    setBlacklistDialogOpen(true)
  }

  function hideDomainEverywhere(domain: string) {
    const normalizedRoot = extractRootDomain(domain).toLowerCase()
    if (!normalizedRoot) return
    setBlacklistedRoots((prev) => new Set(prev).add(normalizedRoot))
    setGroups((prev) => prev.filter((g) => extractRootDomain(g.domain).toLowerCase() !== normalizedRoot))
    setParserResultsMap((prev) => {
      const next = new Map(prev)
      for (const key of Array.from(next.keys())) {
        if (extractRootDomain(String(key)).toLowerCase() === normalizedRoot) {
          next.delete(key)
        }
      }
      return next
    })
    setParserStatus((prev) => {
      if (!prev?.results?.length) return prev
      const results = prev.results.filter(
        (r) => extractRootDomain(String(r.domain || "")).toLowerCase() !== normalizedRoot,
      )
      return { ...prev, results }
    })
    setSelectedDomains((prev) => {
      const next = new Set(prev)
      for (const d of Array.from(next)) {
        if (extractRootDomain(d).toLowerCase() === normalizedRoot) {
          next.delete(d)
        }
      }
      return next
    })
  }

  async function handleAddToBlacklist() {
    if (!blacklistDomain.trim()) {
      toast.error("Домен не указан")
      return
    }

    setAddingToBlacklist(true)
    try {
      // НОРМАЛИЗАЦИЯ: Используем extractRootDomain для нормализации домена
      // Это гарантирует, что домен будет добавлен в том же формате, что используется при фильтрации
      const normalizedDomain = extractRootDomain(blacklistDomain)
      await addToBlacklist({
        domain: normalizedDomain,
        parsingRunId: runId || undefined,
        reason: blacklistReason.trim() || null,
      })
      // Optimistic UI update: hide this domain immediately from current run view.
      hideDomainEverywhere(normalizedDomain)
      // Инвалидируем кэш blacklist ПЕРЕД перезагрузкой данных
      invalidateBlacklistCache()
      toast.success(`Домен "${normalizedDomain}" добавлен в blacklist`)
      // Закрываем модальное окно
      setBlacklistDialogOpen(false)
      setBlacklistDomain("")
      setBlacklistReason("")
      // Увеличиваем задержку, чтобы backend успел закоммитить изменения
      await new Promise((resolve) => setTimeout(resolve, 500))
      // Принудительно перезагружаем данные (await чтобы дождаться завершения)
      // Устанавливаем loading в true, чтобы показать индикатор загрузки
      setLoading(true)
      // Принудительно обновляем ключ для перезагрузки
      setRefreshKey((prev) => prev + 1)
      await loadData()
    } catch (error) {
      const normalizedDomain = extractRootDomain(blacklistDomain)
      const errorText = String((error as any)?.message || "").toLowerCase()
      const isAlreadyInBlacklist =
        error instanceof APIError &&
        (error.status === 400 || error.status === 409) &&
        (errorText.includes("already") || errorText.includes("уже") || errorText.includes("exists"))

      if (isAlreadyInBlacklist) {
        hideDomainEverywhere(normalizedDomain)
        invalidateBlacklistCache()
        toast.info(`Домен "${normalizedDomain}" уже в blacklist и скрыт из run`)
        setBlacklistDialogOpen(false)
        setBlacklistDomain("")
        setBlacklistReason("")
        await loadData()
      } else {
        toast.error("Ошибка добавления в blacklist")
        console.error("Error adding to blacklist:", error)
        setLoading(false)
      }
    } finally {
      setAddingToBlacklist(false)
    }
  }

  function openSupplierDialog(domain: string, type: "supplier" | "reseller", supplierId?: number | null) {
    setSelectedDomain(domain)
    setEditingSupplierId(supplierId || null)

    // Если редактируем существующего поставщика, загружаем его данные
    if (supplierId) {
      // Находим поставщика в кэше
      const cachedSuppliers = getCachedSuppliers()
      const supplier = cachedSuppliers?.find((s) => s.id === supplierId)
      if (supplier) {
        setSupplierForm({
          name: supplier.name || "",
          inn: supplier.inn || "",
          email: supplier.email || "",
          domain: supplier.domain || domain,
          address: supplier.address || "",
          type: supplier.type || type,
          // Checko fields
          ogrn: supplier.ogrn || "",
          kpp: supplier.kpp || "",
          okpo: supplier.okpo || "",
          companyStatus: supplier.companyStatus || "",
          registrationDate: supplier.registrationDate || "",
          legalAddress: supplier.legalAddress || "",
          phone: supplier.phone || "",
          website: supplier.website || "",
          vk: supplier.vk || "",
          telegram: supplier.telegram || "",
          authorizedCapital: supplier.authorizedCapital ?? null,
          revenue: supplier.revenue ?? null,
          profit: supplier.profit ?? null,
          financeYear: supplier.financeYear ?? null,
          legalCasesCount: supplier.legalCasesCount ?? null,
          legalCasesSum: supplier.legalCasesSum ?? null,
          legalCasesAsPlaintiff: supplier.legalCasesAsPlaintiff ?? null,
          legalCasesAsDefendant: supplier.legalCasesAsDefendant ?? null,
          checkoData: supplier.checkoData ?? null,
        })
      } else {
        setSupplierForm({
          name: "",
          inn: "",
          email: "",
          domain: domain,
          address: "",
          type: type,
          // Checko fields
          ogrn: "",
          kpp: "",
          okpo: "",
          companyStatus: "",
          registrationDate: "",
          legalAddress: "",
          phone: "",
          website: "",
          vk: "",
          telegram: "",
          authorizedCapital: null,
          revenue: null,
          profit: null,
          financeYear: null,
          legalCasesCount: null,
          legalCasesSum: null,
          legalCasesAsPlaintiff: null,
          legalCasesAsDefendant: null,
          checkoData: null,
        })
      }
    } else {
      // Для нового поставщика проверяем данные из Domain Parser
      const rootDomain = extractRootDomain(domain).toLowerCase()
      const parserResult = parserResultsMap.get(domain) || parserResultsMap.get(rootDomain)

      let prefillInn = ""
      let prefillEmail = ""

      if (parserResult && !parserResult.error) {
        prefillInn = parserResult.inn || ""
        prefillEmail = parserResult.emails && parserResult.emails.length > 0 ? parserResult.emails[0] : ""

        if (prefillInn || prefillEmail) {
          console.log(`[Domain Parser] Предзаполнение для ${domain}: INN=${prefillInn}, Email=${prefillEmail}`)
        }
      }

      setSupplierForm({
        name: "",
        inn: prefillInn,
        email: prefillEmail,
        domain: domain,
        address: "",
        type: type,
        // Checko fields
        ogrn: "",
        kpp: "",
        okpo: "",
        companyStatus: "",
        registrationDate: "",
        legalAddress: "",
        phone: "",
        website: "",
        vk: "",
        telegram: "",
        authorizedCapital: null,
        revenue: null,
        profit: null,
        financeYear: null,
        legalCasesCount: null,
        legalCasesSum: null,
        legalCasesAsPlaintiff: null,
        legalCasesAsDefendant: null,
        checkoData: null,
      })
    }
    setSupplierDialogOpen(true)
  }

  function openEditSupplierDialog(domain: string, supplierId: number, currentType: "supplier" | "reseller") {
    openSupplierDialog(domain, currentType, supplierId)
  }

  async function handleCreateSupplier() {
    if (!supplierForm.name.trim()) {
      toast.error("Укажите название")
      return
    }
    if (!supplierForm.inn || !/^\d{10,12}$/.test(supplierForm.inn)) {
      toast.error("ИНН обязателен (10 или 12 цифр)")
      return
    }
    if (!supplierForm.email || !/^[^\s@]+@[^\s@]+\.[^\s@]+$/.test(supplierForm.email)) {
      toast.error("Email обязателен")
      return
    }

    try {
      if (editingSupplierId) {
        // Обновляем существующего поставщика
        await updateSupplier(editingSupplierId, {
          name: supplierForm.name,
          inn: supplierForm.inn || null,
          email: supplierForm.email || null,
          domain: supplierForm.domain || null,
          emails: supplierForm.email ? [supplierForm.email] : null,
          domains: supplierForm.domain ? [supplierForm.domain] : null,
          address: supplierForm.address || null,
          type: supplierForm.type,
          // Checko fields
          ogrn: supplierForm.ogrn || null,
          kpp: supplierForm.kpp || null,
          okpo: supplierForm.okpo || null,
          // Обрезаем до лимитов БД
          companyStatus: supplierForm.companyStatus ? supplierForm.companyStatus.substring(0, 50) : null,
          registrationDate: supplierForm.registrationDate || null,
          legalAddress: supplierForm.legalAddress || null,
          phone: supplierForm.phone ? supplierForm.phone.substring(0, 50) : null,
          website: supplierForm.website || null,
          vk: supplierForm.vk || null,
          telegram: supplierForm.telegram || null,
          // Числовые поля:确保传递 number | null
          authorizedCapital: supplierForm.authorizedCapital !== undefined ? supplierForm.authorizedCapital : null,
          revenue: supplierForm.revenue !== undefined ? supplierForm.revenue : null,
          profit: supplierForm.profit !== undefined ? supplierForm.profit : null,
          financeYear: supplierForm.financeYear !== undefined ? supplierForm.financeYear : null,
          legalCasesCount: supplierForm.legalCasesCount !== undefined ? supplierForm.legalCasesCount : null,
          legalCasesSum: supplierForm.legalCasesSum !== undefined ? supplierForm.legalCasesSum : null,
          legalCasesAsPlaintiff:
            supplierForm.legalCasesAsPlaintiff !== undefined ? supplierForm.legalCasesAsPlaintiff : null,
          legalCasesAsDefendant:
            supplierForm.legalCasesAsDefendant !== undefined ? supplierForm.legalCasesAsDefendant : null,
          checkoData: supplierForm.checkoData,
        })
        toast.success(`${supplierForm.type === "supplier" ? "Поставщик" : "Реселлер"} обновлен`)
      } else {
        // Создаем нового поставщика
        await createSupplier({
          name: supplierForm.name,
          inn: supplierForm.inn || null,
          email: supplierForm.email || null,
          domain: supplierForm.domain || null,
          emails: supplierForm.email ? [supplierForm.email] : null,
          domains: supplierForm.domain ? [supplierForm.domain] : null,
          address: supplierForm.address || null,
          type: supplierForm.type,
          // Checko fields
          ogrn: supplierForm.ogrn || null,
          kpp: supplierForm.kpp || null,
          okpo: supplierForm.okpo || null,
          // Обрезаем до лимитов БД
          companyStatus: supplierForm.companyStatus ? supplierForm.companyStatus.substring(0, 50) : null,
          registrationDate: supplierForm.registrationDate || null,
          legalAddress: supplierForm.legalAddress || null,
          phone: supplierForm.phone ? supplierForm.phone.substring(0, 50) : null,
          website: supplierForm.website || null,
          vk: supplierForm.vk || null,
          telegram: supplierForm.telegram || null,
          // Числовые поля:确保传递 number | null
          authorizedCapital: supplierForm.authorizedCapital !== undefined ? supplierForm.authorizedCapital : null,
          revenue: supplierForm.revenue !== undefined ? supplierForm.revenue : null,
          profit: supplierForm.profit !== undefined ? supplierForm.profit : null,
          financeYear: supplierForm.financeYear !== undefined ? supplierForm.financeYear : null,
          legalCasesCount: supplierForm.legalCasesCount !== undefined ? supplierForm.legalCasesCount : null,
          legalCasesSum: supplierForm.legalCasesSum !== undefined ? supplierForm.legalCasesSum : null,
          legalCasesAsPlaintiff:
            supplierForm.legalCasesAsPlaintiff !== undefined ? supplierForm.legalCasesAsPlaintiff : null,
          legalCasesAsDefendant:
            supplierForm.legalCasesAsDefendant !== undefined ? supplierForm.legalCasesAsDefendant : null,
          checkoData: supplierForm.checkoData,
        })
        toast.success(`${supplierForm.type === "supplier" ? "Поставщик" : "Реселлер"} создан`)
      }
      // Инвалидируем кэш поставщиков
      invalidateSuppliersCache()
      setSupplierDialogOpen(false)
      setEditingSupplierId(null)
      // Обновить данные, чтобы сразу показать бейдж
      loadData()
    } catch (error: any) {
      if (error instanceof APIError && error.status === 409) {
        const detail = (error.data as any)?.detail
        if (detail?.code === "inn_conflict") {
          setInnConflict({
            existingSupplierId: Number(detail.existingSupplierId),
            existingSupplierName: detail.existingSupplierName,
            existingSupplierDomains: detail.existingSupplierDomains,
            existingSupplierEmails: detail.existingSupplierEmails,
          })
          return
        }
      }
      toast.error(editingSupplierId ? "Ошибка обновления" : "Ошибка создания")
      console.error("Error saving supplier:", error)
    }
  }

  if (loading) {
    return (
      <div className="min-h-screen bg-gradient-to-br from-background to-muted/30">
        <Navigation />
        <motion.main
          initial={{ opacity: 0 }}
          animate={{ opacity: 1 }}
          transition={{ duration: 0.5 }}
          className="container mx-auto px-0 py-6 max-w-none w-full"
        >
          <motion.div
            initial={{ opacity: 0, y: -20 }}
            animate={{ opacity: 1, y: 0 }}
            transition={{ duration: 0.5 }}
            className="text-center py-12"
          >
            <div className="h-16 w-16 rounded-full bg-purple-100 flex items-center justify-center mx-auto mb-4">
              <Clock className="h-8 w-8 text-purple-600 animate-pulse" />
            </div>
            <p className="text-lg text-muted-foreground">Загрузка деталей запуска...</p>
          </motion.div>
        </motion.main>
      </div>
    )
  }

  if (!run) {
    return (
      <div className="min-h-screen bg-gradient-to-br from-background to-muted/30">
        <Navigation />
        <motion.main
          initial={{ opacity: 0 }}
          animate={{ opacity: 1 }}
          transition={{ duration: 0.5 }}
          className="container mx-auto px-0 py-6 max-w-none w-full"
        >
          <motion.div
            initial={{ opacity: 0, y: -20 }}
            animate={{ opacity: 1, y: 0 }}
            transition={{ duration: 0.5 }}
            className="text-center py-12"
          >
            <div className="h-16 w-16 rounded-full bg-red-100 flex items-center justify-center mx-auto mb-4">
              <XCircle className="h-8 w-8 text-red-600" />
            </div>
            <p className="text-lg text-red-600">Запуск парсинга не найден</p>
            <motion.div whileHover={{ scale: 1.05 }} whileTap={{ scale: 0.95 }} className="mt-4">
              <Button
                onClick={() => router.push("/parsing-runs")}
                className="bg-gradient-to-r from-purple-600 to-indigo-600 hover:from-purple-700 hover:to-indigo-700 text-white"
              >
                Вернуться к списку
              </Button>
            </motion.div>
          </motion.div>
        </motion.main>
      </div>
    )
  }

  function getStatusBadge(status: string) {
    if (status === "completed")
      return (
        <Badge variant="default" className="text-lg px-4 py-1">
          Завершен
        </Badge>
      )
    if (status === "running")
      return (
        <Badge variant="outline" className="text-lg px-4 py-1">
          Выполняется
        </Badge>
      )
    return (
      <Badge variant="destructive" className="text-lg px-4 py-1">
        Ошибка
      </Badge>
    )
  }

  const displayRunId = run.runId || run.run_id || runId
  const keyword = run.keyword || "Unknown"
  const displayKeyword = (() => {
    const s = String(keyword || "").trim()
    if (!s) return ""
    return s.charAt(0).toUpperCase() + s.slice(1)
  })()
  const depth = run.depth || null
  const createdAt = run.startedAt || run.started_at || run.createdAt || run.created_at || ""
  const finishedAt = run.finishedAt || run.finished_at

  const formatDateShort = (dateString: string | null | undefined) => {
    try {
      if (!dateString) return ""
      const d = new Date(dateString)
      if (Number.isNaN(d.getTime())) return ""
      const dd = String(d.getDate()).padStart(2, "0")
      const mm = String(d.getMonth() + 1).padStart(2, "0")
      const yy = String(d.getFullYear()).slice(-2)
      const hh = String(d.getHours()).padStart(2, "0")
      const mi = String(d.getMinutes()).padStart(2, "0")
      return `${dd}.${mm}.${yy} ${hh}.${mi}`
    } catch {
      return ""
    }
  }

  const durationMinutes = (() => {
    try {
      const processLog: any = (run as any)?.processLog || (run as any)?.process_log
      const dsRaw = processLog?.duration_seconds
      if (dsRaw !== null && dsRaw !== undefined && !Number.isNaN(Number(dsRaw))) {
        const mins = Math.max(1, Math.round(Number(dsRaw) / 60))
        return mins
      }
      if (createdAt && finishedAt) {
        const a = new Date(createdAt)
        const b = new Date(String(finishedAt))
        if (!Number.isNaN(a.getTime()) && !Number.isNaN(b.getTime())) {
          const mins = Math.max(1, Math.round((b.getTime() - a.getTime()) / 60000))
          return mins
        }
      }
    } catch {
      return null
    }
    return null
  })()

  // Функция для форматирования дат
  const formatDate = (dateString: string | null | undefined) => {
    if (!dateString) return "—"
    try {
      const trimmed = dateString.trim()
      if (!trimmed) return "—"
      const normalized = trimmed.includes("T") ? trimmed : trimmed.replace(" ", "T")
      const hasTimezone = /[zZ]|[+-]\d{2}:?\d{2}$/.test(normalized)
      const date = new Date(hasTimezone ? normalized : normalized)
      return date.toLocaleString("ru-RU", {
        year: "numeric",
        month: "2-digit",
        day: "2-digit",
        hour: "2-digit",
        minute: "2-digit",
        second: "2-digit",
      })
    } catch (e) {
      return dateString
    }
  }

  // Функции для работы с выбранными доменами
  const toggleDomainSelection = async (domain: string) => {
    setSelectedDomains((prev) => {
      const newSet = new Set(prev)
      if (newSet.has(domain)) {
        newSet.delete(domain)
      } else {
        newSet.add(domain)
      }
      return newSet
    })
  }

  // OLD INN Extraction removed - now using Domain Parser with auto-trigger Comet workflow

  const selectAllDomains = () => {
    const filtered = groups.filter((group) => {
      if (searchQuery && !group.domain.toLowerCase().includes(searchQuery.toLowerCase())) return false
      if (filterStatus === "supplier" && group.supplierType !== "supplier") return false
      if (filterStatus === "reseller" && group.supplierType !== "reseller") return false
      if (filterStatus === "needs_moderation" && group.supplierType !== "needs_moderation") return false
      // 'new' filter removed
      return true
    })
    setSelectedDomains(new Set(filtered.map((g) => g.domain)))
  }

  const deselectAllDomains = () => {
    setSelectedDomains(new Set())
  }

  const copySelectedDomains = () => {
    const domainsArray = Array.from(selectedDomains)
    if (domainsArray.length === 0) {
      toast.error("Нет выбранных доменов")
      return
    }
    navigator.clipboard.writeText(domainsArray.join("\n"))
    toast.success(`Скопировано ${domainsArray.length} доменов`)
  }

  // Функция для запуска Domain Parser (получение данных)
  const handleDomainParser = async () => {
    if (selectedDomains.size === 0) {
      toast.error("Выберите хотя бы один домен")
      return
    }
    if (!runId) {
      toast.error("runId не найден")
      return
    }

    // Обновляем актуальный список поставщиков перед фильтрацией
    let currentSuppliers: Map<string, SupplierDTO> = suppliersByDomainRef.current
    try {
      const suppliersResult = await getSuppliers({ limit: 1000 })
      setCachedSuppliers(suppliersResult.suppliers)
      const refreshed = new Map<string, SupplierDTO>()
      for (const s of suppliersResult.suppliers) {
        if (s.domain) {
          refreshed.set(s.domain.toLowerCase(), s)
        }
      }
      suppliersByDomainRef.current = refreshed
      currentSuppliers = refreshed
    } catch {
      // fallback to cached map
    }

    // Фильтруем домены: только те, где НЕТ поставщика/реселлера и НЕТ ИНН
    const domainsArray = Array.from(selectedDomains)
    const parserMap = parserResultsMap as Map<string, DomainParserResult>

    const domainsWithoutInn = domainsArray.filter((domain) => {
      const rootDomain = extractRootDomain(domain).toLowerCase()
      const supplier: SupplierDTO | undefined = currentSuppliers.get(rootDomain)

      if (supplier) return false

      const parserResult: DomainParserResult | undefined =
        parserMap.get(domain) ?? parserMap.get(rootDomain)
      const parserInn = parserResult ? parserResult.inn : null
      const hasInn = Boolean(parserInn)

      return !hasInn
    })

    if (domainsWithoutInn.length === 0) {
      toast.info("Все выбранные домены уже имеют ИНН или отмечены как поставщики/реселлеры")
      return
    }

    console.log("[Domain Parser] Starting for domains:", domainsWithoutInn)
    setParserLoading(true)

    try {
      const hasModeration = domainsWithoutInn.some((d) => {
        const g = groups.find((gr: ParsingDomainGroup) => gr.domain === d)
        return g?.supplierType === "needs_moderation"
      })
      const resp = await startDomainParserBatch(runId, domainsWithoutInn, hasModeration)
      setParserRunId(resp.parserRunId)
      toast.success(`Парсер запущен для ${domainsWithoutInn.length} доменов${hasModeration ? " (форс-режим)" : ""}`)

      if (domainsArray.length > domainsWithoutInn.length) {
        const skipped = domainsArray.length - domainsWithoutInn.length
        toast.info(`Пропущено ${skipped} доменов (есть ИНН или статус поставщика/реселлера)`)
      }
    } catch (error) {
      console.error("[Domain Parser] Error:", error)
      if (error instanceof APIError) {
        toast.error(`Ошибка парсера: ${error.message}`)
      } else {
        toast.error(error instanceof Error ? error.message : "Ошибка запуска парсера")
      }
    } finally {
      setParserLoading(false)
    }
  }

  return (
    <div className="min-h-screen bg-gradient-to-br from-background to-muted/30">
      <Navigation />

      <motion.main
        initial={{ opacity: 0, y: 20 }}
        animate={{ opacity: 1, y: 0 }}
        transition={{ duration: 0.5 }}
        className="container mx-auto px-0 py-6 max-w-none w-full"
      >
        {/* Results Accordion */}
        <motion.div
          initial={{ opacity: 0, y: 20 }}
          animate={{ opacity: 1, y: 0 }}
          transition={{ duration: 0.7, delay: 0.4 }}
        >
          <Card className="card-hover bg-gradient-to-br from-white to-purple-50 border-purple-200 shadow-lg">
            <CardHeader className="border-b border-purple-100 p-6">
              <div className="flex items-start justify-between gap-4 mb-4">
                <motion.div initial={{ opacity: 0, x: -20 }} animate={{ opacity: 1, x: 0 }} transition={{ duration: 0.5, delay: 0.5 }}>
                  <CardTitle className="text-2xl text-gradient mb-1">{displayKeyword}</CardTitle>
                  <div className="flex items-center gap-3 text-sm text-muted-foreground flex-wrap">
                    {depth !== null && depth !== undefined && (
                      <div className="flex items-center gap-1">
                        <Layers className="h-4 w-4" />
                        <span>{depth}</span>
                      </div>
                    )}
                    {createdAt && (
                      <div className="flex items-center gap-1">
                        <Clock className="h-4 w-4" />
                        <span>Создано {formatDateShort(createdAt)}</span>
                      </div>
                    )}
                    {finishedAt && durationMinutes !== null && (
                      <div className="flex items-center gap-1">
                        <CheckCircle className="h-4 w-4" />
                        <span>Завершен за {durationMinutes} мин</span>
                      </div>
                    )}
                    {run.resultsCount !== null && run.resultsCount !== undefined && (
                      <div className="flex items-center gap-2">
                        <span className="text-2xl font-bold text-purple-600 leading-none">{run.resultsCount}</span>
                        <span className="text-sm text-muted-foreground">результатов</span>
                      </div>
                    )}
                  </div>

                  {parsingLogs && (parsingLogs.google || parsingLogs.yandex) && (
                    <div className="mt-2 flex items-center gap-2 flex-wrap">
                      {parsingLogs.google && (
                        <button
                          type="button"
                          onClick={() => {
                            setAccordionValue((prev) => (prev.includes("google") ? prev.filter((v) => v !== "google") : [...prev, "google"]))
                          }}
                          className="inline-flex items-center gap-2 px-2 py-1 rounded-md border border-blue-200 bg-blue-50 text-blue-700 hover:bg-blue-100 text-xs"
                          title="Google"
                        >
                          <span className="inline-flex items-center justify-center w-5 h-5 rounded-full bg-blue-600 text-white font-bold text-[10px]">G</span>
                          <span className="font-semibold">Google</span>
                          <span className="px-1.5 py-0.5 rounded border border-blue-200 bg-white/70">{parsingLogs.google.total_links} ссылок</span>
                          {parsingLogs.google.pages_processed > 0 && (
                            <span className="px-1.5 py-0.5 rounded border border-blue-200 bg-white/70">{parsingLogs.google.pages_processed} стр.</span>
                          )}
                        </button>
                      )}
                      {parsingLogs.yandex && (
                        <button
                          type="button"
                          onClick={() => {
                            setAccordionValue((prev) => (prev.includes("yandex") ? prev.filter((v) => v !== "yandex") : [...prev, "yandex"]))
                          }}
                          className="inline-flex items-center gap-2 px-2 py-1 rounded-md border border-red-200 bg-red-50 text-red-700 hover:bg-red-100 text-xs"
                          title="Яндекс"
                        >
                          <span className="inline-flex items-center justify-center w-5 h-5 rounded-full bg-red-600 text-white font-bold text-[10px]">Я</span>
                          <span className="font-semibold">Яндекс</span>
                          <span className="px-1.5 py-0.5 rounded border border-red-200 bg-white/70">{parsingLogs.yandex.total_links} ссылок</span>
                          {parsingLogs.yandex.pages_processed > 0 && (
                            <span className="px-1.5 py-0.5 rounded border border-red-200 bg-white/70">{parsingLogs.yandex.pages_processed} стр.</span>
                          )}
                        </button>
                      )}
                    </div>
                  )}
                </motion.div>
                <div className="flex flex-col items-end gap-2">
                  <motion.div initial={{ opacity: 0, scale: 0.8 }} animate={{ opacity: 1, scale: 1 }} transition={{ duration: 0.5, delay: 0.2 }}>
                    {getStatusBadge(run.status)}
                  </motion.div>

                  <motion.div
                    initial={{ opacity: 0, scale: 0.8 }}
                    animate={{ opacity: 1, scale: 1 }}
                    transition={{ duration: 0.3 }}
                    className="flex gap-2"
                  >
                    <motion.div whileHover={{ scale: 1.05 }} whileTap={{ scale: 0.95 }}>
                      <Button
                        size="sm"
                        variant="outline"
                        onClick={copySelectedDomains}
                        disabled={selectedDomains.size === 0}
                        className="h-8 text-xs border-purple-300 focus:border-purple-500 focus:ring-purple-500 text-purple-700 hover:bg-purple-50 bg-transparent"
                      >
                        <Copy className="h-3 w-3 mr-1" />
                        Копировать ({selectedDomains.size})
                      </Button>
                    </motion.div>
                    <motion.div whileHover={{ scale: 1.05 }} whileTap={{ scale: 0.95 }}>
                      <Button
                        size="sm"
                        onClick={handleDomainParser}
                        disabled={parserLoading || selectedDomains.size === 0}
                        className="h-8 text-xs bg-gradient-to-r from-blue-600 to-cyan-600 hover:from-blue-700 hover:to-cyan-700 text-white"
                      >
                        <FileSearch className="h-3 w-3 mr-1" />
                        Получить данные ({selectedDomains.size})
                      </Button>
                    </motion.div>
                  </motion.div>
                </div>
              </div>
              {/* === ЕДИНЫЙ БЛОК: Извлечение ИНН/email — метрики + статус парсера === */}
              {(() => {
                const supplierCount = groups.filter(g => g.supplierType === "supplier" || g.supplierType === "reseller").length
                const moderationCount = groups.filter(g => g.supplierType === "needs_moderation").length
                const noStatusCount = groups.filter(g => !g.supplierType).length
                const totalDomains = groups.length
                const allProcessed = totalDomains > 0 && noStatusCount === 0
                const realPercent = totalDomains > 0 ? Math.min(100, Math.round(((supplierCount + moderationCount) / totalDomains) * 100)) : 0
                const processLog = run?.processLog || run?.process_log
                const dpAuto = processLog?.domain_parser_auto
                const isWorkerOnThisRun = workerCurrentRun?.runId === runId
                const isWorkerBusy = !!workerCurrentRun
                const isRunning = isWorkerOnThisRun && !workerPaused

                return (
                  <motion.div initial={{ opacity: 0, y: -10 }} animate={{ opacity: 1, y: 0 }} className="mb-3">
                    <div className="rounded-lg border border-slate-200 bg-white shadow-sm overflow-hidden">
                      {/* Заголовок + кнопка паузы */}
                      <div className="flex items-center justify-between px-3 py-2 bg-slate-50 border-b border-slate-200">
                        <span className="text-sm font-semibold text-slate-700">Извлечение ИНН / Email</span>
                        <div className="flex items-center gap-2">
                          <div className="flex items-center gap-1.5 text-xs">
                            <span className="px-2 py-0.5 rounded-full bg-emerald-50 text-emerald-700 border border-emerald-200 font-medium">🏢 {supplierCount}</span>
                            <span className="px-2 py-0.5 rounded-full bg-amber-50 text-amber-700 border border-amber-200 font-medium">⚠️ {moderationCount}</span>
                            <span className="text-slate-400">/ {totalDomains} обработано</span>
                          </div>
                          {moderationCount > 0 && (
                            <Button
                              size="sm"
                              className="h-6 text-[10px] px-2 bg-gradient-to-r from-blue-600 to-cyan-600 hover:from-blue-700 hover:to-cyan-700 text-white"
                              disabled={parserLoading}
                              onClick={() => {
                                const moderationDomains = groups
                                  .filter(g => g.supplierType === "needs_moderation")
                                  .map(g => g.domain)
                                if (moderationDomains.length === 0) return
                                setSelectedDomains(new Set(moderationDomains))
                              }}
                            >
                              <FileSearch className="h-3 w-3 mr-1" />
                              Выбрать модерацию ({moderationCount})
                            </Button>
                          )}
                        </div>
                      </div>

                      {/* Прогресс-бар */}
                      <div className="px-3 py-2">
                        <FlinstonesProgressBar
                          progress={totalDomains > 0 ? Math.min(100, Math.round(((supplierCount + moderationCount) / totalDomains) * 100)) : 0}
                          label="Прогресс"
                          color={moderationCount > 0 ? "amber" : "emerald"}
                          current={supplierCount + moderationCount}
                          total={totalDomains}
                          isActive={isRunning}
                        />
                      </div>

                      {/* Статус парсера — ВСЕГДА видно */}
                      <div className="px-3 py-2">
                        {workerPaused ? (
                          <div className="flex items-center gap-2 text-xs text-amber-700 bg-amber-50 rounded-md px-2 py-1.5 border border-amber-200">
                            <span className="text-base">⏸</span>
                            <div>
                              <span className="font-semibold">Парсер приостановлен.</span> Нажмите «Продолжить» чтобы возобновить.
                            </div>
                          </div>
                        ) : isRunning ? (
                          <div className="space-y-1.5">
                            <div className="flex items-center gap-2 text-xs text-blue-700 bg-blue-50 rounded-md px-2 py-1.5 border border-blue-100">
                              <motion.div animate={{ rotate: 360 }} transition={{ duration: 2, repeat: Infinity, ease: "linear" }}>
                                <Activity className="h-3.5 w-3.5" />
                              </motion.div>
                              <div className="flex flex-wrap gap-x-3 gap-y-0.5">
                                <span className="font-semibold">Парсер работает</span>
                                {workerCurrentRun?.keyword && <span>🔑 {workerCurrentRun.keyword}</span>}
                                {parserStatus?.currentDomain && <span>🔍 <b>{parserStatus.currentDomain}</b></span>}
                                <span>📊 {workerCurrentRun?.processed}/{workerCurrentRun?.total}</span>
                                {parserStatus?.currentSourceUrls && parserStatus.currentSourceUrls.length > 0 && (
                                  <span className="text-slate-500">🌐 {parserStatus.currentSourceUrls.length} URL</span>
                                )}
                              </div>
                            </div>
                            {/* Live per-domain results */}
                            {parserStatus?.results && parserStatus.results.length > 0 && (
                              <div className="bg-slate-50 rounded-md border border-slate-200 px-2 py-1.5 max-h-[120px] overflow-y-auto">
                                <div className="text-[10px] font-semibold text-slate-500 mb-1">Обработанные домены:</div>
                                {parserStatus.results.map((r: any, i: number) => (
                                  <div key={i} className="flex items-center gap-1.5 text-[10px] py-0.5 border-b border-slate-100 last:border-0">
                                    <span className={r.inn ? "text-emerald-600" : r.error ? "text-red-500" : "text-amber-500"}>
                                      {r.inn ? "✅" : r.error ? "❌" : "⚠️"}
                                    </span>
                                    <span className="font-mono text-slate-700 w-[140px] truncate">{r.domain}</span>
                                    {r.inn && <span className="text-blue-700 font-medium">ИНН: {r.inn}</span>}
                                    {r.emails?.length > 0 && <span className="text-emerald-600">📧 {r.emails[0]}</span>}
                                    {!r.inn && !r.error && !(r.emails?.length > 0) && <span className="text-slate-400">нет данных</span>}
                                    {!r.inn && !r.error && r.emails?.length > 0 && !r.inn && <span className="text-amber-500">ИНН не найден</span>}
                                    {r.error && <span className="text-red-500 truncate max-w-[200px]">{r.error}</span>}
                                    {r.sourceUrls && <span className="text-slate-400 ml-auto">{r.sourceUrls.length} стр.</span>}
                                  </div>
                                ))}
                              </div>
                            )}
                          </div>
                        ) : isWorkerBusy && !isWorkerOnThisRun ? (
                          <div className="flex items-center gap-2 text-xs text-slate-600 bg-slate-50 rounded-md px-2 py-1.5 border border-slate-200">
                            <span className="text-base">⏳</span>
                            <div className="flex flex-wrap gap-x-3 gap-y-0.5">
                              <span className="font-semibold">Парсер занят другим run</span>
                              {workerCurrentRun?.keyword && <span>🔑 {workerCurrentRun.keyword}</span>}
                              <a href={`/parsing-runs/${workerCurrentRun?.runId}`} className="underline text-blue-600">
                                📋 {workerCurrentRun?.runId?.slice(0, 8)}…
                              </a>
                              {parserStatus?.currentDomain && <span>🔍 {parserStatus.currentDomain}</span>}
                            </div>
                          </div>
                        ) : allProcessed ? (
                          <div className="flex items-center gap-2 text-xs text-emerald-700 bg-emerald-50 rounded-md px-2 py-1.5 border border-emerald-200">
                            <span className="text-base">✅</span>
                            <span className="font-semibold">Все {totalDomains} доменов обработаны</span>
                            <span className="text-emerald-600">({realPercent}%)</span>
                          </div>
                        ) : noStatusCount > 0 && !isWorkerBusy ? (
                          <div className="flex items-center gap-2 text-xs text-amber-700 bg-amber-50 rounded-md px-2 py-1.5 border border-amber-200">
                            <span className="text-base">💤</span>
                            <div>
                              <span className="font-semibold">Парсер не активен.</span>
                              <span className="ml-1">{noStatusCount} доменов ожидают обработки.</span>
                              {dpAuto?.status === "completed" && <span className="ml-1 text-amber-600">(Run будет переставлен в очередь)</span>}
                            </div>
                          </div>
                        ) : (
                          <div className="flex items-center gap-2 text-xs text-slate-500 bg-slate-50 rounded-md px-2 py-1.5 border border-slate-200">
                            <span className="text-base">💤</span>
                            <span>Парсер не активен. Нет доменов для обработки.</span>
                          </div>
                        )}

                        {/* Доп. инфо: последний домен, ошибка */}
                        {(() => {
                          const results: any[] = (parserStatus?.results || []) as any[]
                          const fromResults = results.length > 0
                            ? String((results[0] as any)?.domain || (results[results.length - 1] as any)?.domain || "").trim()
                            : ""
                          const last =
                            (isRunning && parserStatus?.currentDomain ? String(parserStatus.currentDomain) : "") ||
                            (!isRunning ? fromResults : "") ||
                            (dpAuto?.lastDomain ? String(dpAuto.lastDomain) : "")
                          if (!last) return null
                          return <p className="text-[10px] text-slate-400 mt-1 pl-1">Последний обработанный: {last}</p>
                        })()}
                        {dpAuto?.error && (
                          <p className="text-[10px] text-red-600 mt-1 pl-1">Ошибка: {String(dpAuto.error)}</p>
                        )}
                      </div>
                    </div>
                  </motion.div>
                )
              })()}

              {parsingLogs && (parsingLogs.google || parsingLogs.yandex) && (
                <div className="mb-4">
                  {accordionValue.includes("google") && parsingLogs.google && (
                    <div className="rounded-md border border-blue-100 bg-blue-50/40 p-3 mb-3">
                      <div className="text-sm space-y-1">
                        <p className="text-muted-foreground">
                          Найдено ссылок: <span className="font-medium text-blue-600">{parsingLogs.google.total_links}</span>
                        </p>
                        {parsingLogs.google.pages_processed > 0 && (
                          <p className="text-muted-foreground">
                            Обработано страниц: <span className="font-medium">{parsingLogs.google.pages_processed}</span>
                          </p>
                        )}
                        {parsingLogs.google.links_by_page && Object.keys(parsingLogs.google.links_by_page).length > 0 && (
                          <div className="mt-2">
                            <p className="text-xs font-medium text-muted-foreground mb-1">Ссылок по страницам:</p>
                            <div className="flex flex-wrap gap-2">
                              {Object.entries(parsingLogs.google.links_by_page)
                                .sort(([a], [b]) => Number(a) - Number(b))
                                .map(([page, count]) => (
                                  <Badge key={`google-page-${page}`} variant="outline" className="text-xs">
                                    Страница {page}: {count}
                                  </Badge>
                                ))}
                            </div>
                          </div>
                        )}
                      </div>
                      {parsingLogs.google.last_links && parsingLogs.google.last_links.length > 0 && (
                        <div className="mt-3">
                          <p className="text-xs font-medium text-muted-foreground mb-2">
                            Найденные ссылки ({parsingLogs.google.last_links.length}):
                          </p>
                          <div className="space-y-1 max-h-96 overflow-y-auto border rounded-md p-2 bg-muted/30">
                            {parsingLogs.google.last_links.map((link, idx) => (
                              <div key={`google-${idx}`} className="text-xs text-muted-foreground flex items-start gap-2 py-1">
                                <span className="text-muted-foreground/50 min-w-[2rem]">{idx + 1}.</span>
                                <a
                                  href={link}
                                  target="_blank"
                                  rel="noopener noreferrer"
                                  className="text-blue-600 hover:text-blue-800 hover:underline break-all flex-1"
                                >
                                  {link}
                                </a>
                                <ExternalLink className="w-3 h-3 text-muted-foreground/50 flex-shrink-0 mt-0.5" />
                              </div>
                            ))}
                          </div>
                        </div>
                      )}
                    </div>
                  )}

                  {accordionValue.includes("yandex") && parsingLogs.yandex && (
                    <div className="rounded-md border border-red-100 bg-red-50/40 p-3">
                      <div className="text-sm space-y-1">
                        <p className="text-muted-foreground">
                          Найдено ссылок: <span className="font-medium text-red-600">{parsingLogs.yandex.total_links}</span>
                        </p>
                        {parsingLogs.yandex.pages_processed > 0 && (
                          <p className="text-muted-foreground">
                            Обработано страниц: <span className="font-medium">{parsingLogs.yandex.pages_processed}</span>
                          </p>
                        )}
                        {parsingLogs.yandex.links_by_page && Object.keys(parsingLogs.yandex.links_by_page).length > 0 && (
                          <div className="mt-2">
                            <p className="text-xs font-medium text-muted-foreground mb-1">Ссылок по страницам:</p>
                            <div className="flex flex-wrap gap-2">
                              {Object.entries(parsingLogs.yandex.links_by_page)
                                .sort(([a], [b]) => Number(a) - Number(b))
                                .map(([page, count]) => (
                                  <Badge key={`yandex-page-${page}`} variant="outline" className="text-xs">
                                    Страница {page}: {count}
                                  </Badge>
                                ))}
                            </div>
                          </div>
                        )}
                      </div>
                      {parsingLogs.yandex.last_links && parsingLogs.yandex.last_links.length > 0 && (
                        <div className="mt-3">
                          <p className="text-xs font-medium text-muted-foreground mb-2">
                            Найденные ссылки ({parsingLogs.yandex.last_links.length}):
                          </p>
                          <div className="space-y-1 max-h-96 overflow-y-auto border rounded-md p-2 bg-muted/30">
                            {parsingLogs.yandex.last_links.map((link, idx) => (
                              <div key={`yandex-${idx}`} className="text-xs text-muted-foreground flex items-start gap-2 py-1">
                                <span className="text-muted-foreground/50 min-w-[2rem]">{idx + 1}.</span>
                                <a
                                  href={link}
                                  target="_blank"
                                  rel="noopener noreferrer"
                                  className="text-red-600 hover:text-red-800 hover:underline break-all flex-1"
                                >
                                  {link}
                                </a>
                                <ExternalLink className="w-3 h-3 text-muted-foreground/50 flex-shrink-0 mt-0.5" />
                              </div>
                            ))}
                          </div>
                        </div>
                      )}
                    </div>
                  )}
                </div>
              )}
              {/* Фильтры и поиск */}
              <div className="w-full space-y-2">
                <div className="flex w-full items-center gap-3">
                  <div className="min-w-0 flex-1">
                    <GlowSearchInput
                      placeholder=""
                      value={searchQuery}
                      onChange={(e) => setSearchQuery(e.target.value)}
                      containerClassName="w-full min-w-0"
                      filterOpen={filterMenuOpen}
                      onFilterOpenChange={setFilterMenuOpen}
                      filterContent={
                        <div className="rounded-md border border-border bg-popover text-popover-foreground shadow-md p-1">
                          <button
                            type="button"
                            className={
                              filterStatus === "all"
                                ? "w-full text-left text-xs px-2 py-1.5 rounded bg-accent text-accent-foreground"
                                : "w-full text-left text-xs px-2 py-1.5 rounded hover:bg-accent/50"
                            }
                            onClick={() => {
                              setFilterStatus("all")
                              setFilterMenuOpen(false)
                            }}
                          >
                            Все домены
                          </button>
                          <button
                            type="button"
                            className={
                              filterStatus === "supplier"
                                ? "w-full text-left text-xs px-2 py-1.5 rounded bg-accent text-accent-foreground"
                                : "w-full text-left text-xs px-2 py-1.5 rounded hover:bg-accent/50"
                            }
                            onClick={() => {
                              setFilterStatus("supplier")
                              setFilterMenuOpen(false)
                            }}
                          >
                            Поставщики
                          </button>
                          <button
                            type="button"
                            className={
                              filterStatus === "reseller"
                                ? "w-full text-left text-xs px-2 py-1.5 rounded bg-accent text-accent-foreground"
                                : "w-full text-left text-xs px-2 py-1.5 rounded hover:bg-accent/50"
                            }
                            onClick={() => {
                              setFilterStatus("reseller")
                              setFilterMenuOpen(false)
                            }}
                          >
                            Ресселеры
                          </button>
                          <button
                            type="button"
                            className={
                              filterStatus === "needs_moderation"
                                ? "w-full text-left text-xs px-2 py-1.5 rounded bg-accent text-accent-foreground"
                                : "w-full text-left text-xs px-2 py-1.5 rounded hover:bg-accent/50"
                            }
                            onClick={() => {
                              setFilterStatus("needs_moderation")
                              setFilterMenuOpen(false)
                            }}
                          >
                            Требуют модерации
                          </button>
                        </div>
                      }
                    />
                  </div>

                  <div className="shrink-0 rounded-[0.9em] bg-[linear-gradient(90deg,#03a9f4,#f441a5)] p-[3px] transition-all duration-300 hover:shadow-[0_0_20px_rgba(244,65,165,0.45)]">
                    <button
                      type="button"
                      onClick={() => {
                        const allVisible = groups.filter((group) => {
                          if (searchQuery && !group.domain.toLowerCase().includes(searchQuery.toLowerCase())) return false
                          if (filterStatus === "supplier" && group.supplierType !== "supplier") return false
                          if (filterStatus === "reseller" && group.supplierType !== "reseller") return false
                          if (filterStatus === "needs_moderation" && group.supplierType !== "needs_moderation") return false
                          return true
                        })
                        const allSelected = allVisible.length > 0 && allVisible.every((g) => selectedDomains.has(g.domain))
                        if (allSelected) {
                          setSelectedDomains(new Set())
                        } else {
                          setSelectedDomains(new Set(allVisible.map((g) => g.domain)))
                        }
                      }}
                      className="min-h-[56px] rounded-[0.5em] border-0 bg-black px-4 text-sm font-semibold text-white shadow-[2px_2px_3px_#000000b4] cursor-pointer"
                    >
                      {(() => {
                        const allVisible = groups.filter((group) => {
                          if (searchQuery && !group.domain.toLowerCase().includes(searchQuery.toLowerCase())) return false
                          if (filterStatus === "supplier" && group.supplierType !== "supplier") return false
                          if (filterStatus === "reseller" && group.supplierType !== "reseller") return false
                          if (filterStatus === "needs_moderation" && group.supplierType !== "needs_moderation") return false
                          return true
                        })
                        const allSelected = allVisible.length > 0 && allVisible.every((g) => selectedDomains.has(g.domain))
                        return allSelected ? "Отменить все" : `Выбрать все (${allVisible.length})`
                      })()}
                    </button>
                  </div>
                </div>

                {selectedDomains.size > 0 && (
                  <div className="flex justify-end">
                    <Badge variant="outline" className="bg-accent/30 border-border text-foreground">
                      Выбрано: {selectedDomains.size}
                    </Badge>
                  </div>
                )}
              </div>
            </CardHeader>
            <CardContent>
              {(() => {
                // Применяем фильтры
                const filteredGroups = groups.filter((group) => {
                  // Фильтр по поисковому запросу
                  if (searchQuery && !group.domain.toLowerCase().includes(searchQuery.toLowerCase())) {
                    return false
                  }
                  // Фильтр по статусу
                  if (filterStatus === "supplier" && group.supplierType !== "supplier") {
                    return false
                  }
                  if (filterStatus === "reseller" && group.supplierType !== "reseller") {
                    return false
                  }
                  if (filterStatus === "needs_moderation" && group.supplierType !== "needs_moderation") {
                    return false
                  }
                  // 'new' filter removed
                  return true
                })

                if (filteredGroups.length === 0) {
                  return (
                    <div className="text-center py-12 text-muted-foreground">
                      Результаты не найдены или все домены в blacklist
                    </div>
                  )
                }

                return (
                  <div className="w-full">
                    <div className="relative overflow-hidden rounded-md border border-border bg-card">
                      {(() => {
                        const logGroups = filteredGroups
                        const withInn = logGroups.filter((g) => !!g.inn)
                        const withError = logGroups.filter((g) => ((g as any).extractionLog || []).some((e: any) => !!e.error) && !g.inn)
                        const noData = logGroups.filter((g) => !g.inn && (!g.emails || g.emails.length === 0) && !(((g as any).extractionLog || []).some((e: any) => !!e.error)))

                        return (
                          <div className="flex items-center gap-3 border-b border-border bg-muted/35 px-3 py-2 flex-wrap">
                            <span className="text-sm font-semibold text-foreground">Лог извлечения</span>
                            <div className="flex gap-1.5 text-xs">
                              {withInn.length > 0 && (
                                <Badge className="bg-emerald-100 text-emerald-700 border-emerald-200">ИНН: {withInn.length}</Badge>
                              )}
                              {withError.length > 0 && (
                                <Badge variant="destructive" className="text-xs">{withError.length} ошибок</Badge>
                              )}
                              {noData.length > 0 && (
                                <Badge variant="outline" className="text-xs">{noData.length} без данных</Badge>
                              )}
                            </div>
                          </div>
                        )
                      })()}

                      <table className="w-full text-xs">
                        <thead className="bg-card">
                          <tr className="border-b border-border">
                            <th className="py-2 px-2 w-8">
                              <Checkbox
                                checked={filteredGroups.length > 0 && filteredGroups.every((g) => selectedDomains.has(g.domain))}
                                onCheckedChange={() => {
                                  const allSel = filteredGroups.every((g) => selectedDomains.has(g.domain))
                                  if (allSel) {
                                    setSelectedDomains(new Set())
                                  } else {
                                    setSelectedDomains(new Set(filteredGroups.map((g) => g.domain)))
                                  }
                                }}
                              />
                            </th>
                            <th className="px-3 py-2 text-left font-semibold text-muted-foreground">Домен</th>
                            <th className="px-3 py-2 text-left font-semibold text-muted-foreground">ИНН</th>
                            <th className="px-3 py-2 text-left font-semibold text-muted-foreground">Email</th>
                            <th className="px-3 py-2 text-left font-semibold text-muted-foreground">Источник</th>
                            <th className="px-3 py-2 text-right font-semibold text-muted-foreground">Результат</th>
                          </tr>
                        </thead>
                        <tbody>
                          {filteredGroups.map((g, idx) => {
                            const root = extractRootDomain(g.domain).toLowerCase()
                            const hasParserResult = Boolean(g.inn) || Boolean(g.emails && g.emails.length > 0) || Boolean(((g as any).extractionLog || []).length > 0)
                            const extLog = (g as any).extractionLog as Array<{ url?: string; inn_found?: string; emails_found?: string[]; error?: string }> | undefined
                            const pagesWithInn = extLog?.filter((e) => e.inn_found)?.length || 0
                            const pagesWithEmail = extLog?.filter((e) => e.emails_found && e.emails_found.length > 0)?.length || 0
                            const pagesWithError = extLog?.filter((e) => e.error)?.length || 0

                            const innSourceUrl = g.innSourceUrl || extLog?.find((e) => e.inn_found)?.url
                            const emailSourceUrl = g.emailSourceUrl || extLog?.find((e) => e.emails_found && e.emails_found.length > 0)?.url
                            const primarySourceUrl = innSourceUrl || emailSourceUrl || (g.sourceUrls && g.sourceUrls.length > 0 ? g.sourceUrls[0] : null)

                            const googleHit = g.urls?.find((u) => (u.source || "") === "google" || (u.source || "") === "both")
                            const yandexHit = g.urls?.find((u) => (u.source || "") === "yandex" || (u.source || "") === "both")

                            // Если есть supplierId, значит поставщик уже существует в базе
                            const isExistingSupplier = g.supplierType === "supplier" && g.supplierId
                            const isUnprocessed = !hasParserResult && !g.inn && (!g.emails || g.emails.length === 0) && !((extLog || []).some((e) => !!e.error))
                            const resultLabel = isExistingSupplier
                              ? "supplier_icon"
                              : isUnprocessed
                                ? "не обработан"
                                : g.inn
                                  ? "ИНН найден"
                                  : (extLog || []).some((e) => !!e.error)
                                    ? "Parser timeout (ош)"
                                    : "Ничего не найдено"
                            const resultClass = isExistingSupplier
                              ? "text-emerald-600 font-semibold"
                              : isUnprocessed
                                ? "text-slate-500"
                                : g.inn
                                  ? "text-emerald-700"
                                  : (extLog || []).some((e) => !!e.error)
                                    ? "text-red-600"
                                    : "text-red-600"

                            const strategyUsed = (g as any).strategyUsed as string | null | undefined
                            const strategyTimeMs = (g as any).strategyTimeMs as number | null | undefined
                            const strategyTimeLabel = (() => {
                              if (strategyTimeMs === null || strategyTimeMs === undefined) return null
                              if (Number.isNaN(Number(strategyTimeMs))) return null
                              const ms = Number(strategyTimeMs)
                              if (ms >= 1000) return `${(ms / 1000).toFixed(1)}s`
                              return `${Math.round(ms)}ms`
                            })()

                            const supplierBadge = g.supplierType === "reseller" ? (
                              <button
                                type="button"
                                onClick={() => {
                                  if (g.supplierId) router.push(`/suppliers/${g.supplierId}`)
                                }}
                              >
                                <Badge className="bg-purple-50 text-purple-700 border border-purple-200 hover:bg-purple-100">Реселлер</Badge>
                              </button>
                            ) : g.supplierType === "needs_moderation" ? (
                              <button
                                type="button"
                                onClick={() => openManualLearnDialog(g.domain, g.inn || undefined)}
                              >
                                <Badge className="bg-amber-50 text-amber-700 border border-amber-200 hover:bg-amber-100">Требует модерации</Badge>
                              </button>
                            ) : g.supplierType === "supplier" ? null : (
                              <Badge variant="outline">Новый</Badge>
                            )

                            return (
                              <tr key={g.domain} className={`border-b border-border ${selectedDomains.has(g.domain) ? "bg-accent/35" : idx % 2 === 0 ? "bg-card" : "bg-muted/15"}`}>
                                <td className="py-1.5 px-2 w-8">
                                  <Checkbox
                                    checked={selectedDomains.has(g.domain)}
                                    onCheckedChange={() => toggleDomainSelection(g.domain)}
                                  />
                                </td>
                                <td className="py-1.5 px-3">
                                  <div className="flex items-center gap-2">
                                    <button
                                      type="button"
                                      className="font-mono text-blue-700 hover:underline"
                                      onClick={() => {
                                        setHistoryDomain(g.domain)
                                        setHistoryDialogOpen(true)
                                      }}
                                    >
                                      {g.domain}
                                    </button>
                                    {googleHit?.url ? (
                                      <a
                                        href={googleHit.url}
                                        target="_blank"
                                        rel="noopener noreferrer"
                                        className="text-[10px] px-1.5 py-0.5 rounded border border-blue-200 bg-blue-50 text-blue-700 hover:bg-blue-100"
                                        title={googleHit.url}
                                      >
                                        G
                                      </a>
                                    ) : null}
                                    {yandexHit?.url ? (
                                      <a
                                        href={yandexHit.url}
                                        target="_blank"
                                        rel="noopener noreferrer"
                                        className="text-[10px] px-1.5 py-0.5 rounded border border-amber-200 bg-amber-50 text-amber-700 hover:bg-amber-100"
                                        title={yandexHit.url}
                                      >
                                        Y
                                      </a>
                                    ) : null}
                                    {supplierBadge}
                                  </div>
                                </td>

                                <td className="py-1.5 px-3">
                                  {(() => {
                                    // Если есть supplierId, берем INN из данных поставщика
                                    if (g.supplierId) {
                                      const cachedSuppliers = getCachedSuppliers()
                                      const supplier = cachedSuppliers?.find((s) => s.id === g.supplierId)
                                      const inn = supplier?.inn || g.inn
                                      if (inn) {
                                        return (
                                          <div className="flex items-center gap-1">
                                            <span className="text-blue-700 font-medium">{inn}</span>
                                            <button
                                              type="button"
                                              className="text-slate-400 hover:text-blue-600 transition-colors"
                                              title="Копировать ИНН"
                                              onClick={() => {
                                                navigator.clipboard.writeText(inn)
                                                toast.success(`ИНН ${inn} скопирован`)
                                              }}
                                            >
                                              <Copy className="h-3 w-3" />
                                            </button>
                                          </div>
                                        )
                                      }
                                    }
                                    // Если нет supplierId, используем g.inn
                                    if (g.inn) {
                                      return (
                                        <div className="flex items-center gap-1">
                                          <span className="text-blue-700 font-medium">{g.inn}</span>
                                          <button
                                            type="button"
                                            className="text-slate-400 hover:text-blue-600 transition-colors"
                                            title="Копировать ИНН"
                                            onClick={() => {
                                              navigator.clipboard.writeText(g.inn || "")
                                              toast.success(`ИНН ${g.inn} скопирован`)
                                            }}
                                          >
                                            <Copy className="h-3 w-3" />
                                          </button>
                                          {innSourceUrl && (
                                            <a
                                              href={innSourceUrl}
                                              target="_blank"
                                              rel="noopener noreferrer"
                                              className="text-blue-500 hover:text-blue-700"
                                              title={innSourceUrl}
                                            >
                                              🔗
                                            </a>
                                          )}
                                        </div>
                                      )
                                    }
                                    return <span className="text-slate-400">—</span>
                                  })()}
                                </td>

                                <td className="py-1.5 px-3">
                                  {(() => {
                                    // Если есть supplierId, берем email из данных поставщика
                                    if (g.supplierId) {
                                      const cachedSuppliers = getCachedSuppliers()
                                      const supplier = cachedSuppliers?.find((s) => s.id === g.supplierId)
                                      const email = supplier?.email
                                      if (email) {
                                        return (
                                          <div className="flex items-center gap-1">
                                            <span className="text-emerald-700">{email}</span>
                                            <button
                                              type="button"
                                              className="text-slate-400 hover:text-emerald-600 transition-colors"
                                              title="Копировать Email"
                                              onClick={() => {
                                                navigator.clipboard.writeText(email)
                                                toast.success(`Email скопирован`)
                                              }}
                                            >
                                              <Copy className="h-3 w-3" />
                                            </button>
                                          </div>
                                        )
                                      }
                                    }
                                    // Если нет supplierId, используем g.emails
                                    if (g.emails && g.emails.length > 0) {
                                      return (
                                        <div className="flex items-center gap-1">
                                          <span className="text-emerald-700">{g.emails.join(", ")}</span>
                                          <button
                                            type="button"
                                            className="text-slate-400 hover:text-emerald-600 transition-colors"
                                            title="Копировать Email"
                                            onClick={() => {
                                              navigator.clipboard.writeText((g.emails || []).join(", "))
                                              toast.success(`Email скопирован`)
                                            }}
                                          >
                                            <Copy className="h-3 w-3" />
                                          </button>
                                          {emailSourceUrl && (
                                            <a
                                              href={emailSourceUrl}
                                              target="_blank"
                                              rel="noopener noreferrer"
                                              className="text-emerald-500 hover:text-emerald-700"
                                              title={emailSourceUrl}
                                            >
                                              🔗
                                            </a>
                                          )}
                                        </div>
                                      )
                                    }
                                    return <span className="text-slate-400">—</span>
                                  })()}
                                </td>

                                <td className="py-1.5 px-3">
                                  {primarySourceUrl ? (
                                    <a
                                      href={primarySourceUrl}
                                      target="_blank"
                                      rel="noopener noreferrer"
                                      className="text-blue-600 hover:underline text-[10px] truncate max-w-[260px] inline-block align-middle"
                                      title={primarySourceUrl}
                                    >
                                      {primarySourceUrl.replace(/^https?:\/\//, "").slice(0, 48)}
                                      {primarySourceUrl.length > 80 ? "…" : ""}
                                    </a>
                                  ) : (
                                    <span className="text-slate-400">—</span>
                                  )}
                                </td>


                                <td className="py-1.5 px-3 text-right">
                                  <div className="flex flex-col items-end">
                                    {resultLabel === "supplier_icon" ? (
                                      <button
                                        type="button"
                                        title={g.supplierId ? "Открыть карточку поставщика" : "Поставщик"}
                                        aria-label="Поставщик"
                                        disabled={!g.supplierId}
                                        onClick={() => {
                                          if (g.supplierId) router.push(`/suppliers/${g.supplierId}`)
                                        }}
                                        className="inline-flex items-center justify-center rounded-full p-0.5 transition-all duration-200 hover:scale-105 hover:shadow-sm hover:ring-2 hover:ring-ring/35 disabled:cursor-default disabled:opacity-70 disabled:hover:scale-100 disabled:hover:shadow-none disabled:hover:ring-0"
                                      >
                                        <SupplierIcon />
                                      </button>
                                    ) : (
                                      <span className={resultClass}>{resultLabel}</span>
                                    )}
                                    {(strategyUsed || strategyTimeLabel) && (
                                      <span className="text-[10px] text-slate-400">
                                        {strategyUsed ? `🧩 ${strategyUsed}` : null}
                                        {strategyUsed && strategyTimeLabel ? " · " : null}
                                        {strategyTimeLabel ? `⏱ ${strategyTimeLabel}` : null}
                                      </span>
                                    )}
                                  </div>
                                </td>
                              </tr>
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

          {learnedItems.length > 0 && (
            <Card className="mt-4 border border-slate-200">
              <CardContent className="space-y-4 pt-4">
                <div>
                  <h4 className="font-semibold text-sm mb-2 flex items-center gap-2">
                    🎓 Обучение парсера — Чему научился Domain Parser
                  </h4>
                  <Accordion type="multiple" className="w-full">
                    {learnedItems.map((item, idx) => (
                      <AccordionItem key={`learned-${idx}`} value={`learned-${idx}`} className="border-b">
                        <AccordionTrigger className="hover:no-underline">
                          <div className="flex items-center gap-2 flex-1">
                            <span
                              className={`w-3 h-3 rounded-full ${item.type === "inn" ? "bg-blue-500" : "bg-green-500"}`}
                            ></span>
                            <span className="font-mono font-semibold">{item.domain}</span>
                            <Badge className={item.type === "inn" ? "bg-blue-600 text-white" : "bg-green-600 text-white"}>
                              {item.type === "inn" ? "ИНН" : "Email"}: {item.value}
                            </Badge>
                            <Badge variant="outline" className="bg-purple-50">
                              📚 Выучено
                            </Badge>
                          </div>
                        </AccordionTrigger>
                        <AccordionContent>
                          <div className="pt-2 space-y-3">
                            <div className="p-3 bg-purple-50 border border-purple-200 rounded-md">
                              <p className="text-sm font-semibold text-purple-900 mb-2">💡 Что выучил парсер:</p>
                              <p className="text-sm text-purple-800">{item.learning}</p>
                            </div>

                            <div className="text-sm">
                              <p className="font-semibold text-gray-700 mb-1">Найденное значение:</p>
                              <div
                                className={`p-2 rounded border ${
                                  item.type === "inn" ? "bg-blue-50 border-blue-200" : "bg-green-50 border-green-200"
                                }`}
                              >
                                <span className="font-mono text-lg">{item.value}</span>
                              </div>
                            </div>

                            {item.sourceUrls && item.sourceUrls.length > 0 && (
                              <div className="text-sm">
                                <p className="font-semibold text-gray-700 mb-1">Источники ({item.sourceUrls.length}):</p>
                                <div className="space-y-1">
                                  {item.sourceUrls.map((url, urlIdx) => (
                                    <div key={urlIdx} className="text-xs">
                                      <a
                                        href={url}
                                        target="_blank"
                                        rel="noopener noreferrer"
                                        className="text-blue-600 hover:underline flex items-center gap-1"
                                      >
                                        <span className="truncate">{url}</span>
                                        <ExternalLink className="h-3 w-3 flex-shrink-0" />
                                      </a>
                                    </div>
                                  ))}
                                </div>
                              </div>
                            )}

                            {item.urlPatterns && item.urlPatterns.length > 0 && (
                              <div className="text-sm">
                                <p className="font-semibold text-gray-700 mb-1">Выученные URL паттерны:</p>
                                <div className="flex flex-wrap gap-1">
                                  {item.urlPatterns.map((pattern, patternIdx) => (
                                    <Badge key={patternIdx} variant="outline" className="text-xs">
                                      {pattern}
                                    </Badge>
                                  ))}
                                </div>
                              </div>
                            )}
                          </div>
                        </AccordionContent>
                      </AccordionItem>
                    ))}
                  </Accordion>

                  {learningStats && (
                    <div className="mt-3 p-3 bg-purple-50 border border-purple-200 rounded-md">
                      <p className="text-sm text-purple-800">
                        <strong>📊 Статистика обучения:</strong> Всего выучено паттернов: {learningStats.totalLearned}
                      </p>
                    </div>
                  )}
                </div>
              </CardContent>
            </Card>
          )}
        </motion.div>
      </motion.main>

      {/* Supplier Dialog */}
      <Dialog open={supplierDialogOpen} onOpenChange={setSupplierDialogOpen}>
        <DialogContent>
          <DialogHeader>
            <DialogTitle>
              {editingSupplierId
                ? `Изменить ${supplierForm.type === "supplier" ? "поставщика" : "реселлера"}`
                : supplierForm.type === "supplier"
                  ? "Создать поставщика"
                  : "Создать реселлера"}
            </DialogTitle>
            <DialogDescription>Заполните информацию о компании</DialogDescription>
          </DialogHeader>

          <div className="space-y-4">
            <div>
              <Label htmlFor="name">Название *</Label>
              <Input
                id="name"
                value={supplierForm.name}
                onChange={(e) => setSupplierForm({ ...supplierForm, name: e.target.value })}
                placeholder="ООО Компания"
              />
            </div>
            <div>
              <div className="flex items-start gap-2">
                <div className="flex-1">
                  <Label htmlFor="inn">ИНН</Label>
                  <Input
                    id="inn"
                    value={supplierForm.inn}
                    onChange={(e) => setSupplierForm({ ...supplierForm, inn: e.target.value.replace(/\D/g, "") })}
                    placeholder="1234567890"
                  />
                </div>
                <div className="pt-7 flex gap-2">
                  <CheckoInfoDialog
                    inn={supplierForm.inn}
                    onDataLoaded={(data) => {
                      setSupplierForm({ ...supplierForm, ...data })
                    }}
                  />
                  {supplierForm.inn && supplierForm.inn.length >= 10 && (
                    <Button
                      variant="outline"
                      size="default"
                      onClick={() => window.open(`https://checko.ru/search?query=${supplierForm.inn}`, "_blank")}
                      className="flex items-center gap-1"
                      title="Открыть на Checko.ru"
                    >
                      <ExternalLink className="h-4 w-4" />
                      Checko
                    </Button>
                  )}
                </div>
              </div>
            </div>
            <div>
              <Label htmlFor="email">Email</Label>
              <Input
                id="email"
                type="email"
                value={supplierForm.email}
                onChange={(e) => setSupplierForm({ ...supplierForm, email: e.target.value })}
                placeholder="info@example.com"
              />
            </div>
            <div>
              <Label htmlFor="domain">Домен</Label>
              <Input
                id="domain"
                value={supplierForm.domain}
                onChange={(e) => setSupplierForm({ ...supplierForm, domain: e.target.value })}
                placeholder="example.com"
              />
            </div>
            <div>
              <Label htmlFor="address">Адрес</Label>
              <Input
                id="address"
                value={supplierForm.address}
                onChange={(e) => setSupplierForm({ ...supplierForm, address: e.target.value })}
                placeholder="г. Москва, ул. Ленина, д. 1"
              />
            </div>
          </div>

          <DialogFooter>
            <Button
              variant="outline"
              onClick={() => {
                setSupplierDialogOpen(false)
                setEditingSupplierId(null)
              }}
            >
              Отмена
            </Button>
            <Button onClick={handleCreateSupplier}>{editingSupplierId ? "Сохранить" : "Создать"}</Button>
          </DialogFooter>
        </DialogContent>
      </Dialog>

      <Dialog open={!!innConflict} onOpenChange={(open) => !open && setInnConflict(null)}>
        <DialogContent>
          <DialogHeader>
            <DialogTitle>Конфликт ИНН</DialogTitle>
            <DialogDescription>В базе уже есть поставщик с таким ИНН.</DialogDescription>
          </DialogHeader>
          {innConflict && (
            <div className="space-y-2 text-sm">
              <div>Поставщик: {innConflict.existingSupplierName || `ID ${innConflict.existingSupplierId}`}</div>
              {innConflict.existingSupplierDomains?.length ? (
                <div>Домены: {innConflict.existingSupplierDomains.join(", ")}</div>
              ) : null}
              {innConflict.existingSupplierEmails?.length ? (
                <div>Email: {innConflict.existingSupplierEmails.join(", ")}</div>
              ) : null}
            </div>
          )}
          <DialogFooter className="flex flex-wrap gap-2">
            <Button variant="outline" onClick={() => setInnConflict(null)}>
              Отмена
            </Button>
            {innConflict && (
              <Button
                variant="secondary"
                onClick={async () => {
                  try {
                    if (!supplierForm.domain) {
                      toast.error("Укажите домен для привязки")
                      return
                    }
                    await attachDomainToSupplier(innConflict.existingSupplierId, {
                      domain: supplierForm.domain,
                      email: supplierForm.email || null,
                    })
                    setSupplierDialogOpen(false)
                    setEditingSupplierId(null)
                    loadData()
                  } finally {
                    setInnConflict(null)
                  }
                }}
              >
                Привязать домен
              </Button>
            )}
            {innConflict && (
              <Button
                onClick={async () => {
                  try {
                    await updateSupplier(innConflict.existingSupplierId, {
                      name: supplierForm.name,
                      inn: supplierForm.inn || null,
                      email: supplierForm.email || null,
                      domain: supplierForm.domain || null,
                      emails: supplierForm.email ? [supplierForm.email] : null,
                      domains: supplierForm.domain ? [supplierForm.domain] : null,
                      address: supplierForm.address || null,
                      type: supplierForm.type,
                    })
                    setSupplierDialogOpen(false)
                    setEditingSupplierId(null)
                    loadData()
                  } finally {
                    setInnConflict(null)
                  }
                }}
              >
                Обновить поставщика
              </Button>
            )}
          </DialogFooter>
        </DialogContent>
      </Dialog>

      {/* Blacklist Dialog */}
      <Dialog open={blacklistDialogOpen} onOpenChange={setBlacklistDialogOpen}>
        <DialogContent>
          <DialogHeader>
            <DialogTitle>Добавить домен в черный список</DialogTitle>
            <DialogDescription>Добавить "{blacklistDomain}" в blacklist?</DialogDescription>
          </DialogHeader>

          <div className="space-y-4">
            <div>
              <Label htmlFor="blacklist-reason">Причина добавления в черный список (необязательно)</Label>
              <Textarea
                id="blacklist-reason"
                placeholder="Укажите причину добавления домена в черный список..."
                value={blacklistReason}
                onChange={(e) => setBlacklistReason(e.target.value)}
                rows={4}
                className="mt-1"
              />
            </div>
          </div>

          <DialogFooter>
            <Button
              variant="outline"
              onClick={() => {
                setBlacklistDialogOpen(false)
                setBlacklistDomain("")
                setBlacklistReason("")
              }}
            >
              Отмена
            </Button>
            <Button onClick={handleAddToBlacklist} disabled={addingToBlacklist} variant="destructive">
              {addingToBlacklist ? "Добавление..." : "Добавить"}
            </Button>
          </DialogFooter>
        </DialogContent>
      </Dialog>

      {/* Old INN Extraction Dialog removed - using Domain Parser results accordion now */}
      <DomainHistoryDialog
        open={historyDialogOpen}
        onOpenChange={setHistoryDialogOpen}
        domain={historyDomain}
      />

      {/* Manual learning dialog */}
      <Dialog open={manualLearnDialogOpen} onOpenChange={setManualLearnDialogOpen}>
        <DialogContent>
          <DialogHeader>
            <DialogTitle>Обучить парсер по ИНН</DialogTitle>
            <DialogDescription>
              Вставьте ссылку, где отображён ИНН для домена {manualLearnDomain}
            </DialogDescription>
          </DialogHeader>

          <div className="space-y-4">
            <div>
              <Label htmlFor="manual-learn-domain">Домен</Label>
              <Input id="manual-learn-domain" value={manualLearnDomain} disabled />
            </div>
            <div>
              <Label htmlFor="manual-learn-inn">ИНН</Label>
              <Input
                id="manual-learn-inn"
                value={manualLearnInn}
                onChange={(e) => setManualLearnInn(e.target.value.replace(/\D/g, ""))}
                disabled={manualLearnInnDisabled}
              />
            </div>
            <div>
              <Label htmlFor="manual-learn-url">Ссылка на страницу с ИНН</Label>
              <Input
                id="manual-learn-url"
                value={manualLearnSourceUrl}
                onChange={(e) => setManualLearnSourceUrl(e.target.value)}
                placeholder="https://example.com/rekvizity"
              />
            </div>
            <div>
              <Label htmlFor="manual-learn-urls">Доп. ссылки (по 1 в строке)</Label>
              <Textarea
                id="manual-learn-urls"
                value={manualLearnSourceUrlsText}
                onChange={(e) => setManualLearnSourceUrlsText(e.target.value)}
                placeholder={"https://site.ru/company/rekvizity\nhttps://site.ru/contacts"}
                rows={3}
              />
              <div className="text-[10px] text-muted-foreground mt-1">
                Вставь 1–3 ссылки на страницы, где реально виден ИНН. Парсер выучит URL-паттерны (например /requisites, /contacts).
              </div>
            </div>
          </div>

          <DialogFooter>
            <Button variant="outline" onClick={() => setManualLearnDialogOpen(false)}>
              Отмена
            </Button>
            <Button onClick={handleManualLearnSubmit} disabled={manualLearnSubmitting}>
              {manualLearnSubmitting ? "Обучение..." : "Сохранить"}
            </Button>
          </DialogFooter>
        </DialogContent>
      </Dialog>
    </div>
  )
}

export default function ParsingRunDetailsPageWithAuth() {
  return (
    <AuthGuard allowedRoles={["moderator"]}>
      <ParsingRunDetailsPage />
    </AuthGuard>
  )
}
