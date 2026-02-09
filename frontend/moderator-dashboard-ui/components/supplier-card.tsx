"use client"

import { useState } from "react"
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card"
import { Badge } from "@/components/ui/badge"
import { Button } from "@/components/ui/button"
import { Separator } from "@/components/ui/separator"
import { Accordion, AccordionContent, AccordionItem, AccordionTrigger } from "@/components/ui/accordion"
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from "@/components/ui/select"
import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogFooter,
  DialogHeader,
  DialogTitle,
} from "@/components/ui/dialog"
import { Textarea } from "@/components/ui/textarea"
import { Label } from "@/components/ui/label"
import type { SupplierDTO } from "@/lib/types"
import {
  formatCurrency,
  formatDate,
  calculatePercentageChange,
  getRiskLevel,
  getRiskColor,
  getRiskEmoji,
  formatOKVEDCode,
  calculateReliabilityRating,
  calculateReliabilityScore,
  ratingToStars,
  type ReliabilityLevel,
} from "@/lib/format-utils"
import { addToBlacklist, getCheckoData, updateSupplier } from "@/lib/api"
import { toast } from "sonner"
import { Edit, Ban, Tag, Globe, Phone, MapPin, Mail, Star, RefreshCw, ExternalLink, CheckCircle2 } from "lucide-react"
import { AreaChart, Area, LineChart, Line, XAxis, YAxis, CartesianGrid, Tooltip, ResponsiveContainer, Legend } from "recharts"
import { TrendingDown, TrendingUp, Info, Download } from "lucide-react"
import Link from "next/link"
import { extractRootDomain } from "@/lib/utils-domain"
import { useRouter } from "next/navigation"
import { cn } from "@/lib/utils"

// Types for Checko data
interface CheckoData {
  rating?: number
  Рейтинг?: number
  _finances?: Record<string, FinanceYear>
  _legal?: LegalData
  _inspections?: InspectionData
  _enforcements?: EnforcementData
  Учред?: Founder[] | { ФЛ?: Founder[] }
  Руковод?: Leader[]
  ОКВЭД?: OKVED[] | OKVED
  ОКВЭДДоп?: OKVED[]
  timestamp?: number
}

interface FinanceYear {
  "2110"?: number // Revenue
  "2400"?: number // Profit
}

interface LegalData {
  asPlaintiff?: number
  asDefendant?: number
  total?: number
  sum?: number
}

interface InspectionData {
  total?: number
  violations?: number
}

interface EnforcementData {
  count?: number
}

interface Founder {
  name?: string
  ФИО?: string
  ИНН?: string
  inn?: string
  share?: number
  Доля?: number | { Номинал?: number; Процент?: number }
  Стоимость?: number
  Номинал?: number
  Процент?: number
  ДатаЗаписи?: string
}

interface Leader {
  name?: string
  ИНН?: string
  position?: string
  Должность?: string
}

interface OKVED {
  Код?: string
  Наим?: string
  Вероятн?: string // Вероятность (основной/дополнительный)
}

interface SupplierCardProps {
  supplier: SupplierDTO
  onSupplierUpdate?: (updatedSupplier: SupplierDTO) => void
}

