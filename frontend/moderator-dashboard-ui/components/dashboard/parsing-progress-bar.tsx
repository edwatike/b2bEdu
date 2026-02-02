"use client"

import { motion, AnimatePresence } from "framer-motion"
import { Card, CardContent } from "@/components/ui/card"
import { Badge } from "@/components/ui/badge"
import { Globe, Zap, CheckCircle2, AlertTriangle, Loader2, ExternalLink } from "lucide-react"
import { cn } from "@/lib/utils"

interface ParsingProgressBarProps {
  isRunning: boolean
  status: string
  progressPercent?: number
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
  captchaDetected?: boolean
  recentDomains?: Array<{
    domain: string
    source: string | null
    createdAt: string
  }>
  parsingLogs?: {
    google?: { total_links: number; pages_processed: number; last_links: string[] }
    yandex?: { total_links: number; pages_processed: number; last_links: string[] }
  } | null
  keyword?: string
  depth?: number
}

export function ParsingProgressBar({
  isRunning,
  status,
  progressPercent = 0,
  resultsCount,
  source,
  sourceStats,
  sourceStatus,
  captchaDetected,
  recentDomains,
  parsingLogs,
  keyword,
  depth,
}: ParsingProgressBarProps) {
  const totalDomains = (sourceStats?.google ?? 0) + (sourceStats?.yandex ?? 0) + (sourceStats?.both ?? 0)
  const googleProgress = sourceStatus?.google.domains ?? sourceStats?.google ?? 0
  const yandexProgress = sourceStatus?.yandex.domains ?? sourceStats?.yandex ?? 0

  // Calculate individual source progress for "both" mode
  const maxDomainsPerSource = (depth ?? 5) * 10
  const googlePercent =
    source === "both"
      ? Math.min((googleProgress / maxDomainsPerSource) * 100, 100)
      : source === "google"
        ? progressPercent
        : 0
  const yandexPercent =
    source === "both"
      ? Math.min((yandexProgress / maxDomainsPerSource) * 100, 100)
      : source === "yandex"
        ? progressPercent
        : 0

  return (
    <AnimatePresence>
      {isRunning && (
        <motion.div
          initial={{ opacity: 0, y: -20, scale: 0.95 }}
          animate={{ opacity: 1, y: 0, scale: 1 }}
          exit={{ opacity: 0, y: -20, scale: 0.95 }}
          transition={{ duration: 0.4, ease: "easeOut" }}
        >
          <Card
            className={cn(
              "mt-4 overflow-hidden border-2 transition-all duration-300",
              captchaDetected
                ? "border-amber-400 bg-gradient-to-br from-amber-50 to-orange-50"
                : status === "completed"
                  ? "border-emerald-400 bg-gradient-to-br from-emerald-50 to-green-50"
                  : "border-blue-400 bg-gradient-to-br from-blue-50 via-indigo-50 to-purple-50",
            )}
          >
            {/* Animated top border */}
            <div className="relative h-1 overflow-hidden">
              <motion.div
                className={cn(
                  "absolute inset-0",
                  captchaDetected
                    ? "bg-gradient-to-r from-amber-400 via-orange-500 to-amber-400"
                    : status === "completed"
                      ? "bg-gradient-to-r from-emerald-400 via-green-500 to-emerald-400"
                      : "bg-gradient-to-r from-blue-500 via-indigo-500 to-purple-500",
                )}
                animate={{
                  x: status === "running" ? ["0%", "100%"] : "0%",
                }}
                transition={{
                  duration: 2,
                  repeat: status === "running" ? Number.POSITIVE_INFINITY : 0,
                  ease: "linear",
                }}
                style={{ width: "200%" }}
              />
            </div>

            <CardContent className="p-5">
              {/* Header Section */}
              <div className="flex items-center justify-between mb-4">
                <div className="flex items-center gap-3">
                  <motion.div
                    className={cn(
                      "relative h-12 w-12 rounded-xl flex items-center justify-center",
                      captchaDetected ? "bg-amber-100" : status === "completed" ? "bg-emerald-100" : "bg-blue-100",
                    )}
                    animate={status === "running" && !captchaDetected ? { scale: [1, 1.05, 1] } : {}}
                    transition={{ duration: 2, repeat: Number.POSITIVE_INFINITY }}
                  >
                    {captchaDetected ? (
                      <AlertTriangle className="h-6 w-6 text-amber-600" />
                    ) : status === "completed" ? (
                      <CheckCircle2 className="h-6 w-6 text-emerald-600" />
                    ) : (
                      <Loader2 className="h-6 w-6 text-blue-600 animate-spin" />
                    )}

                    {/* Pulsing ring */}
                    {status === "running" && !captchaDetected && (
                      <motion.div
                        className="absolute inset-0 rounded-xl border-2 border-blue-400"
                        animate={{ scale: [1, 1.3], opacity: [0.5, 0] }}
                        transition={{ duration: 1.5, repeat: Number.POSITIVE_INFINITY }}
                      />
                    )}
                  </motion.div>

                  <div>
                    <h3 className="font-semibold text-lg text-slate-800">
                      {captchaDetected
                        ? "Требуется CAPTCHA"
                        : status === "completed"
                          ? "Парсинг завершен"
                          : "Парсинг выполняется"}
                    </h3>
                    {keyword && (
                      <p className="text-sm text-slate-500">
                        Ключевое слово: <span className="font-medium text-slate-700">"{keyword}"</span>
                      </p>
                    )}
                  </div>
                </div>

                {/* Total domains badge */}
                <motion.div key={totalDomains} initial={{ scale: 1.2 }} animate={{ scale: 1 }} className="text-right">
                  <div className="flex items-center gap-2">
                    <Globe className="h-4 w-4 text-slate-400" />
                    <span className="text-2xl font-bold text-slate-800">{totalDomains}</span>
                  </div>
                  <p className="text-xs text-slate-500">доменов найдено</p>
                </motion.div>
              </div>

              {/* Main Progress Bar */}
              <div className="relative mb-4">
                <div className="flex items-center justify-between mb-2">
                  <span className="text-sm font-medium text-slate-600">Общий прогресс</span>
                  <span className="text-sm font-bold text-slate-700">{Math.round(progressPercent)}%</span>
                </div>

                <div className="relative h-4 bg-slate-200 rounded-full overflow-hidden">
                  {/* Background glow */}
                  <div className="absolute inset-0 bg-gradient-to-r from-transparent via-white/20 to-transparent" />

                  {/* Progress fill */}
                  <motion.div
                    className={cn(
                      "h-full rounded-full relative",
                      status === "completed"
                        ? "bg-gradient-to-r from-emerald-400 to-green-500"
                        : "bg-gradient-to-r from-blue-500 via-indigo-500 to-purple-500",
                    )}
                    initial={{ width: 0 }}
                    animate={{ width: `${progressPercent}%` }}
                    transition={{ duration: 0.5, ease: "easeOut" }}
                  >
                    {/* Shimmer effect */}
                    {status === "running" && (
                      <motion.div
                        className="absolute inset-0 bg-gradient-to-r from-transparent via-white/30 to-transparent"
                        animate={{ x: ["-100%", "100%"] }}
                        transition={{ duration: 1.5, repeat: Number.POSITIVE_INFINITY, ease: "linear" }}
                      />
                    )}
                  </motion.div>

                  {/* Glow effect at the end */}
                  {status === "running" && progressPercent > 0 && (
                    <motion.div
                      className="absolute top-0 h-full w-4 bg-white/50 blur-sm rounded-full"
                      style={{ left: `calc(${progressPercent}% - 8px)` }}
                      animate={{ opacity: [0.5, 1, 0.5] }}
                      transition={{ duration: 1, repeat: Number.POSITIVE_INFINITY }}
                    />
                  )}
                </div>
              </div>

              {/* Source-specific progress (for "both" mode) */}
              {source === "both" && (
                <div className="grid grid-cols-2 gap-4 mb-4">
                  {/* Google Progress */}
                  <div className="space-y-2">
                    <div className="flex items-center justify-between">
                      <div className="flex items-center gap-2">
                        <div className="h-2.5 w-2.5 rounded-full bg-blue-500" />
                        <span className="text-sm font-medium text-slate-600">Google</span>
                        {sourceStatus?.google.completed && <CheckCircle2 className="h-3.5 w-3.5 text-emerald-500" />}
                      </div>
                      <span className="text-sm text-slate-500">{googleProgress} доменов</span>
                    </div>
                    <div className="h-2 bg-slate-200 rounded-full overflow-hidden">
                      <motion.div
                        className={cn(
                          "h-full rounded-full",
                          sourceStatus?.google.completed
                            ? "bg-emerald-400"
                            : "bg-gradient-to-r from-blue-400 to-blue-600",
                        )}
                        initial={{ width: 0 }}
                        animate={{ width: `${googlePercent}%` }}
                        transition={{ duration: 0.5 }}
                      />
                    </div>
                  </div>

                  {/* Yandex Progress */}
                  <div className="space-y-2">
                    <div className="flex items-center justify-between">
                      <div className="flex items-center gap-2">
                        <div className="h-2.5 w-2.5 rounded-full bg-red-500" />
                        <span className="text-sm font-medium text-slate-600">Яндекс</span>
                        {sourceStatus?.yandex.completed && <CheckCircle2 className="h-3.5 w-3.5 text-emerald-500" />}
                      </div>
                      <span className="text-sm text-slate-500">{yandexProgress} доменов</span>
                    </div>
                    <div className="h-2 bg-slate-200 rounded-full overflow-hidden">
                      <motion.div
                        className={cn(
                          "h-full rounded-full",
                          sourceStatus?.yandex.completed
                            ? "bg-emerald-400"
                            : "bg-gradient-to-r from-red-400 to-red-600",
                        )}
                        initial={{ width: 0 }}
                        animate={{ width: `${yandexPercent}%` }}
                        transition={{ duration: 0.5 }}
                      />
                    </div>
                  </div>
                </div>
              )}

              {/* Single source progress bar */}
              {source !== "both" && source && (
                <div className="mb-4 space-y-2">
                  <div className="flex items-center justify-between">
                    <div className="flex items-center gap-2">
                      <div
                        className={cn("h-2.5 w-2.5 rounded-full", source === "google" ? "bg-blue-500" : "bg-red-500")}
                      />
                      <span className="text-sm font-medium text-slate-600">
                        {source === "google" ? "Google" : "Яндекс"}
                      </span>
                    </div>
                    <span className="text-sm text-slate-500">{totalDomains} доменов</span>
                  </div>
                  <div className="h-2 bg-slate-200 rounded-full overflow-hidden">
                    <motion.div
                      className={cn(
                        "h-full rounded-full",
                        source === "google"
                          ? "bg-gradient-to-r from-blue-400 to-blue-600"
                          : "bg-gradient-to-r from-red-400 to-red-600",
                      )}
                      initial={{ width: 0 }}
                      animate={{ width: `${progressPercent}%` }}
                      transition={{ duration: 0.5 }}
                    />
                  </div>
                </div>
              )}

              {/* Parser Logs Section */}
              {parsingLogs && (parsingLogs.google || parsingLogs.yandex) && (
                <div className="bg-slate-900 rounded-lg p-3 mb-4">
                  <div className="flex items-center gap-2 mb-2">
                    <Zap className="h-4 w-4 text-yellow-400" />
                    <span className="text-sm font-medium text-slate-200">Live данные парсера</span>
                  </div>

                  <div className="grid grid-cols-2 gap-3 text-xs">
                    {parsingLogs.google && (
                      <div className="space-y-1">
                        <div className="flex items-center gap-1.5 text-blue-400">
                          <div className="h-1.5 w-1.5 rounded-full bg-blue-400 animate-pulse" />
                          Google
                        </div>
                        <div className="text-slate-400">
                          {parsingLogs.google.total_links} ссылок • {parsingLogs.google.pages_processed} стр.
                        </div>
                      </div>
                    )}
                    {parsingLogs.yandex && (
                      <div className="space-y-1">
                        <div className="flex items-center gap-1.5 text-red-400">
                          <div className="h-1.5 w-1.5 rounded-full bg-red-400 animate-pulse" />
                          Яндекс
                        </div>
                        <div className="text-slate-400">
                          {parsingLogs.yandex.total_links} ссылок • {parsingLogs.yandex.pages_processed} стр.
                        </div>
                      </div>
                    )}
                  </div>
                </div>
              )}

              {/* Recent Domains Feed */}
              {recentDomains && recentDomains.length > 0 && (
                <div className="border-t border-slate-200 pt-3">
                  <div className="flex items-center justify-between mb-2">
                    <span className="text-sm font-medium text-slate-600">Последние найденные домены</span>
                    <Badge variant="secondary" className="text-xs">
                      Live
                      <motion.span
                        className="ml-1 h-1.5 w-1.5 rounded-full bg-emerald-500 inline-block"
                        animate={{ opacity: [1, 0.3, 1] }}
                        transition={{ duration: 1, repeat: Number.POSITIVE_INFINITY }}
                      />
                    </Badge>
                  </div>

                  <div className="space-y-1.5 max-h-32 overflow-y-auto">
                    <AnimatePresence mode="popLayout">
                      {recentDomains.slice(0, 5).map((domain, idx) => (
                        <motion.div
                          key={`${domain.domain}-${domain.createdAt}`}
                          initial={{ opacity: 0, x: -20 }}
                          animate={{ opacity: 1, x: 0 }}
                          exit={{ opacity: 0, x: 20 }}
                          transition={{ duration: 0.3, delay: idx * 0.05 }}
                          className="flex items-center gap-2 text-sm bg-white/60 rounded-md px-2.5 py-1.5 border border-slate-100"
                        >
                          <div
                            className={cn(
                              "h-2 w-2 rounded-full shrink-0",
                              domain.source === "google"
                                ? "bg-blue-500"
                                : domain.source === "yandex"
                                  ? "bg-red-500"
                                  : "bg-purple-500",
                            )}
                          />
                          <span className="text-slate-700 truncate flex-1 font-mono text-xs">{domain.domain}</span>
                          <ExternalLink className="h-3 w-3 text-slate-400 shrink-0" />
                        </motion.div>
                      ))}
                    </AnimatePresence>
                  </div>
                </div>
              )}

              {/* CAPTCHA Warning */}
              {captchaDetected && (
                <motion.div
                  initial={{ opacity: 0, y: 10 }}
                  animate={{ opacity: 1, y: 0 }}
                  className="mt-3 p-3 bg-amber-100 rounded-lg border border-amber-300"
                >
                  <div className="flex items-center gap-2 text-amber-800">
                    <AlertTriangle className="h-5 w-5" />
                    <span className="font-medium">Обнаружена CAPTCHA</span>
                  </div>
                  <p className="text-sm text-amber-700 mt-1">
                    Пожалуйста, откройте окно Chrome и решите капчу для продолжения парсинга.
                  </p>
                </motion.div>
              )}
            </CardContent>
          </Card>
        </motion.div>
      )}
    </AnimatePresence>
  )
}
