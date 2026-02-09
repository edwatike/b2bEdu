"use client"

import { useState, useEffect, useRef } from "react"
import { useRouter } from "next/navigation"
import { motion } from "framer-motion"
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card"
import { Button } from "@/components/ui/button"
import { Input } from "@/components/ui/input"
import { Badge } from "@/components/ui/badge"
import { Label } from "@/components/ui/label"
import { handleStartParsing } from "../actions/parsing"
import { Navigation } from "@/components/navigation"
import { AuthGuard } from "@/components/auth-guard"
import { ParsingProgressBar } from "@/components/dashboard/parsing-progress-bar"
import {
  APIError,
  getParsingRuns,
  getDomainsQueue,
  getBlacklist,
  getSuppliers,
  getParsingRun,
  getParsingLogs,
  getModeratorDashboardStats,
} from "@/lib/api"
import { extractRootDomain } from "@/lib/utils-domain"
import { toast } from "sonner"
import { ArrowRight, Play, TrendingUp, AlertCircle, Ban, Activity, Globe, Users, Flame, Sparkles } from "lucide-react"
import type { ParsingRunDTO } from "@/lib/types"

function DashboardPage() {
  const router = useRouter()
  const [keyword, setKeyword] = useState("")
  const [depth, setDepth] = useState(5)
  const [source, setSource] = useState<"google" | "yandex" | "both">("both")
  const [loading, setLoading] = useState(false)
  const [stats, setStats] = useState({
    domainsInQueue: 0,
    enrichmentDomainsInQueue: 0,
    newSuppliers: 0,
    activeRuns: 0,
    blacklistCount: 0,
    moderatorTasks: 0,
  })
  const [recentRuns, setRecentRuns] = useState<ParsingRunDTO[]>([])
  const [parsingProgress, setParsingProgress] = useState<{
    isRunning: boolean
    runId: string | null
    status: string
    resultsCount?: number | null
    source?: string | null
    sourceStats?: {
      google: number
      yandex: number
      both: number
    }
    sourceStatus?: {
      google: { completed: boolean; domains: number }
      yandex: { completed: boolean; domains: number }
    }
    captchaDetected?: boolean // Флаг обнаружения CAPTCHA
    recentDomains?: Array<{
      domain: string
      source: string | null
      createdAt: string
    }> // Последние полученные домены
    progressPercent?: number // Процент выполнения (0-100)
    parsingLogs?: {
      google?: { total_links: number; pages_processed: number; last_links: string[] }
      yandex?: { total_links: number; pages_processed: number; last_links: string[] }
    } | null // Логи парсера с информацией о найденных ссылках
  }>({
    isRunning: false,
    runId: null,
    status: "",
    resultsCount: null,
    source: null,
    sourceStats: undefined,
    sourceStatus: undefined,
    captchaDetected: false,
    recentDomains: [],
    progressPercent: undefined,
    parsingLogs: null,
  })

  // Для отслеживания динамики завершения источников (для определения когда источник завершился)
  const sourceHistoryRef = useRef<{
    google: number[]
    yandex: number[]
  }>({ google: [], yandex: [] })

  // Кэш для доменов (используем useRef для сохранения между рендерами)
  const domainsCacheRef = useRef<Array<{ domain: string; source: string | null; createdAt: string }>>([])

  // Фильтр для доменов по источнику
  const [domainSourceFilter, setDomainSourceFilter] = useState<"all" | "google" | "yandex" | "both">("all")

  useEffect(() => {
    loadDashboardData()
  }, [])

  // Polling для обновления статуса парсинга с адаптивным интервалом
  useEffect(() => {
    if (!parsingProgress.isRunning || !parsingProgress.runId) return

    // Адаптивный интервал: реже опрашиваем для снижения нагрузки
    const getPollingInterval = (status: string) => {
      if (status === "running") return 8000 // 8 секунд
      if (status === "completed" || status === "failed") return 12000 // 12 секунд для финальной проверки
      return 8000 // По умолчанию 8 секунд
    }

    let pollCount = 0 // Счетчик для остановки polling после завершения
    const maxPollAfterCompletion = 3 // Максимум 3 проверки после завершения
    let currentStatus = parsingProgress.status
    let currentInterval = getPollingInterval(currentStatus)
    let intervalId: NodeJS.Timeout | null = null

    const poll = async () => {
      try {
        const runId = parsingProgress.runId
        if (!runId) return

        const run = await getParsingRun(runId)

        // Проверяем, есть ли упоминание CAPTCHA в error_message или error
        const captchaDetected =
          run.error_message?.toLowerCase().includes("captcha") ||
          run.error_message?.toLowerCase().includes("капча") ||
          run.error?.toLowerCase().includes("captcha") ||
          run.error?.toLowerCase().includes("капча") ||
          false

        // Получаем статистику по источникам и последние домены
        let sourceStats: { google: number; yandex: number; both: number } | undefined = undefined
        let recentDomains: Array<{ domain: string; source: string | null; createdAt: string }> = []
        let parsingLogs: {
          google?: { total_links: number; pages_processed: number; last_links: string[] }
          yandex?: { total_links: number; pages_processed: number; last_links: string[] }
        } | null = null

        try {
          const domainsData = await getDomainsQueue({ parsingRunId: runId, limit: 1000 })
          const googleCount = domainsData.entries.filter((e) => e.source === "google").length
          const yandexCount = domainsData.entries.filter((e) => e.source === "yandex").length
          const bothCount = domainsData.entries.filter((e) => e.source === "both").length
          sourceStats = { google: googleCount, yandex: yandexCount, both: bothCount }

          // Получаем parsing logs для более точного расчета прогресса
          try {
            const logsData = await getParsingLogs(runId)
            parsingLogs = logsData.parsing_logs || null
          } catch (logsError) {
            console.debug("Could not fetch parsing logs:", logsError)
            // Не критично, продолжаем без логов
          }

          // Получаем последние 10 доменов, отсортированных по дате создания (новые первыми)
          const allDomains = domainsData.entries
            .sort((a, b) => new Date(b.createdAt).getTime() - new Date(a.createdAt).getTime())
            .map((e) => ({
              domain: e.domain,
              source: e.source || null,
              createdAt: e.createdAt,
            }))

          // Кэширование: обновляем кэш только при появлении новых доменов
          const cachedDomains = domainsCacheRef.current
          const cachedDomainsSet = new Set(cachedDomains.map((d) => `${d.domain}_${d.createdAt}`))
          const newDomains = allDomains.filter((d) => !cachedDomainsSet.has(`${d.domain}_${d.createdAt}`))

          if (newDomains.length > 0 || cachedDomains.length === 0) {
            // Обновляем кэш: добавляем новые домены и обновляем список
            domainsCacheRef.current = allDomains.slice(0, 10)
            recentDomains = domainsCacheRef.current
          } else {
            // Используем кэш, если новых доменов нет
            recentDomains = cachedDomains
          }
        } catch (error) {
          console.error("Error getting source stats:", error)
          // При ошибке используем кэш, если он есть
          if (domainsCacheRef.current.length > 0) {
            recentDomains = domainsCacheRef.current
          }
        }

        // Вычисляем процент выполнения на основе реального количества полученных доменов
        // Если статус "running" - показываем реальный прогресс на основе полученных доменов
        // Если статус "completed" - 100%
        // Если статус "failed" - показываем ошибку
        let progressPercent: number | undefined = undefined
        let sourceStatus:
          | { google: { completed: boolean; domains: number }; yandex: { completed: boolean; domains: number } }
          | undefined = undefined

        if (run.status === "completed") {
          progressPercent = 100
          // При завершении все источники завершены
          if (sourceStats) {
            sourceStatus = {
              google: { completed: true, domains: sourceStats.google },
              yandex: { completed: true, domains: sourceStats.yandex },
            }
          }
        } else if (run.status === "running") {
          const totalDomains = sourceStats ? sourceStats.google + sourceStats.yandex + sourceStats.both : 0
          const depth = run.depth || 10 // По умолчанию 10
          const sourceType = run.source || "google"

          // Извлекаем данные из parsing_logs для более точного расчета прогресса
          // Определяем переменные ДО всех условий, чтобы они были доступны везде
          const googleLinksFromLogs = parsingLogs?.google?.total_links || 0
          const googlePagesFromLogs = parsingLogs?.google?.pages_processed || 0
          const yandexLinksFromLogs = parsingLogs?.yandex?.total_links || 0
          const yandexPagesFromLogs = parsingLogs?.yandex?.pages_processed || 0

          // Реальный прогресс на основе полученных доменов
          // Учитываем, что домены могут сохраняться не сразу, поэтому используем более гибкий расчет
          if (sourceType === "both") {
            // Для "both" считаем прогресс каждого источника отдельно
            const expectedPerSource = depth * 10 // ~10 доменов на страницу
            const googleDomains = sourceStats?.google || 0
            const yandexDomains = sourceStats?.yandex || 0

            // Отслеживаем динамику для определения завершения источников
            if (sourceHistoryRef.current.google.length >= 3) {
              sourceHistoryRef.current.google.shift() // Удаляем старый
            }
            sourceHistoryRef.current.google.push(googleDomains)

            if (sourceHistoryRef.current.yandex.length >= 3) {
              sourceHistoryRef.current.yandex.shift() // Удаляем старый
            }
            sourceHistoryRef.current.yandex.push(yandexDomains)

            // Определяем завершение: если количество не меняется 3 проверки подряд
            const googleHistory = sourceHistoryRef.current.google
            const yandexHistory = sourceHistoryRef.current.yandex
            const googleCompleted =
              googleHistory.length >= 3 &&
              googleHistory[0] === googleHistory[1] &&
              googleHistory[1] === googleHistory[2] &&
              googleDomains > 0
            const yandexCompleted =
              yandexHistory.length >= 3 &&
              yandexHistory[0] === yandexHistory[1] &&
              yandexHistory[1] === yandexHistory[2] &&
              yandexDomains > 0

            sourceStatus = {
              google: { completed: googleCompleted, domains: googleDomains },
              yandex: { completed: yandexCompleted, domains: yandexDomains },
            }

            // Прогресс: каждый источник дает максимум 50%
            // Если доменов еще нет в БД, но парсинг идет - показываем прогресс на основе времени
            let googleProgress = 0
            let yandexProgress = 0

            // Используем parsing_logs для более точного расчета прогресса
            if (googleLinksFromLogs > 0 || googlePagesFromLogs > 0) {
              // Используем данные из логов: количество страниц или ссылок
              const pagesProcessed = googlePagesFromLogs > 0 ? googlePagesFromLogs : Math.ceil(googleLinksFromLogs / 10)
              googleProgress = Math.min((pagesProcessed / depth) * 50, 50)
            } else if (googleDomains > 0) {
              googleProgress = Math.min((googleDomains / expectedPerSource) * 100, 50)
            } else if (googleCompleted) {
              // Если завершен, но доменов нет - значит они еще не сохранены
              googleProgress = 50
            } else {
              // Если доменов нет и не завершен - оцениваем по времени
              const startedAt = run.startedAt ? new Date(run.startedAt).getTime() : null
              if (startedAt) {
                const elapsedSeconds = (Date.now() - startedAt) / 1000
                const estimatedPagesProcessed = Math.floor(elapsedSeconds / 12) // ~12 сек на страницу
                googleProgress = Math.min(Math.floor((estimatedPagesProcessed / depth) * 40), 40) // Максимум 40% для одного источника
              }
            }

            if (yandexLinksFromLogs > 0 || yandexPagesFromLogs > 0) {
              // Используем данные из логов: количество страниц или ссылок
              // Yandex может давать 10-20 ссылок на страницу, используем среднее 15
              const pagesProcessed = yandexPagesFromLogs > 0 ? yandexPagesFromLogs : Math.ceil(yandexLinksFromLogs / 15)
              yandexProgress = Math.min((pagesProcessed / depth) * 50, 50)
            } else if (yandexDomains > 0) {
              yandexProgress = Math.min((yandexDomains / expectedPerSource) * 100, 50)
            } else if (yandexCompleted) {
              // Если завершен, но доменов нет - значит они еще не сохранены
              yandexProgress = 50
            } else {
              // Если доменов нет и не завершен - оцениваем по времени
              const startedAt = run.startedAt ? new Date(run.startedAt).getTime() : null
              if (startedAt) {
                const elapsedSeconds = (Date.now() - startedAt) / 1000
                const estimatedPagesProcessed = Math.floor(elapsedSeconds / 12) // ~12 сек на страницу
                yandexProgress = Math.min(Math.floor((estimatedPagesProcessed / depth) * 40), 40) // Максимум 40% для одного источника
              }
            }

            // Если оба источника завершены, но доменов нет - показываем 95% (почти готово)
            if (googleCompleted && yandexCompleted && totalDomains === 0) {
              progressPercent = 95
            } else {
              progressPercent = Math.floor(googleProgress + yandexProgress)
            }
          } else {
            // Для одного источника
            const expectedTotal = depth * 10

            // Если доменов еще нет в БД, но парсинг идет - показываем прогресс на основе времени
            // Это временная оценка, пока домены не сохранятся в БД
            if (totalDomains === 0) {
              const startedAt = run.startedAt ? new Date(run.startedAt).getTime() : null
              const now = Date.now()
              const elapsedSeconds = startedAt ? (now - startedAt) / 1000 : 0

              // Используем parsing_logs для более точного расчета прогресса
              const linksFromLogs = sourceType === "google" ? googleLinksFromLogs : yandexLinksFromLogs
              const pagesFromLogs = sourceType === "google" ? googlePagesFromLogs : yandexPagesFromLogs

              if (linksFromLogs > 0 || pagesFromLogs > 0) {
                // Используем данные из логов: количество страниц или ссылок
                const linksPerPage = sourceType === "google" ? 10 : 15
                const pagesProcessed = pagesFromLogs > 0 ? pagesFromLogs : Math.ceil(linksFromLogs / linksPerPage)
                progressPercent = Math.min((pagesProcessed / depth) * 80, 80)
              } else if (startedAt && elapsedSeconds > 5) {
                // Оценка прогресса на основе времени
                // Предполагаем, что одна страница обрабатывается примерно за 10-15 секунд
                const estimatedPagesProcessed = Math.floor(elapsedSeconds / 12) // ~12 сек на страницу
                progressPercent = Math.min(Math.floor((estimatedPagesProcessed / depth) * 80), 80)
              } else {
                progressPercent = 0
              }
            } else {
              // Если домены есть - считаем нормально
              progressPercent = Math.min(Math.floor((totalDomains / expectedTotal) * 100), 95)
            }

            // Для одного источника статус простой
            if (sourceType === "google") {
              sourceStatus = {
                google: { completed: false, domains: totalDomains },
                yandex: { completed: true, domains: 0 },
              }
            } else if (sourceType === "yandex") {
              sourceStatus = {
                google: { completed: true, domains: 0 },
                yandex: { completed: false, domains: totalDomains },
              }
            }
          }
        }

        // Автоматический переход на вкладку с капчей при обнаружении
        if (captchaDetected && !parsingProgress.captchaDetected) {
          // Первое обнаружение капчи - показываем уведомление
          toast.warning("⚠️ Обнаружена CAPTCHA! Пожалуйста, откройте окно Chrome и решите капчу.", {
            duration: 10000,
          })
        }

        if (run.status === "completed" || run.status === "failed") {
          pollCount++
          const finalRunId = runId
          setParsingProgress((prev) => ({
            isRunning: pollCount < maxPollAfterCompletion, // Продолжаем polling еще несколько раз после завершения
            runId: pollCount < maxPollAfterCompletion ? runId : null,
            status: run.status,
            resultsCount: run.resultsCount,
            source: run.source || prev.source,
            sourceStats: sourceStats,
            recentDomains: recentDomains,
            progressPercent: progressPercent,
            parsingLogs: parsingLogs || prev.parsingLogs, // Сохраняем логи парсера
          }))

          // Останавливаем polling после нескольких проверок
          if (pollCount >= maxPollAfterCompletion) {
            loadDashboardData()
            if (run.status === "completed") {
              toast.success(`Парсинг завершен. Найдено результатов: ${run.resultsCount || 0}`)
              // Автоматический переход на страницу результатов
              setTimeout(() => {
                router.push(`/parsing-runs/${finalRunId}`)
              }, 1000)
            } else {
              toast.error("Парсинг завершен с ошибкой")
            }
          }
        } else {
          pollCount = 0 // Сбрасываем счетчик, если статус снова running
          setParsingProgress((prev) => ({
            ...prev,
            status: run.status,
            resultsCount: run.resultsCount ?? prev.resultsCount ?? 0,
            source: run.source || prev.source,
            sourceStats: sourceStats || prev.sourceStats,
            sourceStatus: sourceStatus || prev.sourceStatus,
            captchaDetected: captchaDetected || prev.captchaDetected,
            recentDomains: recentDomains.length > 0 ? recentDomains : prev.recentDomains,
            progressPercent: progressPercent,
            parsingLogs: parsingLogs || prev.parsingLogs, // Сохраняем логи парсера
          }))
        }

        // Обновляем интервал при изменении статуса
        if (run.status !== currentStatus) {
          currentStatus = run.status
          const newInterval = getPollingInterval(currentStatus)
          if (newInterval !== currentInterval && intervalId) {
            clearInterval(intervalId)
            currentInterval = newInterval
            intervalId = setInterval(poll, currentInterval)
          }
        }
      } catch (error) {
        console.error("Error checking parsing status:", error)
      }
    }

    // Начинаем polling с начальным интервалом
    intervalId = setInterval(poll, currentInterval)

    return () => {
      if (intervalId) clearInterval(intervalId)
    }
  }, [parsingProgress.isRunning, parsingProgress.runId, router])

  async function loadDashboardData() {
    try {
      const [statsData, recentRunsData] = await Promise.all([
        getModeratorDashboardStats(),
        getParsingRuns({ limit: 10, sort: "created_at", order: "desc" }),
      ])

      setStats({
        domainsInQueue: statsData.domains_in_queue,
        enrichmentDomainsInQueue: statsData.enrichment_domains_in_queue ?? 0,
        newSuppliers: statsData.new_suppliers_week ?? statsData.new_suppliers,
        activeRuns: statsData.active_runs,
        blacklistCount: statsData.blacklist_count,
        moderatorTasks: statsData.open_tasks,
      })
      setRecentRuns(recentRunsData.runs)
    } catch (error) {
      if (!(error instanceof APIError && error.status === 499)) {
        console.error("Error loading dashboard data:", error)
      }
    }
  }

  const handleFormSubmit = async (formData: FormData) => {
    console.log("[v0] handleFormSubmit called")
    console.log("[v0] FormData:", {
      keyword: formData.get("keyword"),
      depth: formData.get("depth"),
      source: formData.get("source"),
    })

    setLoading(true)
    try {
      const result = await handleStartParsing(formData)
      console.log("[v0] handleStartParsing result:", result)

      if (result.success && result.runId) {
        toast.success("Парсинг запущен", {
          description: `Запрос: ${result.keyword}`,
        })

        // Update parsing progress state
        setParsingProgress({
          isRunning: true,
          runId: result.runId,
          status: "running",
          resultsCount: 0,
          source: (formData.get("source") as string) || "both",
          sourceStats: undefined,
          sourceStatus: undefined,
          captchaDetected: false,
          recentDomains: [],
          progressPercent: 0,
          parsingLogs: null,
        })

        // Clear keyword after successful start
        setKeyword("")

        // Reload dashboard data
        loadDashboardData()
      } else {
        toast.error("Ошибка запуска парсинга", {
          description: "Не удалось получить runId",
        })
      }
    } catch (error) {
      console.error("[v0] Error in handleFormSubmit:", error)
      toast.error("Ошибка запуска парсинга", {
        description: error instanceof Error ? error.message : "Неизвестная ошибка",
      })
    } finally {
      setLoading(false)
    }
  }

  const exampleKeywords = ["кирпич", "цемент", "труба", "арматура"]

  return (
    <div className="min-h-screen bg-gradient-to-br from-slate-50 to-blue-50/30">
      <Navigation />
      <motion.main
        initial={{ opacity: 0, y: 20 }}
        animate={{ opacity: 1, y: 0 }}
        transition={{ duration: 0.5 }}
        className="container mx-auto px-6 py-12 max-w-7xl"
      >
        {/* Заголовок с градиентом */}
        <motion.div
          initial={{ opacity: 0, y: -20 }}
          animate={{ opacity: 1, y: 0 }}
          transition={{ duration: 0.6 }}
          className="text-center mb-12"
        >
          <h1 className="text-6xl font-bold text-gradient mb-4">B2B Platform</h1>
          <p className="text-xl text-muted-foreground">Интеллектуальная система парсинга и модерации поставщиков</p>
        </motion.div>

        {/* Статистика */}
        <motion.div
          initial={{ opacity: 0, y: 20 }}
          animate={{ opacity: 1, y: 0 }}
          transition={{ duration: 0.7, delay: 0.2 }}
          className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-6 gap-6 mb-8"
        >
          <motion.div whileHover={{ scale: 1.02, y: -2 }} transition={{ type: "spring", stiffness: 300 }}>
            <Card
              role="button"
              tabIndex={0}
              onClick={() => router.push("/moderator/tasks")}
              onKeyDown={(e) => {
                if (e.key === "Enter" || e.key === " ") router.push("/moderator/tasks")
              }}
              className="card-hover relative overflow-hidden bg-gradient-to-br from-orange-50 via-amber-100 to-red-100 border-orange-200 cursor-pointer"
            >
              {/* Flame border */}
              <motion.div
                className="pointer-events-none absolute inset-0 rounded-xl"
                animate={{ opacity: [0.65, 0.95, 0.65] }}
                transition={{ duration: 1.2, repeat: Infinity, ease: "easeInOut" }}
                style={{
                  padding: 2,
                  background:
                    "conic-gradient(from 0deg, rgba(255,35,0,0.95), rgba(255,120,0,0.85), rgba(255,220,140,0.75), rgba(255,120,0,0.85), rgba(255,35,0,0.95))",
                  WebkitMask:
                    "linear-gradient(#000 0 0) content-box, linear-gradient(#000 0 0)",
                  WebkitMaskComposite: "xor",
                  maskComposite: "exclude" as any,
                }}
              />
              <motion.div
                className="pointer-events-none absolute inset-0 rounded-xl opacity-60 blur-xl"
                animate={{
                  rotate: [0, 4, -4, 0],
                  scale: [1, 1.02, 1.01, 1],
                }}
                transition={{ duration: 2.0, ease: "easeInOut", repeat: Infinity }}
                style={{
                  background:
                    "radial-gradient(closest-side at 20% 10%, rgba(255,90,0,0.55), rgba(255,200,80,0.22), rgba(255,255,255,0))",
                }}
              />
              <motion.div
                className="pointer-events-none absolute inset-0 rounded-xl opacity-55 blur-xl"
                animate={{
                  rotate: [0, -6, 6, 0],
                  scale: [1, 1.01, 1.03, 1],
                }}
                transition={{ duration: 2.7, ease: "easeInOut", repeat: Infinity }}
                style={{
                  background:
                    "radial-gradient(closest-side at 80% 30%, rgba(255,40,0,0.45), rgba(255,150,0,0.18), rgba(255,255,255,0))",
                }}
              />
              {/* Flame tongues at top edge */}
              <motion.div
                className="pointer-events-none absolute left-2 right-2 top-0 h-10 opacity-50 blur-lg"
                animate={{ y: [0, -3, 0], opacity: [0.45, 0.7, 0.45] }}
                transition={{ duration: 0.9, repeat: Infinity, ease: "easeInOut" }}
                style={{
                  background:
                    "radial-gradient(12px 20px at 10% 90%, rgba(255,120,0,0.9), rgba(255,120,0,0)) , radial-gradient(14px 22px at 30% 90%, rgba(255,60,0,0.85), rgba(255,60,0,0)) , radial-gradient(16px 24px at 50% 90%, rgba(255,180,60,0.8), rgba(255,180,60,0)) , radial-gradient(14px 22px at 70% 90%, rgba(255,80,0,0.85), rgba(255,80,0,0)) , radial-gradient(12px 20px at 90% 90%, rgba(255,150,40,0.8), rgba(255,150,40,0))",
                }}
              />

              <CardContent className="relative p-6 min-h-[104px] flex items-center">
                <div className="w-full flex items-center justify-between">
                  <div>
                    <p className="text-sm text-orange-700 font-medium">Задачи</p>
                    <p className="text-3xl font-bold text-orange-900 mt-1">{stats.moderatorTasks}</p>
                  </div>
                  <motion.div
                    className="h-12 w-12 rounded-full bg-orange-200 flex items-center justify-center"
                    animate={{
                      boxShadow: [
                        "0 0 0px rgba(255,120,0,0)",
                        "0 0 22px rgba(255,120,0,0.55)",
                        "0 0 0px rgba(255,120,0,0)",
                      ],
                    }}
                    transition={{ duration: 1.0, repeat: Infinity, ease: "easeInOut" }}
                  >
                    <Flame className="h-6 w-6 text-orange-700" />
                  </motion.div>
                </div>
              </CardContent>
            </Card>
          </motion.div>

          <motion.div whileHover={{ scale: 1.02, y: -2 }} transition={{ type: "spring", stiffness: 300 }}>
            <Card
              role="button"
              tabIndex={0}
              onClick={() => router.push("/domains")}
              onKeyDown={(e) => {
                if (e.key === "Enter" || e.key === " ") router.push("/domains")
              }}
              className="card-hover bg-gradient-to-br from-blue-50 to-blue-100 border-blue-200 cursor-pointer"
            >
              <CardContent className="p-6 min-h-[104px] flex items-center">
                <div className="w-full flex items-center justify-between">
                  <div>
                    <p className="text-sm text-blue-600 font-medium">Домены в очереди</p>
                    <p className="text-3xl font-bold text-blue-900 mt-1">{stats.domainsInQueue}</p>
                  </div>
                  <div className="h-12 w-12 rounded-full bg-blue-200 flex items-center justify-center">
                    <Globe className="h-6 w-6 text-blue-700" />
                  </div>
                </div>
              </CardContent>
            </Card>
          </motion.div>

          <motion.div whileHover={{ scale: 1.02, y: -2 }} transition={{ type: "spring", stiffness: 300 }}>
            <Card
              role="button"
              tabIndex={0}
              onClick={() => router.push("/domains")}
              onKeyDown={(e) => {
                if (e.key === "Enter" || e.key === " ") router.push("/domains")
              }}
              className="card-hover bg-gradient-to-br from-cyan-50 to-cyan-100 border-cyan-200 cursor-pointer"
            >
              <CardContent className="p-6 min-h-[104px] flex items-center">
                <div className="w-full flex items-center justify-between">
                  <div>
                    <p className="text-sm text-cyan-700 font-medium">Обогащение</p>
                    <p className="text-3xl font-bold text-cyan-900 mt-1">{stats.enrichmentDomainsInQueue}</p>
                    <p className="text-xs text-cyan-700 mt-1">Домены в очереди на ИНН/email</p>
                  </div>
                  <div className="h-12 w-12 rounded-full bg-cyan-200 flex items-center justify-center">
                    <Sparkles className="h-6 w-6 text-cyan-700" />
                  </div>
                </div>
              </CardContent>
            </Card>
          </motion.div>

          <motion.div whileHover={{ scale: 1.02, y: -2 }} transition={{ type: "spring", stiffness: 300 }}>
            <Card
              role="button"
              tabIndex={0}
              onClick={() => router.push("/suppliers?recentDays=7")}
              onKeyDown={(e) => {
                if (e.key === "Enter" || e.key === " ") router.push("/suppliers?recentDays=7")
              }}
              className="card-hover bg-gradient-to-br from-green-50 to-green-100 border-green-200 cursor-pointer"
            >
              <CardContent className="p-6 min-h-[104px] flex items-center">
                <div className="w-full flex items-center justify-between">
                  <div>
                    <p className="text-sm text-green-600 font-medium">Новые поставщики за неделю</p>
                    <p className="text-3xl font-bold text-green-900 mt-1">{stats.newSuppliers}</p>
                  </div>
                  <div className="h-12 w-12 rounded-full bg-green-200 flex items-center justify-center">
                    <Users className="h-6 w-6 text-green-700" />
                  </div>
                </div>
              </CardContent>
            </Card>
          </motion.div>

          <motion.div whileHover={{ scale: 1.02, y: -2 }} transition={{ type: "spring", stiffness: 300 }}>
            <Card
              role="button"
              tabIndex={0}
              onClick={() => router.push("/parsing-runs?status=running")}
              onKeyDown={(e) => {
                if (e.key === "Enter" || e.key === " ") router.push("/parsing-runs?status=running")
              }}
              className="card-hover bg-gradient-to-br from-purple-50 to-purple-100 border-purple-200 cursor-pointer"
            >
              <CardContent className="p-6 min-h-[104px] flex items-center">
                <div className="w-full flex items-center justify-between">
                  <div>
                    <p className="text-sm text-purple-600 font-medium">Активные запуски</p>
                    <p className="text-3xl font-bold text-purple-900 mt-1">{stats.activeRuns}</p>
                  </div>
                  <div className="h-12 w-12 rounded-full bg-purple-200 flex items-center justify-center">
                    <Activity className="h-6 w-6 text-purple-700" />
                  </div>
                </div>
              </CardContent>
            </Card>
          </motion.div>

          <motion.div whileHover={{ scale: 1.02, y: -2 }} transition={{ type: "spring", stiffness: 300 }}>
            <Card
              role="button"
              tabIndex={0}
              onClick={() => router.push("/blacklist")}
              onKeyDown={(e) => {
                if (e.key === "Enter" || e.key === " ") router.push("/blacklist")
              }}
              className="card-hover bg-gradient-to-br from-red-50 to-red-100 border-red-200 cursor-pointer"
            >
              <CardContent className="p-6 min-h-[104px] flex items-center">
                <div className="w-full flex items-center justify-between">
                  <div>
                    <p className="text-sm text-red-600 font-medium">Blacklist</p>
                    <p className="text-3xl font-bold text-red-900 mt-1">{stats.blacklistCount}</p>
                  </div>
                  <div className="h-12 w-12 rounded-full bg-red-200 flex items-center justify-center">
                    <Ban className="h-6 w-6 text-red-700" />
                  </div>
                </div>
              </CardContent>
            </Card>
          </motion.div>
        </motion.div>
        {/* Новый парсинг */}
        <div className="mb-4">
          <h1 className="text-3xl font-bold mb-2 text-balance">Запустить новый парсинг</h1>

          <Card className="border-2">
            <CardContent className="pt-4 space-y-3">
              <form action={handleFormSubmit} className="space-y-3">
                <div className="grid gap-3">
                  <div>
                    <Label htmlFor="keyword" className="text-sm mb-1 block">
                      Ключевое слово
                    </Label>
                    <Input
                      id="keyword"
                      name="keyword"
                      autoComplete="off"
                      placeholder="Введите ключевое слово..."
                      value={keyword}
                      onChange={(e) => setKeyword(e.target.value)}
                      className="text-base h-10"
                    />
                    <div className="flex gap-1 flex-wrap mt-1.5">
                      <span className="text-xs text-muted-foreground">Примеры:</span>
                      {exampleKeywords.map((word) => (
                        <Button
                          key={word}
                          variant="outline"
                          size="sm"
                          className="h-7 text-xs bg-transparent"
                          type="button"
                          aria-label={`Пример ключевого слова ${word}`}
                          onClick={() => setKeyword(word)}
                        >
                          {word}
                        </Button>
                      ))}
                    </div>
                  </div>

                  <div className="grid grid-cols-1 md:grid-cols-2 gap-3">
                    <div>
                      <Label htmlFor="depth" className="text-sm mb-1 block">
                        Глубина парсинга
                      </Label>
                      <Input
                        id="depth"
                        name="depth"
                        type="number"
                        min={1}
                        value={depth}
                        onChange={(e) => setDepth(Number.parseInt(e.target.value) || 1)}
                        className="text-base h-10"
                      />
                      <p className="text-xs text-muted-foreground mt-1">Количество страниц результатов</p>
                    </div>

                    <div>
                      <Label className="text-sm mb-1 block">Источник</Label>
                      <div className="flex gap-1">
                        <input type="hidden" name="source" value={source} />
                        <Button
                          variant={source === "google" ? "default" : "outline"}
                          type="button"
                          onClick={() => setSource("google")}
                          className="flex-1 h-10 text-sm"
                        >
                          Google
                        </Button>
                        <Button
                          variant={source === "yandex" ? "default" : "outline"}
                          type="button"
                          onClick={() => setSource("yandex")}
                          className="flex-1 h-10 text-sm"
                        >
                          Яндекс
                        </Button>
                        <Button
                          variant={source === "both" ? "default" : "outline"}
                          type="button"
                          onClick={() => setSource("both")}
                          className="flex-1 h-10 text-sm"
                        >
                          Оба
                        </Button>
                      </div>
                    </div>
                  </div>
                </div>

                <Button
                  type="submit"
                  disabled={loading || parsingProgress.isRunning || !keyword.trim()}
                  size="lg"
                  className="w-full h-10 text-sm"
                >
                  <Play className="mr-2 h-4 w-4" />
                  {loading
                    ? "Запускаем..."
                    : parsingProgress.isRunning
                      ? "Парсинг выполняется..."
                      : "Запустить парсинг"}
                </Button>
              </form>
            </CardContent>
          </Card>

          <ParsingProgressBar
            isRunning={parsingProgress.isRunning}
            status={parsingProgress.status}
            progressPercent={parsingProgress.progressPercent}
            resultsCount={parsingProgress.resultsCount}
            source={parsingProgress.source}
            sourceStats={parsingProgress.sourceStats}
            sourceStatus={parsingProgress.sourceStatus}
            captchaDetected={parsingProgress.captchaDetected}
            recentDomains={parsingProgress.recentDomains}
            parsingLogs={parsingProgress.parsingLogs}
            keyword={keyword}
            depth={depth}
          />
        </div>

        {/* Быстрые действия */}

        {/* Последние запуски */}
        <div className="mb-8">
          <div className="flex items-center justify-between mb-3">
            <h2 className="text-xl font-bold">Последние запуски</h2>
            <Button variant="ghost" size="sm" className="h-8 text-xs" onClick={() => router.push("/parsing-runs?status=running")}>
              Все запуски
              <ArrowRight className="ml-2 h-3 w-3" />
            </Button>
          </div>

          {recentRuns.length === 0 ? (
            <Card>
              <CardContent className="py-6 text-center text-muted-foreground text-sm">
                Нет запусков парсинга
              </CardContent>
            </Card>
          ) : (
            <div className="flex gap-2 overflow-x-auto pb-2">
              {recentRuns.map((run) => {
                const runId = run.runId || run.run_id || ""
                const createdAt = run.createdAt || run.created_at || ""
                return (
                  <Card
                    key={runId}
                    className="min-w-[200px] cursor-pointer hover:border-primary transition-colors"
                    onClick={() => runId && router.push(`/parsing-runs/${runId}`)}
                  >
                    <CardContent className="pt-3">
                      <div className="flex items-start justify-between mb-1.5">
                        <div className="font-semibold text-sm">{run.keyword}</div>
                        <Badge
                          variant={
                            run.status === "completed"
                              ? "default"
                              : run.status === "running"
                                ? "outline"
                                : "destructive"
                          }
                          className={
                            run.status === "completed"
                              ? "bg-green-600 hover:bg-green-700 text-white text-xs"
                              : run.status === "failed"
                                ? "bg-red-600 hover:bg-red-700 text-white text-xs"
                                : "text-xs"
                          }
                        >
                          {run.status === "completed" ? "✓" : run.status === "running" ? "⏳" : "✗"}
                        </Badge>
                      </div>
                      <div className="text-xs text-muted-foreground">
                        {createdAt
                          ? new Date(createdAt).toLocaleDateString("ru-RU", {
                              day: "numeric",
                              month: "short",
                            })
                          : "—"}
                      </div>
                      {run.resultsCount !== null && run.resultsCount !== undefined && (
                        <div className="text-xs font-medium mt-1">{run.resultsCount} результатов</div>
                      )}
                    </CardContent>
                  </Card>
                )
              })}
            </div>
          )}
        </div>

        {/* CTA кнопки */}
        <div className="grid grid-cols-1 md:grid-cols-3 gap-3">
          <Button
            variant="outline"
            size="lg"
            className="h-12 text-sm justify-start bg-transparent"
            onClick={() => router.push("/parsing-runs?status=running")}
          >
            <TrendingUp className="mr-2 h-4 w-4" />
            Обработать очередь
          </Button>

          <Button
            variant="outline"
            size="lg"
            className="h-12 text-sm justify-start bg-transparent"
            onClick={() => router.push("/suppliers")}
          >
            <AlertCircle className="mr-2 h-4 w-4" />
            Проверить новых
          </Button>

          <Button
            variant="outline"
            size="lg"
            className="h-12 text-sm justify-start bg-transparent"
            onClick={() => router.push("/blacklist")}
          >
            <Ban className="mr-2 h-4 w-4" />
            Управление Blacklist
          </Button>
        </div>
      </motion.main>
    </div>
  )
}

// Оборачиваем компонент в AuthGuard
export default function DashboardPageWithAuth() {
  return (
    <AuthGuard allowedRoles={["moderator"]}>
      <DashboardPage />
    </AuthGuard>
  )
}