export function SupplierCard({ supplier, onSupplierUpdate }: SupplierCardProps) {
  const router = useRouter()
  const [addingToBlacklist, setAddingToBlacklist] = useState(false)
  const [blacklistDialogOpen, setBlacklistDialogOpen] = useState(false)
  const [blacklistReason, setBlacklistReason] = useState("")
  const [loadingCheckoData, setLoadingCheckoData] = useState(false)
  
  // Parse checkoData if available
  let checkoData: CheckoData | null = null
  if (supplier.checkoData) {
    try {
      checkoData = JSON.parse(supplier.checkoData)
    } catch (error) {
      console.error("Failed to parse checkoData:", error)
      console.error("checkoData value:", supplier.checkoData?.substring(0, 100))
      checkoData = null
    }
  }
  
  // Normalize OKVED data (can be object or array)
  const normalizedOKVED: OKVED[] = (() => {
    if (!checkoData) return []
    const okved = checkoData.ОКВЭД
    if (!okved) return []
    if (Array.isArray(okved)) return okved
    if (typeof okved === 'object' && okved.Код) return [okved]
    return []
  })()
  
  // Add additional OKVED if exists
  if (checkoData?.ОКВЭДДоп && Array.isArray(checkoData.ОКВЭДДоп)) {
    normalizedOKVED.push(...checkoData.ОКВЭДДоп)
  }
  
  // Normalize founders data (extract from Учред.ФЛ if needed)
  const normalizedFounders: Founder[] = (() => {
    if (!checkoData?.Учред) return []
    const учред = checkoData.Учред
    if (Array.isArray(учред)) return учред
    if (typeof учред === 'object' && учред.ФЛ && Array.isArray(учред.ФЛ)) {
      return учред.ФЛ.map((фл: any) => ({
        ФИО: фл.ФИО,
        ИНН: фл.ИНН,
        Доля: фл.Доля,
        ДатаЗаписи: фл.ДатаЗаписи,
      }))
    }
    return []
  })()
  
  // Prepare financial chart data (sorted ascending: oldest to newest)
  const chartData = prepareChartData(supplier, checkoData)
  const latestCheckoYear = (() => {
    if (!checkoData?._finances) return null
    const years = Object.keys(checkoData._finances).filter(Boolean)
    if (!years.length) return null
    return years.sort((a, b) => Number(a) - Number(b)).pop() || null
  })()
  const derivedFinanceYear = supplier.financeYear ?? (latestCheckoYear ? Number(latestCheckoYear) : null)
  
  // Initialize selectedYear with the last (newest) year
  const [selectedYear, setSelectedYear] = useState<string | null>(
    chartData.length > 0 ? chartData[chartData.length - 1].year : null
  )
  const [financeMode, setFinanceMode] = useState<"both" | "revenue" | "profit">("both")
  
  // Check if Checko data exists and is fresh (less than 24 hours old)
  const hasFreshCheckoData = checkoData && checkoData.timestamp && 
    (Date.now() / 1000 - checkoData.timestamp) < 24 * 60 * 60

  
  function openBlacklistDialog() {
    if (!supplier.domain) {
      toast.error("Домен не указан")
      return
    }
    setBlacklistReason("")
    setBlacklistDialogOpen(true)
  }

  async function handleAddToBlacklist() {
    if (!supplier.domain) {
      toast.error("Домен не указан")
      return
    }
    
    try {
      setAddingToBlacklist(true)
      const normalizedDomain = extractRootDomain(supplier.domain)
      await addToBlacklist({ 
        domain: normalizedDomain,
        reason: blacklistReason.trim() || null
      })
      toast.success("Домен добавлен в blacklist")
      setBlacklistDialogOpen(false)
      setBlacklistReason("")
    } catch (error) {
      toast.error("Ошибка при добавлении в blacklist")
      console.error("Error adding to blacklist:", error)
    } finally {
      setAddingToBlacklist(false)
    }
  }

  async function handleLoadCheckoData() {
    if (!supplier.inn || supplier.inn.length < 10) {
      toast.error("ИНН не указан или некорректен")
      return
    }

    // Проверяем, есть ли уже свежие данные Checko (менее 24 часов)
    if (hasFreshCheckoData) {
      toast.info("Данные Checko уже загружены и актуальны (менее 24 часов)")
      return
    }

    try {
      setLoadingCheckoData(true)
      
      // Загружаем данные Checko (бэкенд кэширует на 24 часа, поэтому не будет лишних запросов)
      const checkoResponse = await getCheckoData(supplier.inn, false)
      
      // Обновляем поставщика с данными Checko
      const updatedSupplier = await updateSupplier(supplier.id, {
        name: checkoResponse.name || supplier.name,
        inn: supplier.inn,
        email: supplier.email,
        domain: supplier.domain,
        address: supplier.address,
        type: supplier.type,
        // Checko fields
        ogrn: checkoResponse.ogrn || null,
        kpp: checkoResponse.kpp || null,
        okpo: checkoResponse.okpo || null,
        companyStatus: checkoResponse.companyStatus || null,
        registrationDate: checkoResponse.registrationDate || null,
        legalAddress: checkoResponse.legalAddress || null,
        phone: checkoResponse.phone || null,
        website: checkoResponse.website || null,
        vk: checkoResponse.vk || null,
        telegram: checkoResponse.telegram || null,
        authorizedCapital: checkoResponse.authorizedCapital ?? null,
        revenue: checkoResponse.revenue ?? null,
        profit: checkoResponse.profit ?? null,
        financeYear: checkoResponse.financeYear ?? null,
        legalCasesCount: checkoResponse.legalCasesCount ?? null,
        legalCasesSum: checkoResponse.legalCasesSum ?? null,
        legalCasesAsPlaintiff: checkoResponse.legalCasesAsPlaintiff ?? null,
        legalCasesAsDefendant: checkoResponse.legalCasesAsDefendant ?? null,
        checkoData: checkoResponse.checkoData || null,
      })

      toast.success("Данные Checko успешно загружены и обновлены")
      
      // Обновляем supplier в родительском компоненте или перезагружаем страницу
      if (onSupplierUpdate) {
        onSupplierUpdate(updatedSupplier)
      } else {
        router.refresh()
      }
    } catch (error: any) {
      console.error("Error loading Checko data:", error)
      if (error?.message) {
        toast.error(`Ошибка загрузки данных Checko: ${error.message}`)
      } else {
        toast.error("Ошибка загрузки данных Checko")
      }
    } finally {
      setLoadingCheckoData(false)
    }
  }

  // Get current year financial data from checkoData if supplier fields are empty
  const currentYearData = derivedFinanceYear && checkoData?._finances?.[derivedFinanceYear.toString()]
  const currentRevenue = supplier.revenue ?? (currentYearData as any)?.["2110"] ?? 0
  const currentProfit = supplier.profit ?? (currentYearData as any)?.["2400"] ?? 0

  // Get previous year data for comparison
  const previousYear = derivedFinanceYear ? derivedFinanceYear - 1 : null
  const previousYearData = previousYear && checkoData?._finances?.[previousYear.toString()]
  const revenueChange = (previousYearData as any)?.["2110"]
    ? calculatePercentageChange(currentRevenue, (previousYearData as any)["2110"])
    : ""
  const profitChange = (previousYearData as any)?.["2400"]
    ? calculatePercentageChange(currentProfit, (previousYearData as any)["2400"])
    : ""

  // Get legal data from checkoData if supplier fields are empty
  const legalAsPlaintiff = supplier.legalCasesAsPlaintiff ?? checkoData?._legal?.asPlaintiff ?? 0
  const legalAsDefendant = supplier.legalCasesAsDefendant ?? checkoData?._legal?.asDefendant ?? 0
  const legalTotal = supplier.legalCasesCount ?? checkoData?._legal?.total ?? 0
  const legalSum = supplier.legalCasesSum ?? checkoData?._legal?.sum ?? 0
  
  // Calculate risk level based on arbitration, inspections, and enforcements
  const inspectionsCount = checkoData?._inspections?.total ?? 0
  const enforcementsCount = checkoData?._enforcements?.count ?? 0
  const hasEnforcements = enforcementsCount > 0
  
  // Check if there are actual cases (not just total count)
  const hasActualCases = legalAsPlaintiff > 0 || legalAsDefendant > 0
  const hasManyCases = hasActualCases && (legalTotal > 10 || legalAsDefendant > 5)
  const hasManyInspections = inspectionsCount > 5
  
  // Large sum threshold: 1 billion rubles
  const largeSumThreshold = 1_000_000_000
  const hasLargeSum = legalSum > largeSumThreshold
  
  // Risk level calculation
  let riskLevel: "low" | "medium" | "high" = "low"
  let riskExplanation = ""
  
  if (hasEnforcements || hasLargeSum) {
    riskLevel = "high"
    const reasons: string[] = []
    if (hasEnforcements) reasons.push("исполнительных производств")
    if (hasLargeSum) reasons.push("большой суммы исков")
    riskExplanation = `из-за ${reasons.join(" и ")}`
  } else if (hasManyInspections || (hasManyCases && hasActualCases)) {
    riskLevel = "medium"
    const reasons: string[] = []
    if (hasManyInspections) reasons.push("количества проверок")
    if (hasManyCases) reasons.push("судебных споров")
    riskExplanation = `из-за ${reasons.join(" и ")}`
  } else {
    riskLevel = "low"
    riskExplanation = "ограничений не выявлено"
  }
  
  // Calculate financial profile subtitle
  const financialProfileSubtitle = calculateFinancialProfileSubtitle(chartData)
  
  // Generate moderator recommendation based on risk level
  const getModeratorRecommendation = (level: "low" | "medium" | "high"): string => {
    switch (level) {
      case "high":
        return "рассмотреть добавление в blacklist"
      case "medium":
        return "усиленный мониторинг"
      case "low":
        return "стандартный мониторинг"
    }
  }
  
  const moderatorRecommendation = getModeratorRecommendation(riskLevel)
  
  // Calculate reliability score with detailed breakdown
  const reliabilityResult = calculateReliabilityScore(checkoData, supplier)
  const reliabilityRating = reliabilityResult.score
  const reliabilityLevel = reliabilityResult.level
  const ratingStars = ratingToStars(reliabilityRating)

  return (
    <>
    <Card className="w-full shadow-lg transition-all duration-300 hover:shadow-xl">
      {/* SECTION 1: HEADER */}
      <CardHeader className="space-y-4">
        <div className="flex flex-wrap items-start justify-between gap-3">
          <div className="flex flex-wrap items-center gap-3">
            <CardTitle className="text-2xl font-bold md:text-3xl">{supplier.name}</CardTitle>
            <Badge
              variant={supplier.type === "supplier" ? "default" : "secondary"}
              className={
                supplier.type === "supplier" ? "bg-green-500 hover:bg-green-600" : "bg-purple-500 hover:bg-purple-600"
              }
            >
              {supplier.type === "supplier" ? "Поставщик" : "Реселлер"}
            </Badge>
            {/* Reliability Rating */}
            <Badge variant="outline" className="gap-1">
              <Star className="h-3 w-3 fill-yellow-400 text-yellow-400" />
              {reliabilityResult.score}
              {ratingStars > 0 && (
                <span className="ml-1 text-xs">
                  {"★".repeat(ratingStars)}
                </span>
              )}
            </Badge>
          </div>
        </div>

        {/* Metadata */}
        <div className="flex flex-wrap items-center gap-4 text-sm text-muted-foreground">
          {supplier.legalAddress && (
            <div className="flex items-center gap-1">
              <MapPin className="h-4 w-4" />
              <span className="line-clamp-1">{supplier.legalAddress}</span>
            </div>
          )}
          {supplier.phone && (
            <a href={`tel:${supplier.phone}`} className="flex items-center gap-1 hover:text-foreground">
              <Phone className="h-4 w-4" />
              <span>{supplier.phone}</span>
            </a>
          )}
          {supplier.website && (
            <a
              href={supplier.website}
              target="_blank"
              rel="noopener noreferrer"
              className="flex items-center gap-1 hover:text-foreground"
            >
              <Globe className="h-4 w-4" />
              <span>Сайт</span>
            </a>
          )}
          {supplier.vk && (
            <a
              href={supplier.vk}
              target="_blank"
              rel="noopener noreferrer"
              className="flex items-center gap-1 hover:text-foreground"
            >
              <span className="font-semibold">VK</span>
            </a>
          )}
          {supplier.telegram && (
            <a
              href={supplier.telegram}
              target="_blank"
              rel="noopener noreferrer"
              className="flex items-center gap-1 hover:text-foreground"
            >
              <span className="font-semibold">TG</span>
            </a>
          )}
          {supplier.inn && (
            <a
              href={`https://checko.ru/search?query=${supplier.inn}`}
              target="_blank"
              rel="noopener noreferrer"
              className="flex items-center gap-1 hover:text-foreground"
              title="Открыть на Checko.ru"
            >
              <ExternalLink className="h-4 w-4" />
              <span className="font-semibold">Checko</span>
            </a>
          )}
        </div>

        {(() => {
          const emails = (supplier.emails && supplier.emails.length ? supplier.emails : supplier.email ? [supplier.email] : [])
          if (!emails.length) return null
          return (
            <div className="flex flex-col gap-1 text-sm text-muted-foreground">
              {emails.slice(0, 5).map((em, idx) => (
                <div key={`${em}-${idx}`} className="flex items-center gap-1">
                  <Mail className="h-4 w-4" />
                  <a href={`mailto:${em}`} className="hover:text-foreground">
                    {em}
                  </a>
                </div>
              ))}
            </div>
          )
        })()}

        {/* Company details */}
        <div className="grid grid-cols-2 gap-2 text-xs text-muted-foreground md:grid-cols-4">
          {supplier.inn && (
            <div>
              <span className="font-medium">ИНН:</span> {supplier.inn}
            </div>
          )}
          {supplier.ogrn && (
            <div>
              <span className="font-medium">ОГРН:</span> {supplier.ogrn}
            </div>
          )}
          {supplier.kpp && (
            <div>
              <span className="font-medium">КПП:</span> {supplier.kpp}
            </div>
          )}
          {supplier.registrationDate && (
            <div>
              <span className="font-medium">Дата рег.:</span> {formatDate(supplier.registrationDate)}
            </div>
          )}
        </div>
        {supplier.dataStatus && supplier.dataStatus !== "complete" && (
          <div className="text-xs text-amber-700 bg-amber-50 border border-amber-200 rounded px-2 py-1 inline-flex">
            Неполные данные (ожидает Checko)
          </div>
        )}
      </CardHeader>

      <CardContent className="space-y-6">
        {/* SECTION 2: FINANCIAL PROFILE — Modern AreaChart design */}
        {(() => {
          const lastYear = chartData.length > 0 ? chartData[chartData.length - 1] : null
          const prevYear = chartData.length > 1 ? chartData[chartData.length - 2] : null

          function formatShortRub(n: number) {
            if (!Number.isFinite(n)) return "—"
            const abs = Math.abs(n)
            if (abs >= 1_000_000_000) return `${(n / 1_000_000_000).toFixed(1)} млрд`
            if (abs >= 1_000_000) return `${(n / 1_000_000).toFixed(1)} млн`
            if (abs >= 1_000) return `${(n / 1_000).toFixed(1)} тыс`
            return `${n}`
          }

          function deltaPct(prev: number, curr: number) {
            if (!Number.isFinite(prev) || !Number.isFinite(curr) || prev === 0) return null
            return ((curr - prev) / Math.abs(prev)) * 100
          }

          const revDelta = lastYear && prevYear ? deltaPct(prevYear.revenue, lastYear.revenue) : null
          const profDelta = lastYear && prevYear ? deltaPct(prevYear.profit, lastYear.profit) : null

          const healthFlags: { text: string; tone: "good" | "warn" | "bad" }[] = []
          if (lastYear && prevYear) {
            if (lastYear.revenue > prevYear.revenue) healthFlags.push({ text: "выручка растёт", tone: "good" })
            else healthFlags.push({ text: "выручка снизилась", tone: "warn" })
            if (lastYear.profit >= 0) healthFlags.push({ text: "прибыль положительная", tone: "good" })
            else healthFlags.push({ text: "убыток", tone: "bad" })
            const margin = lastYear.revenue ? (lastYear.profit / lastYear.revenue) * 100 : null
            if (margin != null) {
              if (margin >= 10) healthFlags.push({ text: `маржа ~${margin.toFixed(1)}%`, tone: "good" })
              else if (margin >= 3) healthFlags.push({ text: `маржа ~${margin.toFixed(1)}%`, tone: "warn" })
              else healthFlags.push({ text: `маржа ~${margin.toFixed(1)}%`, tone: "bad" })
            }
          }

          const financeModes = [
            { key: "both" as const, label: "Оба" },
            { key: "revenue" as const, label: "Выручка" },
            { key: "profit" as const, label: "Прибыль" },
          ]

          const visibleAreas = {
            revenue: financeMode === "both" || financeMode === "revenue",
            profit: financeMode === "both" || financeMode === "profit",
          }

          return (
            <div className="space-y-4">
              <div className="flex flex-col gap-3 md:flex-row md:items-start md:justify-between">
                <div>
                  <h3 className="text-lg font-semibold">Финансы</h3>
                  {financialProfileSubtitle && (
                    <p className="text-sm text-muted-foreground mt-1">{financialProfileSubtitle}</p>
                  )}
                </div>
                {chartData.length > 0 && (
                  <div className="flex flex-wrap gap-2">
                    {financeModes.map((m) => (
                      <Button
                        key={m.key}
                        variant={financeMode === m.key ? "default" : "secondary"}
                        className="rounded-full"
                        size="sm"
                        onClick={() => setFinanceMode(m.key)}
                      >
                        {m.label}
                      </Button>
                    ))}
                  </div>
                )}
              </div>

              {lastYear ? (
                <>
                  {/* KPI tiles */}
                  <div className="grid gap-3 md:grid-cols-3">
                    <div className="rounded-2xl border bg-card p-4">
                      <div className="text-xs text-muted-foreground">Выручка ({lastYear.year})</div>
                      <div className="mt-1 flex items-baseline justify-between gap-3">
                        <div className="text-2xl font-semibold">{formatShortRub(lastYear.revenue)}</div>
                        <div className="flex items-center gap-1 text-sm">
                          {revDelta != null && revDelta >= 0 ? (
                            <TrendingUp className="h-4 w-4 text-green-600" />
                          ) : revDelta != null ? (
                            <TrendingDown className="h-4 w-4 text-red-600" />
                          ) : null}
                          <span className="tabular-nums">
                            {revDelta == null ? "" : `${revDelta >= 0 ? "+" : ""}${revDelta.toFixed(1)}%`}
                          </span>
                        </div>
                      </div>
                      <div className="mt-1 text-xs text-muted-foreground">{formatCurrency(lastYear.revenue)}</div>
                    </div>

                    <div className="rounded-2xl border bg-card p-4">
                      <div className="text-xs text-muted-foreground">Прибыль ({lastYear.year})</div>
                      <div className="mt-1 flex items-baseline justify-between gap-3">
                        <div className="text-2xl font-semibold">{formatShortRub(lastYear.profit)}</div>
                        <div className="flex items-center gap-1 text-sm">
                          {profDelta != null && profDelta >= 0 ? (
                            <TrendingUp className="h-4 w-4 text-green-600" />
                          ) : profDelta != null ? (
                            <TrendingDown className="h-4 w-4 text-red-600" />
                          ) : null}
                          <span className="tabular-nums">
                            {profDelta == null ? "" : `${profDelta >= 0 ? "+" : ""}${profDelta.toFixed(1)}%`}
                          </span>
                        </div>
                      </div>
                      <div className="mt-1 text-xs text-muted-foreground">{formatCurrency(lastYear.profit)}</div>
                    </div>

                    {healthFlags.length > 0 && (
                      <div className="rounded-2xl border bg-card p-4">
                        <div className="flex items-center justify-between">
                          <div className="text-xs text-muted-foreground">Быстрая интерпретация</div>
                          <Info className="h-4 w-4 text-muted-foreground" />
                        </div>
                        <div className="mt-2 flex flex-wrap gap-2">
                          {healthFlags.map((f, idx) => (
                            <Badge
                              key={idx}
                              variant={f.tone === "good" ? "default" : f.tone === "warn" ? "secondary" : "destructive"}
                              className="rounded-full"
                            >
                              {f.tone === "good" ? "✅" : f.tone === "warn" ? "⚠️" : "🛑"} {f.text}
                            </Badge>
                          ))}
                        </div>
                        <div className="mt-2 text-xs text-muted-foreground">
                          UI-подсказки, не юридическое заключение.
                        </div>
                      </div>
                    )}
                  </div>

                  {/* Combined AreaChart */}
                  {chartData.length > 1 && (
                    <div className="rounded-2xl border bg-card p-4">
                      <div className="flex flex-col gap-1 md:flex-row md:items-center md:justify-between">
                        <div>
                          <div className="text-sm font-medium">Динамика по годам</div>
                          <div className="text-xs text-muted-foreground">Наведите курсор для точных значений</div>
                        </div>
                        <div className="text-xs text-muted-foreground">
                          Период: {chartData[0].year}–{chartData[chartData.length - 1].year}
                        </div>
                      </div>
                      <div className="mt-3 h-[280px]">
                        <ResponsiveContainer width="100%" height="100%">
                          <AreaChart data={chartData} margin={{ top: 10, right: 14, left: 6, bottom: 0 }}>
                            <CartesianGrid strokeDasharray="3 3" />
                            <XAxis dataKey="year" tickLine={false} axisLine={false} />
                            <YAxis
                              tickLine={false}
                              axisLine={false}
                              tickFormatter={(v) => formatShortRub(Number(v))}
                              width={70}
                            />
                            <Tooltip
                              formatter={(value: any, name: any) => {
                                const label = name === "revenue" ? "Выручка" : "Прибыль"
                                return [formatCurrency(Number(value)), label]
                              }}
                              labelFormatter={(label) => `Год: ${label}`}
                            />
                            <Legend formatter={(value) => (value === "revenue" ? "Выручка" : "Прибыль")} />
                            {visibleAreas.revenue && (
                              <Area type="monotone" dataKey="revenue" stroke="rgb(59, 130, 246)" fill="rgb(59, 130, 246)" fillOpacity={0.18} strokeWidth={2} />
                            )}
                            {visibleAreas.profit && (
                              <Area type="monotone" dataKey="profit" stroke="rgb(34, 197, 94)" fill="rgb(34, 197, 94)" fillOpacity={0.18} strokeWidth={2} />
                            )}
                          </AreaChart>
                        </ResponsiveContainer>
                      </div>
                    </div>
                  )}
                </>
              ) : (
                <p className="text-sm text-muted-foreground">Финансовые данные отсутствуют</p>
              )}
            </div>
          )
        })()}

        <Separator />

        {/* SECTION 3: RELIABILITY RATING */}
        <div className="space-y-4">
          <h3 className="text-lg font-semibold">Оценка надежности</h3>
          
          {/* Rating Badge and Score */}
          <div className="flex items-center gap-3">
            <Badge
              variant={reliabilityLevel === "high" ? "default" : reliabilityLevel === "medium" ? "secondary" : "destructive"}
              className={cn(
                "text-sm font-semibold",
                reliabilityLevel === "high" ? "bg-green-500 hover:bg-green-600" :
                reliabilityLevel === "medium" ? "bg-yellow-500 hover:bg-yellow-600" :
                "bg-red-500 hover:bg-red-600"
              )}
            >
              {reliabilityLevel === "high" ? "Высокая" : reliabilityLevel === "medium" ? "Средняя" : "Низкая"}
            </Badge>
            <span className="text-sm text-muted-foreground">
              {reliabilityResult.score}/100
            </span>
          </div>
          
          {/* Rating Score Bar */}
          <div className="relative h-8 bg-muted rounded-full overflow-hidden">
            <div 
              className={cn(
                "h-full flex items-center justify-end pr-3 transition-all duration-500",
                reliabilityLevel === "high" ? "bg-green-500" : 
                reliabilityLevel === "medium" ? "bg-yellow-500" : 
                "bg-red-500"
              )}
              style={{ width: `${reliabilityResult.score}%` }}
            >
              <span className="text-sm font-bold text-white">
                {reliabilityResult.score}
              </span>
            </div>
          </div>
          
          {/* Factors by Category */}
          <div className="space-y-3">
            {/* Positive Factors */}
            {reliabilityResult.positive.length > 0 && (
              <div className="space-y-2">
                <div className="flex items-center gap-2">
                  <Badge variant="outline" className="bg-green-50 text-green-700 border-green-200">
                    Положительные ({reliabilityResult.positive.length})
                  </Badge>
                </div>
                <div className="space-y-1 pl-2">
                  {reliabilityResult.positive.map((reason, index) => (
                    <div key={index} className="flex items-center gap-2 text-sm">
                      <CheckCircle2 className="h-4 w-4 text-green-600 flex-shrink-0" />
                      <span>{reason}</span>
                    </div>
                  ))}
                </div>
              </div>
            )}
            
            {/* Attention Factors */}
            {reliabilityResult.attention.length > 0 && (
              <div className="space-y-2">
                <div className="flex items-center gap-2">
                  <Badge variant="outline" className="bg-yellow-50 text-yellow-700 border-yellow-200">
                    Требуют внимания ({reliabilityResult.attention.length})
                  </Badge>
                </div>
                <div className="space-y-1 pl-2">
                  {reliabilityResult.attention.map((reason, index) => (
                    <div key={index} className="flex items-center gap-2 text-sm">
                      <span className="text-yellow-600">⚠️</span>
                      <span>{reason}</span>
                    </div>
                  ))}
                </div>
              </div>
            )}
            
            {/* Negative Factors */}
            {reliabilityResult.negative.length > 0 && (
              <div className="space-y-2">
                <div className="flex items-center gap-2">
                  <Badge variant="outline" className="bg-red-50 text-red-700 border-red-200">
                    Негативные ({reliabilityResult.negative.length})
                  </Badge>
                </div>
                <div className="space-y-1 pl-2">
                  {reliabilityResult.negative.map((reason, index) => (
                    <div key={index} className="flex items-center gap-2 text-sm">
                      <span className="text-red-600">❌</span>
                      <span>{reason}</span>
                    </div>
                  ))}
                </div>
              </div>
            )}
            
            {reliabilityResult.positive.length === 0 && 
             reliabilityResult.attention.length === 0 && 
             reliabilityResult.negative.length === 0 && (
              <p className="text-sm text-muted-foreground">Недостаточно данных для оценки</p>
            )}
          </div>
          
          {/* Disclaimer */}
          <p className="text-xs text-muted-foreground">
            Все рейтинги, а также оценка фактов и рисков рассчитываются на основе рекомендаций ФНС по проявлению коммерческой осмотрительности, являются оценочным мнением нашего сервиса и не являются рекомендациями для принятия каких-либо решений.
          </p>
        </div>

        <Separator />

        {/* SECTION 4: OKVED */}
        {normalizedOKVED.length > 0 && (
          <>
            <div className="space-y-3">
              <h3 className="text-lg font-semibold">ОКВЭД</h3>
              <Accordion type="single" collapsible className="w-full">
                <AccordionItem value="okved-all" className="border-b">
                  <AccordionTrigger className="hover:no-underline">
                    <span className="text-sm">
                      Виды деятельности ({normalizedOKVED.length})
                    </span>
                  </AccordionTrigger>
                  <AccordionContent>
                    <div className="space-y-3 pt-2">
                      {normalizedOKVED.map((okved, index) => {
                        const isMain = index === 0 // First one is main
                        return (
                          <div key={index} className="rounded-md border p-3 space-y-1">
                            <div className="flex items-center gap-2">
                              {isMain && (
                                <Badge variant="default" className="bg-blue-500 hover:bg-blue-600 text-xs">
                                  Основной
                                </Badge>
                              )}
                              <span className="font-mono text-sm font-semibold">{formatOKVEDCode(okved.Код)}</span>
                            </div>
                            {okved.Наим && (
                              <div className="text-sm text-muted-foreground">{okved.Наим}</div>
                            )}
                            {okved.Вероятн && (
                              <div className="text-xs text-muted-foreground">Тип: {okved.Вероятн}</div>
                            )}
                          </div>
                        )
                      })}
                    </div>
                  </AccordionContent>
                </AccordionItem>
              </Accordion>
            </div>
            <Separator />
          </>
        )}

        {/* SECTION 5: RISKS */}
        <div className="space-y-3">
          <div className="space-y-2">
            <div className="flex items-center gap-2">
              <span className="text-sm text-muted-foreground">Вердикт:</span>
              <Badge
                variant={riskLevel === "low" ? "default" : riskLevel === "medium" ? "secondary" : "destructive"}
                className={cn(
                  riskLevel === "low" && "bg-green-500 hover:bg-green-600",
                  riskLevel === "medium" && "bg-yellow-500 hover:bg-yellow-600",
                  riskLevel === "high" && "bg-red-500 hover:bg-red-600"
                )}
              >
                риск {riskLevel === "low" ? "низкий" : riskLevel === "medium" ? "средний" : "высокий"}
              </Badge>
            </div>
            {riskExplanation && (
              <p className="text-xs text-muted-foreground">{riskExplanation}</p>
            )}
          </div>

          <div className={`rounded-lg p-4 ${getRiskColor(riskLevel)}`}>
            <div className="flex items-start gap-3">
              <span className="text-2xl">{getRiskEmoji(riskLevel)}</span>
              <div className="flex-1 space-y-2">
                <div className="space-y-2 text-sm">
                  <div>
                    <span className="text-muted-foreground">Арбитраж: </span>
                    <span className="font-medium">
                      дел всего {legalTotal}, истец {legalAsPlaintiff}, ответчик {legalAsDefendant}
                    </span>
                  </div>
                  {inspectionsCount > 0 && (
                    <div>
                      <span className="text-muted-foreground">Проверки: </span>
                      <span className="font-medium">
                        {inspectionsCount}
                        {checkoData?._inspections?.violations ? (
                          <span> ({checkoData._inspections.violations} нарушений)</span>
                        ) : null}
                      </span>
                    </div>
                  )}
                  {enforcementsCount > 0 && (
                    <div>
                      <span className="text-muted-foreground">Исп. производства: </span>
                      <span className="font-medium">{enforcementsCount}</span>
                    </div>
                  )}
                  {legalSum > 0 && (
                    <div>
                      <span className="text-muted-foreground">Сумма исков: </span>
                      <span className={cn(
                        "font-medium",
                        hasLargeSum && "text-red-600 font-semibold"
                      )}>
                        {formatCurrency(legalSum)}
                      </span>
                    </div>
                  )}
                </div>
              </div>
            </div>
          </div>
        </div>

        <Separator />

        {/* SECTION 6: FOUNDERS */}
        {normalizedFounders.length > 0 && (
          <>
            <div className="space-y-3">
              <h3 className="font-semibold">Учредители</h3>
              <div className="space-y-2">
                {normalizedFounders.map((founder, index) => {
                  const founderName = founder.ФИО || founder.name || "Не указано"
                  const founderInn = founder.ИНН || founder.inn
                  const доля = founder.Доля
                  const founderShare = typeof доля === 'object' ? доля.Процент : (typeof доля === 'number' ? доля : founder.share)
                  const founderCost = typeof доля === 'object' ? доля.Номинал : founder.Стоимость || founder.Номинал
                  
                  return (
                    <div key={index} className="flex items-center gap-2 rounded-md bg-muted/50 p-2 text-sm">
                      <span className="text-lg">👤</span>
                      <div className="flex-1">
                        {founderInn ? (
                          <a
                            href={`https://checko.ru/person/${founderInn}`}
                            target="_blank"
                            rel="noopener noreferrer"
                            className="text-blue-600 hover:text-blue-800 hover:underline font-medium"
                          >
                            {founderName}
                          </a>
                        ) : (
                          <span className="font-medium">{founderName}</span>
                        )}
                        {founderShare && (
                          <span className="ml-2 text-muted-foreground">({founderShare}%)</span>
                        )}
                        {founderCost && (
                          <span className="ml-2 text-xs text-muted-foreground">{formatCurrency(founderCost)}</span>
                        )}
                        {founderInn && (
                          <div className="mt-1 text-xs text-muted-foreground">ИНН: {founderInn}</div>
                        )}
                        {founder.ДатаЗаписи && (
                          <div className="mt-1 text-xs text-muted-foreground">с {formatDate(founder.ДатаЗаписи)}</div>
                        )}
                      </div>
                    </div>
                  )
                })}
              </div>
            </div>
            <Separator />
          </>
        )}

        {/* SECTION 7: LEADERS */}
        {checkoData?.Руковод && checkoData.Руковод.length > 0 && (
          <>
            <div className="space-y-3">
              <h3 className="font-semibold">Руководители</h3>
              <div className="space-y-2">
                {checkoData.Руковод.map((leader, index) => {
                  const leaderName = leader.name || (leader as any).Наим || "Не указано"
                  const leaderInn = leader.ИНН || (leader as any).inn
                  const leaderPosition = leader.position || leader.Должность
                  
                  return (
                    <div key={index} className="flex items-center gap-2 rounded-md bg-muted/50 p-2 text-sm">
                      <span className="text-lg">👔</span>
                      <div className="flex-1">
                        {leaderInn ? (
                          <a
                            href={`https://checko.ru/person/${leaderInn}`}
                            target="_blank"
                            rel="noopener noreferrer"
                            className="text-blue-600 hover:text-blue-800 hover:underline"
                          >
                            {leaderName}
                          </a>
                        ) : (
                          <span>{leaderName}</span>
                        )}
                        {leaderPosition && (
                          <span className="ml-2 text-muted-foreground">— {leaderPosition}</span>
                        )}
                        {leaderInn && (
                          <span className="ml-2 text-xs text-muted-foreground">ИНН: {leaderInn}</span>
                        )}
                      </div>
                    </div>
                  )
                })}
              </div>
            </div>
            <Separator />
          </>
        )}

        {/* SECTION 8: ACTIONS */}
        <div className="space-y-3">
          <div>
            <span className="text-sm text-muted-foreground">Рекомендуемое действие модератора: </span>
            <span className="text-sm font-medium">{moderatorRecommendation}</span>
          </div>
          <div className="flex flex-wrap gap-3 justify-end">
            <Button asChild variant="default" className="gap-2">
              <Link href={`/suppliers/${supplier.id}/edit`}>
                <Edit className="h-4 w-4" />
                Редактировать
              </Link>
            </Button>
            {supplier.inn && supplier.inn.length >= 10 && (
              <Button
                variant="outline"
                className="gap-2"
                onClick={handleLoadCheckoData}
                disabled={loadingCheckoData || !!hasFreshCheckoData}
              >
                <RefreshCw className={`h-4 w-4 ${loadingCheckoData ? "animate-spin" : ""}`} />
                {loadingCheckoData 
                  ? "Загрузка..." 
                  : hasFreshCheckoData 
                    ? "Данные актуальны" 
                    : "Загрузить данные Checko"}
              </Button>
            )}
            <Button 
              variant="destructive" 
              className="gap-2"
              onClick={openBlacklistDialog}
              disabled={!supplier.domain}
            >
              <Ban className="h-4 w-4" />
              Blacklist
            </Button>
            <Button asChild variant="outline" className="gap-2 bg-transparent">
              <Link href={`/suppliers/${supplier.id}/keywords`}>
                <Tag className="h-4 w-4" />
                Ключевые слова
              </Link>
            </Button>
          </div>
        </div>
      </CardContent>
    </Card>
      {/* Blacklist Dialog */}
      <Dialog open={blacklistDialogOpen} onOpenChange={setBlacklistDialogOpen}>
        <DialogContent>
          <DialogHeader>
            <DialogTitle>Добавить домен в черный список</DialogTitle>
            <DialogDescription>
              Добавить "{supplier.domain}" в blacklist?
            </DialogDescription>
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
                setBlacklistReason("")
              }}
            >
              Отмена
            </Button>
            <Button
              onClick={handleAddToBlacklist}
              disabled={addingToBlacklist}
              variant="destructive"
            >
              {addingToBlacklist ? "Добавление..." : "Добавить"}
            </Button>
          </DialogFooter>
        </DialogContent>
      </Dialog>
    </>
  )
}

