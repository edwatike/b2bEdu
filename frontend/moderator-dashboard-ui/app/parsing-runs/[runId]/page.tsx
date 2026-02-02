"use client"

import { useState, useEffect, useRef } from "react"
import { useRouter, useParams } from "next/navigation"
import { motion } from "framer-motion"
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card"
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
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from "@/components/ui/select"
import { Navigation } from "@/components/navigation"
import { CheckoInfoDialog } from "@/components/checko-info-dialog"
import { ParsingResultsTable } from "@/components/parsing/ParsingResultsTable"
import { AuthGuard } from "@/components/auth-guard"
import {
  getParsingRun,
  getDomainsQueue,
  getBlacklist,
  addToBlacklist,
  createSupplier,
  updateSupplier,
  getSuppliers,
  getParsingLogs,
  getCheckoData,
  startDomainParserBatch,
  getDomainParserStatus,
  learnManualInn,
  learnFromComet,
  APIError,
  type LearnedItem,
  type LearningStatistics,
} from "@/lib/api"
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
  Settings,
  Search,
} from "lucide-react"
import type {
  ParsingDomainGroup,
  ParsingRunDTO,
  SupplierDTO,
  DomainParserResult,
  DomainParserStatusResponse,
  CometExtractionResult,
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
  const [searchQuery, setSearchQuery] = useState("")
  const [sortBy, setSortBy] = useState<"domain" | "urls">("urls")
  const [filterStatus, setFilterStatus] = useState<"all" | "supplier" | "reseller" | "new">("all")
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

  // Comet state
  const [cometRunId, setCometRunId] = useState<string | null>(null)
  const [cometStatus, setCometStatus] = useState<any | null>(null)
  const [cometLoading, setCometLoading] = useState(false)
  const [cometResultsMap, setCometResultsMap] = useState<Map<string, any>>(new Map())

  // Learning state
  const [learningLoading, setLearningLoading] = useState(false)
  const [learnedItems, setLearnedItems] = useState<LearnedItem[]>([])
  const [learningStats, setLearningStats] = useState<LearningStatistics | null>(null)

  const [manualLearnDialogOpen, setManualLearnDialogOpen] = useState(false)
  const [manualLearnDomain, setManualLearnDomain] = useState("")
  const [manualLearnInn, setManualLearnInn] = useState("")
  const [manualLearnSourceUrl, setManualLearnSourceUrl] = useState("")
  const [manualLearnSubmitting, setManualLearnSubmitting] = useState(false)
  const [manualLearnInnDisabled, setManualLearnInnDisabled] = useState(false)

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

  // Восстанавливаем кэш результатов ИНН из localStorage при загрузке
  useEffect(() => {
    if (!runId) return
    try {
      // Old INN extraction cache removed - using Domain Parser now
    } catch (error) {
      // Игнорируем ошибки парсинга кэша
    }
  }, [runId])

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
    if (!runId || !parserRunId) return
    try {
      localStorage.setItem(`parser-run-${runId}`, parserRunId)
    } catch {
      // ignore
    }
  }, [parserRunId, runId])

  // Polling для Domain Parser статуса
  useEffect(() => {
    if (!parserRunId) return

    const poll = async () => {
      try {
        const status = await getDomainParserStatus(parserRunId)
        setParserStatus(status)
        if (status.results && status.results.length > 0) {
          setParserResultsMap((prev) => {
            const next = new Map(prev)
            for (const r of status.results) {
              next.set(r.domain, r)
            }
            return next
          })
        }
      } catch (e) {
        // silent
      }
    }

    poll()
    const t = setInterval(poll, 2000)
    return () => clearInterval(t)
  }, [runId, parserRunId])

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
      // Устанавливаем флаг сразу, чтобы предотвратить повторные запуски
      parserAutoSaveProcessedRef.current = true

      console.log("[Domain Parser AutoSave] Starting auto-save for domains with INN+Email")

      // КРИТИЧНО: Загружаем актуальный список поставщиков из БД перед началом
      let currentSuppliers: Map<string, SupplierDTO>
      try {
        const { suppliers } = await getSuppliers()
        currentSuppliers = new Map()
        for (const s of suppliers) {
          if (s.domain) {
            currentSuppliers.set(s.domain.toLowerCase(), s)
          }
        }
        console.log(`[Domain Parser AutoSave] Loaded ${currentSuppliers.size} existing suppliers from DB`)
      } catch (e) {
        console.error("[Domain Parser AutoSave] Failed to load suppliers, aborting:", e)
        toast.error("Ошибка загрузки списка поставщиков")
        return
      }

      let savedCount = 0
      let skippedCount = 0

      for (const [domain, result] of parserResultsMap.entries()) {
        // Пропускаем домены с ошибками или без ИНН
        if (result.error || !result.inn) {
          console.log(`[Domain Parser AutoSave] Skipping ${domain}: missing INN`)
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
          }

          const saved = await createSupplier(supplierData)

          console.log(`[Domain Parser AutoSave] Created supplier with Checko data:`, saved)

          // Добавляем в локальный список чтобы избежать повторного создания
          currentSuppliers.set(rootDomain, saved)

          toast.success(`✅ ${domain}: сохранен как поставщик`)
          savedCount++

          // Небольшая пауза между сохранениями
          await new Promise((resolve) => setTimeout(resolve, 500))
        } catch (error) {
          console.error(`[Domain Parser AutoSave] Error saving ${domain}:`, error)
          toast.error(`Ошибка сохранения ${domain}`)
        }
      }

      console.log(`[Domain Parser AutoSave] Completed: saved=${savedCount}, skipped=${skippedCount}`)

      // Перезагружаем список поставщиков
      if (savedCount > 0) {
        try {
          const { suppliers } = await getSuppliers()
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

  // Polling для получения логов парсера в реальном времени (только во время парсинга)
  useEffect(() => {
    if (!runId) return

    // Не пытаемся получать логи, пока run не загружен
    if (!run) {
      return
    }

    // Если парсинг завершен, не нужно polling
    if (run.status === "completed" || run.status === "failed") {
      return
    }

    const fetchLogs = async () => {
      try {
        const logsData = await getParsingLogs(runId)
        if (logsData.parsing_logs && Object.keys(logsData.parsing_logs).length > 0) {
          setParsingLogs(logsData.parsing_logs)
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

    // Загружаем логи сразу, если run существует и выполняется
    if (run.status === "running") {
      fetchLogs()
    }

    // Polling каждые 2 секунды, если парсинг выполняется
    const intervalId = setInterval(() => {
      if (run.status === "running") {
        fetchLogs()
      }
    }, 2000)

    return () => clearInterval(intervalId)
  }, [runId, run])

  async function loadData() {
    if (!runId) return
    setLoading(true)
    try {
      // Всегда загружаем свежие данные blacklist (кэш может быть устаревшим после добавления)
      // Поставщики можно использовать из кэша
      let suppliersData: { suppliers: any[]; total: number; limit: number; offset: number }
      let blacklistData: { entries: any[]; total: number; limit: number; offset: number }

      const cachedSuppliers = getCachedSuppliers()

      if (cachedSuppliers) {
        // Используем кэш для поставщиков
        suppliersData = {
          suppliers: cachedSuppliers,
          total: cachedSuppliers.length,
          limit: 1000,
          offset: 0,
        }
      } else {
        // Загружаем поставщиков и кэшируем
        const suppliersResult = await getSuppliers({ limit: 1000 })
        suppliersData = suppliersResult
        setCachedSuppliers(suppliersData.suppliers)
      }

      try {
        const nextMap = new Map<string, SupplierDTO>()
        for (const s of suppliersData.suppliers) {
          if ((s as any)?.domain) {
            const root = extractRootDomain(String((s as any).domain)).toLowerCase()
            nextMap.set(root, s as SupplierDTO)
          }
        }
        suppliersByDomainRef.current = nextMap
      } catch {
        // ignore
      }

      // Всегда загружаем свежие данные blacklist (чтобы видеть актуальный список после добавления)
      const blacklistResult = await getBlacklist({ limit: 1000 })
      blacklistData = blacklistResult
      // Обновляем кэш blacklist свежими данными
      setCachedBlacklist(blacklistData.entries)

      const [runData, domainsData, logsData] = await Promise.all([
        getParsingRun(runId),
        getDomainsQueue({ parsingRunId: runId, limit: 1000 }),
        getParsingLogs(runId).catch(() => ({ parsing_logs: {} })), // Загружаем логи вместе с данными
      ])

      setRun(runData)

      // Restore Domain Parser results from process_log if localStorage is empty
      try {
        const hasLocalParserRun = !!localStorage.getItem(`parser-run-${runId}`)
        const hasLocalParserResults = !!localStorage.getItem(`parser-results-${runId}`)
        const pl: any = (runData as any)?.processLog ?? (runData as any)?.process_log
        const runs: any = pl?.domain_parser?.runs

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
                  map.set(String(r.domain), r as DomainParserResult)
                }
              }
              setParserResultsMap(map)
              setParserStatus({
                runId,
                parserRunId: latestId,
                status: (latest.status || "completed") as any,
                processed: Number(latest.processed || map.size),
                total: Number(latest.total || map.size),
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

      // Фильтрация blacklist - нормализуем домены для сравнения
      const blacklistedDomains = new Set(blacklistData.entries.map((e) => extractRootDomain(e.domain).toLowerCase()))
      const normalizedEntries = domainsData.entries.map((entry) => ({
        ...entry,
        createdAt: entry.createdAt || (entry as { created_at?: string | null }).created_at || entry.createdAt,
      }))

      const filtered = normalizedEntries.filter((entry) => {
        const rootDomain = extractRootDomain(entry.domain).toLowerCase()
        return !blacklistedDomains.has(rootDomain)
      })

      // Создать Map для быстрого поиска поставщиков по домену
      // ВАЖНО: Используем toLowerCase для обоих доменов для корректного сопоставления
      const suppliersMap = new Map<string, { type: "supplier" | "reseller"; id: number }>()
      suppliersData.suppliers.forEach((supplier) => {
        if (supplier.domain) {
          const rootDomain = extractRootDomain(supplier.domain).toLowerCase()
          suppliersMap.set(rootDomain, { type: supplier.type, id: supplier.id })
        }
      })

      // Группировка с добавлением информации о поставщиках и источниках
      // Используем parsing_logs для точного определения источников каждого домена
      const parsingLogsForSources =
        logsData.parsing_logs && Object.keys(logsData.parsing_logs).length > 0 ? logsData.parsing_logs : null

      let grouped = groupByDomain(filtered).map((group) => {
        const groupDomainLower = group.domain.toLowerCase()
        const supplierInfo = suppliersMap.get(groupDomainLower)

        // Вычисляем источники для домена на основе всех его URL используя parsing_logs
        const sources = collectDomainSources(group.urls, parsingLogsForSources)

        return {
          ...group,
          supplierType: supplierInfo?.type || null,
          supplierId: supplierInfo?.id || null, // ID поставщика для редактирования
          sources: sources, // Источники, которые нашли этот домен
        }
      })

      // Сортировка
      grouped = grouped.sort((a, b) => {
        if (sortBy === "urls") {
          return b.totalUrls - a.totalUrls // По убыванию количества URL
        } else {
          return a.domain.localeCompare(b.domain) // По алфавиту
        }
      })

      setGroups(grouped)
    } catch (error) {
      toast.error("Ошибка загрузки данных")
      console.error("Error loading data:", error)
    } finally {
      setLoading(false)
    }
  }

  const openManualLearnDialog = (domain: string, inn?: string | null) => {
    setManualLearnDomain(domain)
    setManualLearnInn(inn ? String(inn) : "")
    setManualLearnInnDisabled(Boolean(inn))
    setManualLearnSourceUrl("")
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
    if (!manualLearnSourceUrl.trim()) {
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
      )

      if (response.learnedItems.length > 0) {
        setLearnedItems((prev) => [...response.learnedItems, ...prev])
        setLearningStats(response.statistics)
        toast.success(`🎓 Обучение сохранено: ${response.learnedItems.length} паттернов`)
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
      toast.error("Ошибка добавления в blacklist")
      console.error("Error adding to blacklist:", error)
      setLoading(false)
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

    try {
      if (editingSupplierId) {
        // Обновляем существующего поставщика
        await updateSupplier(editingSupplierId, {
          name: supplierForm.name,
          inn: supplierForm.inn || null,
          email: supplierForm.email || null,
          domain: supplierForm.domain || null,
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
    } catch (error) {
      toast.error(editingSupplierId ? "Ошибка обновления" : "Ошибка создания")
      console.error("Error saving supplier:", error)
    }
  }

  if (loading) {
    return (
      <div className="min-h-screen bg-gradient-to-br from-slate-50 to-purple-50/30">
        <Navigation />
        <motion.main
          initial={{ opacity: 0 }}
          animate={{ opacity: 1 }}
          transition={{ duration: 0.5 }}
          className="container mx-auto px-6 py-6"
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
      <div className="min-h-screen bg-gradient-to-br from-slate-50 to-red-50/30">
        <Navigation />
        <motion.main
          initial={{ opacity: 0 }}
          animate={{ opacity: 1 }}
          transition={{ duration: 0.5 }}
          className="container mx-auto px-6 py-6"
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
  const depth = run.depth || null
  const createdAt = run.startedAt || run.started_at || run.createdAt || run.created_at || ""
  const finishedAt = run.finishedAt || run.finished_at

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
    const allDomains = groups.map((g) => g.domain)
    setSelectedDomains(new Set(allDomains))
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
          refreshed.set(extractRootDomain(s.domain).toLowerCase(), s)
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
      const resp = await startDomainParserBatch(runId, domainsWithoutInn)
      setParserRunId(resp.parserRunId)
      toast.success(`Парсер запущен для ${domainsWithoutInn.length} доменов`)

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
    <div className="min-h-screen bg-gradient-to-br from-slate-50 to-purple-50/30">
      <Navigation />

      <motion.main
        initial={{ opacity: 0, y: 20 }}
        animate={{ opacity: 1, y: 0 }}
        transition={{ duration: 0.5 }}
        className="container mx-auto px-6 py-6 max-w-7xl"
      >
        {/* Summary */}
        <motion.div initial={{ opacity: 0, y: -20 }} animate={{ opacity: 1, y: 0 }} transition={{ duration: 0.6 }}>
          <Card className="card-hover bg-gradient-to-br from-white to-purple-50 border-purple-200 shadow-lg mb-6">
            <CardHeader className="p-6">
              <div className="flex items-start justify-between">
                <div>
                  <motion.div
                    initial={{ opacity: 0, x: -20 }}
                    animate={{ opacity: 1, x: 0 }}
                    transition={{ duration: 0.7, delay: 0.1 }}
                  >
                    <CardTitle className="text-2xl text-gradient mb-2">{keyword}</CardTitle>
                    <div className="flex items-center gap-3 text-sm text-muted-foreground flex-wrap">
                      <div className="flex items-center gap-1">
                        <Clock className="h-4 w-4" />
                        <span>Создан: {formatDate(createdAt)}</span>
                      </div>
                      {finishedAt && (
                        <div className="flex items-center gap-1">
                          <CheckCircle className="h-4 w-4" />
                          <span>Завершен: {formatDate(finishedAt)}</span>
                        </div>
                      )}
                      {depth !== null && depth !== undefined && (
                        <div className="flex items-center gap-1">
                          <Settings className="h-4 w-4" />
                          <span>Глубина: {depth}</span>
                        </div>
                      )}
                    </div>
                  </motion.div>
                </div>
                <motion.div
                  initial={{ opacity: 0, scale: 0.8 }}
                  animate={{ opacity: 1, scale: 1 }}
                  transition={{ duration: 0.5, delay: 0.2 }}
                >
                  {getStatusBadge(run.status)}
                </motion.div>
              </div>
            </CardHeader>
            {run.resultsCount !== null && run.resultsCount !== undefined && (
              <motion.div
                initial={{ opacity: 0, y: 20 }}
                animate={{ opacity: 1, y: 0 }}
                transition={{ duration: 0.5, delay: 0.3 }}
                className="p-6 pt-0"
              >
                <div className="flex items-center justify-between gap-4">
                  <div className="flex items-center gap-3">
                    <div className="text-3xl font-bold text-purple-600">{run.resultsCount}</div>
                    <div className="text-sm text-muted-foreground">результатов найдено</div>
                  </div>
                </div>
              </motion.div>
            )}
          </Card>
        </motion.div>

        {/* Results Accordion */}
        <motion.div
          initial={{ opacity: 0, y: 20 }}
          animate={{ opacity: 1, y: 0 }}
          transition={{ duration: 0.7, delay: 0.4 }}
        >
          <Card className="card-hover bg-gradient-to-br from-white to-purple-50 border-purple-200 shadow-lg">
            <CardHeader className="border-b border-purple-100 p-6">
              <div className="flex items-center justify-between mb-4">
                <motion.div
                  initial={{ opacity: 0, x: -20 }}
                  animate={{ opacity: 1, x: 0 }}
                  transition={{ duration: 0.5, delay: 0.5 }}
                >
                  <CardTitle className="text-xl flex items-center gap-2">
                    <Globe className="h-5 w-5 text-purple-600" />
                    Результаты парсинга
                  </CardTitle>
                </motion.div>
                {/* Кнопки для работы с выбранными доменами */}
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
                      className="h-8 text-xs border-purple-300 text-purple-700 hover:bg-purple-50 bg-transparent"
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
          {parserRunId && parserStatus && (
                <motion.div
                  initial={{ opacity: 0, y: -10 }}
                  animate={{ opacity: 1, y: 0 }}
                  transition={{ duration: 0.3 }}
                  className="mb-3"
                >
                  <div className="p-3 bg-gradient-to-r from-blue-50 to-cyan-50 rounded-lg border border-blue-200">
                    <div className="flex items-center gap-2">
                      <span
                        className={`font-medium flex items-center gap-1 ${
                          parserStatus.status === "running"
                            ? "text-blue-600"
                            : parserStatus.status === "completed"
                              ? "text-green-600"
                              : "text-red-600"
                        }`}
                      >
                        {parserStatus.status === "running" && (
                          <motion.div
                            animate={{ rotate: 360 }}
                            transition={{ duration: 2, repeat: Number.POSITIVE_INFINITY, ease: "linear" }}
                          >
                            <Activity className="h-4 w-4" />
                          </motion.div>
                        )}
                        {parserStatus.status === "running"
                          ? "Получение данных..."
                          : parserStatus.status === "completed"
                            ? "✅ Данные получены"
                            : "❌ Ошибка"}
                      </span>
                      <Badge variant="outline" className="bg-white border-blue-300">
                        {parserStatus.processed}/{parserStatus.total} доменов
                      </Badge>
                    </div>
                    {parserStatus.status === "running" && (
                      <div className="mt-2 w-full bg-gray-200 rounded-full h-2">
                        <motion.div
                          className="bg-gradient-to-r from-blue-600 to-cyan-600 h-2 rounded-full"
                          initial={{ width: 0 }}
                          animate={{ width: `${(parserStatus.processed / parserStatus.total) * 100}%` }}
                          transition={{ duration: 0.5 }}
                        />
                      </div>
                    )}
                  </div>
                </motion.div>
              )}
              {/* Кнопки выбора всех/снятия выбора */}
              <div className="flex items-center gap-2 mb-3">
                <motion.div whileHover={{ scale: 1.05 }} whileTap={{ scale: 0.95 }}>
                  <Button
                    size="sm"
                    variant="outline"
                    onClick={selectAllDomains}
                    className="h-7 text-xs border-purple-300 text-purple-700 hover:bg-purple-50 bg-transparent"
                  >
                    Выбрать все
                  </Button>
                </motion.div>
                <motion.div whileHover={{ scale: 1.05 }} whileTap={{ scale: 0.95 }}>
                  <Button
                    size="sm"
                    variant="outline"
                    onClick={deselectAllDomains}
                    className="h-7 text-xs border-purple-300 text-purple-700 hover:bg-purple-50 bg-transparent"
                  >
                    Снять выбор
                  </Button>
                </motion.div>
                {selectedDomains.size > 0 && (
                  <motion.div
                    initial={{ opacity: 0, scale: 0.8 }}
                    animate={{ opacity: 1, scale: 1 }}
                    transition={{ duration: 0.3 }}
                  >
                    <Badge variant="outline" className="bg-purple-50 border-purple-200 text-purple-700">
                      Выбрано: {selectedDomains.size}
                    </Badge>
                  </motion.div>
                )}
              </div>
              {/* Фильтры и поиск */}
              <div className="flex gap-2 flex-wrap">
                <div className="relative flex-1 min-w-[200px]">
                  <Search className="absolute left-3 top-1/2 transform -translate-y-1/2 h-4 w-4 text-purple-400" />
                  <Input
                    placeholder="Поиск по домену..."
                    value={searchQuery}
                    onChange={(e) => setSearchQuery(e.target.value)}
                    className="pl-10 border-purple-300 focus:border-purple-500 focus:ring-purple-500"
                  />
                </div>
                <Select value={sortBy} onValueChange={(value: "domain" | "urls") => setSortBy(value)}>
                  <SelectTrigger className="w-[180px] border-purple-300 focus:border-purple-500">
                    <SelectValue placeholder="Сортировка" />
                  </SelectTrigger>
                  <SelectContent>
                    <SelectItem value="urls">По количеству URL</SelectItem>
                    <SelectItem value="domain">По алфавиту</SelectItem>
                  </SelectContent>
                </Select>
                <Select
                  value={filterStatus}
                  onValueChange={(value: "all" | "supplier" | "reseller" | "new") => setFilterStatus(value)}
                >
                  <SelectTrigger className="w-[180px] border-purple-300 focus:border-purple-500">
                    <SelectValue placeholder="Фильтр" />
                  </SelectTrigger>
                  <SelectContent>
                    <SelectItem value="all">Все домены</SelectItem>
                    <SelectItem value="supplier">Только поставщики</SelectItem>
                    <SelectItem value="reseller">Только реселлеры</SelectItem>
                    <SelectItem value="new">Только новые</SelectItem>
                  </SelectContent>
                </Select>
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
                  if (filterStatus === "new" && group.supplierType !== null) {
                    return false
                  }
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
                  <ParsingResultsTable
                    groups={filteredGroups.map((group) => ({
                      domain: group.domain,
                      urls: group.urls,
                      totalUrls: group.totalUrls,
                      supplierType: group.supplierType,
                      supplierId: group.supplierId,
                      sources: group.sources,
                      isBlacklisted: false, // TODO: Add blacklist check
                      lastUpdate: getLatestUrlCreatedAt(group.urls) || undefined,
                    }))}
                    selectedDomains={selectedDomains}
                    onSelectionChange={setSelectedDomains}
                    onView={(domain) => {
                      // Open domain details
                      console.log("View domain:", domain)
                    }}
                    onEdit={(domain, supplierId, type) => {
                      if (type) {
                        openEditSupplierDialog(domain, supplierId, type)
                      }
                    }}
                    onBlacklist={(domain) => {
                      openBlacklistDialog(domain)
                    }}
                    onSupplier={(domain, type) => {
                      openSupplierDialog(domain, type)
                    }}
                    onBulkAction={(action, selectedDomains) => {
                      console.log("Bulk action:", action, Array.from(selectedDomains))
                      // Handle bulk actions
                    }}
                  />
                )
              })()}
            </CardContent>
          </Card>

          {/* Логи парсера в реальном времени */}
          {(run?.status === "running" || parsingLogs) && (
            <Card className="mt-6 border-2 border-blue-500">
              <CardHeader>
                <CardTitle>Состояние парсинга</CardTitle>
              </CardHeader>
              <CardContent>
                {parsingLogs ? (
                  <>
                    {parsingLogs.google || parsingLogs.yandex ? (
                      <Accordion
                        type="multiple"
                        value={accordionValue}
                        onValueChange={setAccordionValue}
                        className="w-full"
                      >
                        {parsingLogs.google && (
                          <AccordionItem value="google" className="border-b">
                            <AccordionTrigger className="hover:no-underline">
                              <div className="flex items-center gap-2 flex-1">
                                <span className="w-3 h-3 rounded-full bg-blue-500"></span>
                                <span className="font-semibold">Google</span>
                                <Badge variant="outline" className="ml-2">
                                  {parsingLogs.google.total_links} ссылок
                                </Badge>
                                {parsingLogs.google.pages_processed > 0 && (
                                  <Badge variant="outline" className="ml-1">
                                    {parsingLogs.google.pages_processed} стр.
                                  </Badge>
                                )}
                              </div>
                            </AccordionTrigger>
                            <AccordionContent>
                              <div className="pt-2 space-y-3">
                                <div className="text-sm space-y-1">
                                  <p className="text-muted-foreground">
                                    Найдено ссылок:{" "}
                                    <span className="font-medium text-blue-600">{parsingLogs.google.total_links}</span>
                                  </p>
                                  {parsingLogs.google.pages_processed > 0 && (
                                    <p className="text-muted-foreground">
                                      Обработано страниц:{" "}
                                      <span className="font-medium">{parsingLogs.google.pages_processed}</span>
                                    </p>
                                  )}
                                  {parsingLogs.google.links_by_page &&
                                    Object.keys(parsingLogs.google.links_by_page).length > 0 && (
                                      <div className="mt-2">
                                        <p className="text-xs font-medium text-muted-foreground mb-1">
                                          Ссылок по страницам:
                                        </p>
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
                                        <div
                                          key={`google-${idx}`}
                                          className="text-xs text-muted-foreground flex items-start gap-2 py-1"
                                        >
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
                            </AccordionContent>
                          </AccordionItem>
                        )}
                        {parsingLogs.yandex && (
                          <AccordionItem value="yandex" className="border-b">
                            <AccordionTrigger className="hover:no-underline">
                              <div className="flex items-center gap-2 flex-1">
                                <span className="w-3 h-3 rounded-full bg-red-500"></span>
                                <span className="font-semibold">Яндекс</span>
                                <Badge variant="outline" className="ml-2">
                                  {parsingLogs.yandex.total_links} ссылок
                                </Badge>
                                {parsingLogs.yandex.pages_processed > 0 && (
                                  <Badge variant="outline" className="ml-1">
                                    {parsingLogs.yandex.pages_processed} стр.
                                  </Badge>
                                )}
                              </div>
                            </AccordionTrigger>
                            <AccordionContent>
                              <div className="pt-2 space-y-3">
                                <div className="text-sm space-y-1">
                                  <p className="text-muted-foreground">
                                    Найдено ссылок:{" "}
                                    <span className="font-medium text-red-600">{parsingLogs.yandex.total_links}</span>
                                  </p>
                                  {parsingLogs.yandex.pages_processed > 0 && (
                                    <p className="text-muted-foreground">
                                      Обработано страниц:{" "}
                                      <span className="font-medium">{parsingLogs.yandex.pages_processed}</span>
                                    </p>
                                  )}
                                  {parsingLogs.yandex.links_by_page &&
                                    Object.keys(parsingLogs.yandex.links_by_page).length > 0 && (
                                      <div className="mt-2">
                                        <p className="text-xs font-medium text-muted-foreground mb-1">
                                          Ссылок по страницам:
                                        </p>
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
                                        <div
                                          key={`yandex-${idx}`}
                                          className="text-xs text-muted-foreground flex items-start gap-2 py-1"
                                        >
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
                            </AccordionContent>
                          </AccordionItem>
                        )}
                      </Accordion>
                    ) : (
                      <p className="text-sm text-muted-foreground">Логи парсинга пока недоступны...</p>
                    )}
                  </>
                ) : (
                  <p className="text-sm text-muted-foreground animate-pulse">Загрузка логов парсинга...</p>
                )}
              </CardContent>
            </Card>
          )}

          {/* Логи извлечения данных (Domain Parser) */}
          {parserStatus && parserStatus.results && parserStatus.results.length > 0 && (
            <Card className="mt-6 border-2 border-green-500">
              <CardHeader>
                <CardTitle>Результаты извлечения данных (ИНН + Email)</CardTitle>
              </CardHeader>
              <CardContent>
                <Accordion type="multiple" className="w-full">
                  {parserStatus.results.map((result, idx) => {
                    const hasData = result.inn || (result.emails && result.emails.length > 0)
                    const hasError = !!result.error

                    return (
                      <AccordionItem key={`parser-${idx}`} value={`parser-${idx}`} className="border-b">
                        <AccordionTrigger className="hover:no-underline">
                          <div className="flex items-center gap-2 flex-1">
                            <span
                              className={`w-3 h-3 rounded-full ${hasError ? "bg-red-500" : hasData ? "bg-green-500" : "bg-gray-400"}`}
                            ></span>
                            <span className="font-mono font-semibold">{result.domain}</span>
                            {result.inn && <Badge className="bg-blue-600 text-white">ИНН: {result.inn}</Badge>}
                            {result.emails && result.emails.length > 0 && (
                              <Badge className="bg-green-600 text-white">Email: {result.emails[0]}</Badge>
                            )}
                            {hasError && <Badge variant="destructive">Ошибка</Badge>}
                            {!hasData && !hasError && <Badge variant="outline">Не найдено</Badge>}
                          </div>
                        </AccordionTrigger>
                        <AccordionContent>
                          <div className="pt-2 space-y-3">
                            {result.inn && (
                              <div className="text-sm">
                                <p className="font-semibold text-blue-700 mb-1">ИНН найден:</p>
                                <div className="p-2 bg-blue-50 rounded border border-blue-200">
                                  <span className="font-mono text-lg">{result.inn}</span>
                                </div>
                              </div>
                            )}

                            {result.emails && result.emails.length > 0 && (
                              <div className="text-sm">
                                <p className="font-semibold text-green-700 mb-1">Email найден:</p>
                                <div className="space-y-1">
                                  {result.emails.map((email, emailIdx) => (
                                    <div key={emailIdx} className="p-2 bg-green-50 rounded border border-green-200">
                                      <a href={`mailto:${email}`} className="text-green-700 hover:underline">
                                        {email}
                                      </a>
                                    </div>
                                  ))}
                                </div>
                              </div>
                            )}

                            {result.sourceUrls && result.sourceUrls.length > 0 && (
                              <div className="text-sm">
                                <p className="font-semibold text-muted-foreground mb-1">
                                  Источники ({result.sourceUrls.length}):
                                </p>
                                <div className="space-y-1">
                                  {result.sourceUrls.map((url, urlIdx) => (
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

                            {result.error && (
                              <div className="p-3 bg-red-50 border border-red-200 rounded-md">
                                <p className="text-sm text-red-800 font-semibold mb-1">Ошибка:</p>
                                <p className="text-sm text-red-700">{result.error}</p>
                              </div>
                            )}

                            {!result.inn && !result.emails?.length && !result.error && (
                              <div className="p-3 bg-gray-50 border border-gray-200 rounded-md space-y-2">
                                <p className="text-sm text-gray-700">
                                  ℹ️ Данные не найдены на сайте. Возможно, сайт не содержит контактную информацию или она
                                  находится в защищенных разделах.
                                </p>
                                <Button
                                  size="sm"
                                  variant="outline"
                                  className="text-xs"
                                  onClick={() => openManualLearnDialog(result.domain)}
                                >
                                  🎓 Обучить (указать ИНН)
                                </Button>
                              </div>
                            )}
                          </div>
                        </AccordionContent>
                      </AccordionItem>
                    )
                  })}
                </Accordion>

                <div className="mt-4 p-3 bg-blue-50 border border-blue-200 rounded-md">
                  <p className="text-sm text-blue-800">
                    <strong>Статистика:</strong> Обработано {parserStatus.processed} из {parserStatus.total} доменов
                    {parserStatus.results.filter((r) => r.inn).length > 0 && (
                      <span> • ИНН найден: {parserStatus.results.filter((r) => r.inn).length}</span>
                    )}
                    {parserStatus.results.filter((r) => r.emails && r.emails.length > 0).length > 0 && (
                      <span>
                        {" "}
                        • Email найден: {parserStatus.results.filter((r) => r.emails && r.emails.length > 0).length}
                      </span>
                    )}
                  </p>
                </div>
              </CardContent>
            </Card>
          )}

          {/* Результаты обучения парсера */}
          {learnedItems.length > 0 && (
            <Card className="mt-6 border-2 border-purple-500">
              <CardHeader>
                <CardTitle className="flex items-center gap-2">
                  🎓 Обучение парсера — Чему научился Domain Parser
                </CardTitle>
              </CardHeader>
              <CardContent>
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
                  <div className="mt-4 p-3 bg-purple-50 border border-purple-200 rounded-md">
                    <p className="text-sm text-purple-800">
                      <strong>📊 Статистика обучения:</strong> Всего выучено паттернов: {learningStats.totalLearned} •
                      Обучений от Comet: {learningStats.cometContributions}
                    </p>
                  </div>
                )}
              </CardContent>
            </Card>
          )}

          {/* История парсинга */}
          {(run?.processLog || run?.process_log) && (
            <Card className="mt-6">
              <CardHeader>
                <CardTitle>История парсинга</CardTitle>
              </CardHeader>
              <CardContent>
                <div className="space-y-4">
                  {(() => {
                    const processLog = run.processLog || run.process_log
                    if (!processLog) return null

                    return (
                      <>
                        {processLog.source_statistics && (
                          <div>
                            <h4 className="font-semibold mb-2">Статистика по источникам:</h4>
                            <div className="flex gap-4 text-sm">
                              <span className="flex items-center gap-1">
                                <span className="w-2 h-2 rounded-full bg-blue-500"></span>
                                Google: {processLog.source_statistics.google}
                              </span>
                              <span className="flex items-center gap-1">
                                <span className="w-2 h-2 rounded-full bg-red-500"></span>
                                Yandex: {processLog.source_statistics.yandex}
                              </span>
                              <span className="flex items-center gap-1">
                                <span className="w-2 h-2 rounded-full bg-purple-500"></span>
                                Оба: {processLog.source_statistics.both}
                              </span>
                            </div>
                          </div>
                        )}
                        {processLog.total_domains !== undefined && (
                          <div>
                            <h4 className="font-semibold mb-2">Общее количество доменов:</h4>
                            <p className="text-sm">{processLog.total_domains}</p>
                          </div>
                        )}
                        {processLog.duration_seconds !== undefined && (
                          <div>
                            <h4 className="font-semibold mb-2">Время выполнения:</h4>
                            <p className="text-sm">
                              {Math.floor(processLog.duration_seconds / 60)} мин{" "}
                              {Math.floor(processLog.duration_seconds % 60)} сек
                            </p>
                          </div>
                        )}
                        {processLog.captcha_detected && (
                          <div className="p-3 bg-orange-50 border border-orange-200 rounded-md">
                            <p className="text-sm text-orange-800">⚠️ Обнаружена CAPTCHA во время парсинга</p>
                          </div>
                        )}
                        {processLog.error && (
                          <div className="p-3 bg-red-50 border border-red-200 rounded-md">
                            <h4 className="font-semibold mb-2 text-red-800">Ошибка:</h4>
                            <p className="text-sm text-red-700">{processLog.error}</p>
                          </div>
                        )}
                        {processLog.started_at && (
                          <div>
                            <h4 className="font-semibold mb-2">Время начала:</h4>
                            <p className="text-sm">{new Date(processLog.started_at).toLocaleString("ru-RU")}</p>
                          </div>
                        )}
                        {processLog.finished_at && (
                          <div>
                            <h4 className="font-semibold mb-2">Время завершения:</h4>
                            <p className="text-sm">{new Date(processLog.finished_at).toLocaleString("ru-RU")}</p>
                          </div>
                        )}
                      </>
                    )
                  })()}
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


