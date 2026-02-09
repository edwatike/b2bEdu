/**
 * SupplierFinancials Component
 * 
 * Финансовый блок с интерактивными графиками и метриками
 * Включает: выручка, прибыль, уставный капитал, тренды
 */

"use client"

import { useState, useMemo } from "react"
import { motion } from "framer-motion"
import { TrendingUp, TrendingDown, DollarSign, BarChart3, Info } from "lucide-react"
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card"
import { Badge } from "@/components/ui/badge"
import { Button } from "@/components/ui/button"
import {
  AreaChart, Area, XAxis, YAxis, CartesianGrid, Tooltip,
  ResponsiveContainer, Legend,
} from "recharts"
import type { SupplierDTO } from "@/lib/types"

interface SupplierFinancialsProps {
  supplier: SupplierDTO
}

export function SupplierFinancials({ supplier }: SupplierFinancialsProps) {
  const [financeMode, setFinanceMode] = useState<"both" | "revenue" | "profit">("both")

  const toNumber = (value: unknown): number | null => {
    if (value === null || value === undefined || value === "") return null
    const num = Number(value)
    if (Number.isNaN(num)) return null
    return num
  }

  let checkoData: any | null = null
  if (supplier.checkoData) {
    try {
      checkoData = JSON.parse(supplier.checkoData)
    } catch {
      checkoData = null
    }
  }

  // Build chart data from real Checko _finances
  const chartData = useMemo(() => {
    const data: { year: string; revenue: number; profit: number }[] = []
    if (checkoData?._finances) {
      const years = Object.keys(checkoData._finances).sort()
      years.forEach((year) => {
        const yd = checkoData._finances[year]
        data.push({ year, revenue: yd["2110"] ?? 0, profit: yd["2400"] ?? 0 })
      })
    }
    if (supplier.financeYear) {
      const ys = supplier.financeYear.toString()
      if (!data.some((d) => d.year === ys)) {
        const cyd = checkoData?._finances?.[ys]
        data.push({
          year: ys,
          revenue: supplier.revenue ?? cyd?.["2110"] ?? 0,
          profit: supplier.profit ?? cyd?.["2400"] ?? 0,
        })
      }
    }
    return data.sort((a, b) => a.year.localeCompare(b.year))
  }, [checkoData, supplier.financeYear, supplier.revenue, supplier.profit])

  const lastYear = chartData.length > 0 ? chartData[chartData.length - 1] : null
  const prevYear = chartData.length > 1 ? chartData[chartData.length - 2] : null

  const derivedAuthorizedCapital = toNumber(supplier.authorizedCapital ?? checkoData?.УстКап?.Сумма ?? null)

  // Helpers
  function formatShortRub(n: number) {
    if (!Number.isFinite(n)) return "—"
    const abs = Math.abs(n)
    if (abs >= 1_000_000_000) return `${(n / 1_000_000_000).toFixed(1)} млрд`
    if (abs >= 1_000_000) return `${(n / 1_000_000).toFixed(1)} млн`
    if (abs >= 1_000) return `${(n / 1_000).toFixed(0)} тыс`
    return `${n}`
  }

  const fmtCurrency = (value: number | null | undefined) => {
    if (value === null || value === undefined) return "—"
    return new Intl.NumberFormat("ru-RU", {
      style: "currency", currency: "RUB",
      minimumFractionDigits: 0, maximumFractionDigits: 0,
    }).format(value)
  }

  const formatNumber = (value: number | null | undefined) => {
    if (value === null || value === undefined) return "—"
    return new Intl.NumberFormat("ru-RU").format(value)
  }

  function deltaPct(prev: number, curr: number) {
    if (!Number.isFinite(prev) || !Number.isFinite(curr) || prev === 0) return null
    return ((curr - prev) / Math.abs(prev)) * 100
  }

  const revDelta = lastYear && prevYear ? deltaPct(prevYear.revenue, lastYear.revenue) : null
  const profDelta = lastYear && prevYear ? deltaPct(prevYear.profit, lastYear.profit) : null
  const profitMargin = lastYear && lastYear.revenue
    ? (lastYear.profit / lastYear.revenue) * 100
    : null

  // Health flags
  const healthFlags: { text: string; tone: "good" | "warn" | "bad" }[] = []
  if (lastYear && prevYear) {
    if (lastYear.revenue > prevYear.revenue) healthFlags.push({ text: "выручка растёт", tone: "good" })
    else healthFlags.push({ text: "выручка снизилась", tone: "warn" })
    if (lastYear.profit >= 0) healthFlags.push({ text: "прибыль положительная", tone: "good" })
    else healthFlags.push({ text: "убыток", tone: "bad" })
    if (profitMargin != null) {
      if (profitMargin >= 10) healthFlags.push({ text: `маржа ~${profitMargin.toFixed(1)}%`, tone: "good" })
      else if (profitMargin >= 3) healthFlags.push({ text: `маржа ~${profitMargin.toFixed(1)}%`, tone: "warn" })
      else healthFlags.push({ text: `маржа ~${profitMargin.toFixed(1)}%`, tone: "bad" })
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
    <div className="space-y-6">
      {/* Header with mode toggle */}
      <div className="flex flex-col gap-3 md:flex-row md:items-center md:justify-between">
        <div className="flex items-center gap-2">
          <BarChart3 className="h-5 w-5 text-blue-600" />
          <h3 className="text-lg font-semibold text-neutral-900">Финансы</h3>
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
          <div className="grid grid-cols-1 md:grid-cols-3 gap-4">
            {/* Выручка */}
            <motion.div initial={{ opacity: 0, y: 20 }} animate={{ opacity: 1, y: 0 }} transition={{ duration: 0.4 }}>
              <Card className="bg-gradient-to-br from-blue-50 to-white border-blue-200">
                <CardContent className="p-6">
                  <div className="flex items-start justify-between mb-2">
                    <div className="h-10 w-10 rounded-lg bg-blue-100 flex items-center justify-center">
                      <DollarSign className="h-5 w-5 text-blue-600" />
                    </div>
                    {revDelta != null && (
                      <div className={`flex items-center gap-1 text-sm font-medium ${revDelta >= 0 ? "text-green-600" : "text-red-600"}`}>
                        {revDelta >= 0 ? <TrendingUp className="h-4 w-4" /> : <TrendingDown className="h-4 w-4" />}
                        {revDelta >= 0 ? "+" : ""}{revDelta.toFixed(1)}%
                      </div>
                    )}
                  </div>
                  <p className="text-sm text-neutral-600 mb-1">Выручка ({lastYear.year})</p>
                  <p className="text-2xl font-bold text-neutral-900">{formatShortRub(lastYear.revenue)}</p>
                  <p className="text-xs text-neutral-500 mt-1">{fmtCurrency(lastYear.revenue)}</p>
                </CardContent>
              </Card>
            </motion.div>

            {/* Прибыль */}
            <motion.div initial={{ opacity: 0, y: 20 }} animate={{ opacity: 1, y: 0 }} transition={{ duration: 0.4, delay: 0.1 }}>
              <Card className={`bg-gradient-to-br ${lastYear.profit >= 0 ? "from-green-50 to-white border-green-200" : "from-red-50 to-white border-red-200"}`}>
                <CardContent className="p-6">
                  <div className="flex items-start justify-between mb-2">
                    <div className={`h-10 w-10 rounded-lg flex items-center justify-center ${lastYear.profit >= 0 ? "bg-green-100" : "bg-red-100"}`}>
                      <TrendingUp className={`h-5 w-5 ${lastYear.profit >= 0 ? "text-green-600" : "text-red-600"}`} />
                    </div>
                    {profDelta != null && (
                      <div className={`flex items-center gap-1 text-sm font-medium ${profDelta >= 0 ? "text-green-600" : "text-red-600"}`}>
                        {profDelta >= 0 ? <TrendingUp className="h-4 w-4" /> : <TrendingDown className="h-4 w-4" />}
                        {profDelta >= 0 ? "+" : ""}{profDelta.toFixed(1)}%
                      </div>
                    )}
                  </div>
                  <p className="text-sm text-neutral-600 mb-1">Прибыль ({lastYear.year})</p>
                  <p className={`text-2xl font-bold ${lastYear.profit >= 0 ? "text-green-700" : "text-red-700"}`}>
                    {formatShortRub(lastYear.profit)}
                  </p>
                  <p className="text-xs text-neutral-500 mt-1">
                    {profitMargin != null ? `маржа ${profitMargin.toFixed(1)}%` : "чистая прибыль"}
                  </p>
                </CardContent>
              </Card>
            </motion.div>

            {/* Health / Уставный капитал */}
            <motion.div initial={{ opacity: 0, y: 20 }} animate={{ opacity: 1, y: 0 }} transition={{ duration: 0.4, delay: 0.2 }}>
              {healthFlags.length > 0 ? (
                <Card className="bg-gradient-to-br from-slate-50 to-white border-slate-200 h-full">
                  <CardContent className="p-6">
                    <div className="flex items-center justify-between mb-3">
                      <p className="text-sm text-neutral-600">Быстрая оценка</p>
                      <Info className="h-4 w-4 text-neutral-400" />
                    </div>
                    <div className="flex flex-wrap gap-2 mb-3">
                      {healthFlags.map((f, idx) => (
                        <Badge
                          key={idx}
                          variant={f.tone === "good" ? "default" : f.tone === "warn" ? "secondary" : "destructive"}
                          className="rounded-full text-xs"
                        >
                          {f.tone === "good" ? "✅" : f.tone === "warn" ? "⚠️" : "🛑"} {f.text}
                        </Badge>
                      ))}
                    </div>
                    {derivedAuthorizedCapital != null && (
                      <div className="pt-2 border-t">
                        <p className="text-xs text-neutral-500">Уставный капитал</p>
                        <p className="text-sm font-semibold">{fmtCurrency(derivedAuthorizedCapital)}</p>
                      </div>
                    )}
                  </CardContent>
                </Card>
              ) : (
                <Card className="bg-gradient-to-br from-purple-50 to-white border-purple-200">
                  <CardContent className="p-6">
                    <div className="flex items-start justify-between mb-2">
                      <div className="h-10 w-10 rounded-lg bg-purple-100 flex items-center justify-center">
                        <BarChart3 className="h-5 w-5 text-purple-600" />
                      </div>
                    </div>
                    <p className="text-sm text-neutral-600 mb-1">Уставный капитал</p>
                    <p className="text-2xl font-bold text-neutral-900">{fmtCurrency(derivedAuthorizedCapital)}</p>
                    <p className="text-xs text-neutral-500 mt-1">зарегистрированный</p>
                  </CardContent>
                </Card>
              )}
            </motion.div>
          </div>

          {/* AreaChart — real historical data */}
          {chartData.length > 1 && (
            <motion.div initial={{ opacity: 0, y: 20 }} animate={{ opacity: 1, y: 0 }} transition={{ duration: 0.5, delay: 0.3 }}>
              <Card>
                <CardHeader className="pb-2">
                  <div className="flex flex-col gap-1 md:flex-row md:items-center md:justify-between">
                    <CardTitle className="text-base">Динамика по годам</CardTitle>
                    <span className="text-xs text-neutral-500">
                      Период: {chartData[0].year}–{chartData[chartData.length - 1].year}
                    </span>
                  </div>
                </CardHeader>
                <CardContent>
                  <div className="h-[280px]">
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
                            return [fmtCurrency(Number(value)), label]
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
                </CardContent>
              </Card>
            </motion.div>
          )}
        </>
      ) : (
        <Card>
          <CardContent className="p-6">
            <p className="text-neutral-500">Финансовые данные отсутствуют</p>
          </CardContent>
        </Card>
      )}

      {/* Судебные разбирательства */}
      {(supplier.legalCasesCount !== null || supplier.legalCasesSum !== null) && (
        <motion.div initial={{ opacity: 0, y: 20 }} animate={{ opacity: 1, y: 0 }} transition={{ duration: 0.5, delay: 0.5 }}>
          <Card className="bg-gradient-to-br from-orange-50 to-white border-orange-200">
            <CardHeader>
              <CardTitle className="text-base flex items-center gap-2">
                <TrendingDown className="h-4 w-4 text-orange-600" />
                Судебные разбирательства
              </CardTitle>
            </CardHeader>
            <CardContent>
              <div className="grid grid-cols-2 md:grid-cols-4 gap-4">
                <div>
                  <p className="text-xs text-neutral-600 mb-1">Всего дел</p>
                  <p className="text-xl font-bold text-neutral-900">{formatNumber(supplier.legalCasesCount)}</p>
                </div>
                <div>
                  <p className="text-xs text-neutral-600 mb-1">Сумма исков</p>
                  <p className="text-xl font-bold text-neutral-900">{fmtCurrency(supplier.legalCasesSum)}</p>
                </div>
                <div>
                  <p className="text-xs text-neutral-600 mb-1">Истец</p>
                  <p className="text-xl font-bold text-blue-600">{formatNumber(supplier.legalCasesAsPlaintiff)}</p>
                </div>
                <div>
                  <p className="text-xs text-neutral-600 mb-1">Ответчик</p>
                  <p className="text-xl font-bold text-red-600">{formatNumber(supplier.legalCasesAsDefendant)}</p>
                </div>
              </div>
            </CardContent>
          </Card>
        </motion.div>
      )}
    </div>
  )
}