// Helper function to prepare chart data
function prepareChartData(supplier: SupplierDTO, checkoData: CheckoData | null) {
  const data: { year: string; revenue: number; profit: number }[] = []

  // Add historical data from checkoData
  if (checkoData?._finances) {
    const years = Object.keys(checkoData._finances).sort()
    years.forEach((year) => {
      const yearData = checkoData._finances![year]
      data.push({
        year,
        revenue: yearData["2110"] ?? 0,
        profit: yearData["2400"] ?? 0,
      })
    })
  }

  // Add current year data if not already included
  if (supplier.financeYear) {
    const currentYearExists = data.some((d) => d.year === supplier.financeYear!.toString())
    if (!currentYearExists) {
      const currentYearData = checkoData?._finances?.[supplier.financeYear.toString()]
      data.push({
        year: supplier.financeYear.toString(),
        revenue: supplier.revenue ?? currentYearData?.["2110"] ?? 0,
        profit: supplier.profit ?? currentYearData?.["2400"] ?? 0,
      })
    }
  }

  // Sort ascending (oldest to newest) - like Checko.ru
  return data.sort((a, b) => a.year.localeCompare(b.year))
}

// Helper function to calculate financial profile subtitle
function calculateFinancialProfileSubtitle(chartData: { year: string; revenue: number; profit: number }[]): string {
  if (chartData.length < 3) {
    return ""
  }

  // Get last 3 years (sorted ascending - oldest to newest, so last 3 are newest)
  const last3Years = chartData.slice(-3)
  
  // Check if revenue and profit are growing (comparing newer to older)
  let revenueGrowing = true
  let profitGrowing = true
  let hasLosses = false

  // Compare from older to newer (index 0 is oldest, index 2 is newest)
  for (let i = 0; i < last3Years.length - 1; i++) {
    const older = last3Years[i]      // Older year
    const newer = last3Years[i + 1]  // Newer year
    
    if (newer.revenue <= older.revenue) {
      revenueGrowing = false
    }
    if (newer.profit <= older.profit) {
      profitGrowing = false
    }
    if (newer.profit < 0 || older.profit < 0) {
      hasLosses = true
    }
  }

  if (revenueGrowing && profitGrowing && !hasLosses) {
    return "Стабильный рост, компания прибыльна"
  }

  return ""
}
