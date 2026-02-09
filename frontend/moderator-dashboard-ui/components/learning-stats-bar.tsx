"use client"

import { Brain } from "lucide-react"

export interface LearningStatsData {
  totalLearned: number
  successRateBefore: number
  successRateAfter: number
}

interface LearningStatsBarProps {
  stats: LearningStatsData
  /** "banner" = horizontal bar (domains page), "card" = compact card (moderator dashboard) */
  variant?: "banner" | "card"
}

export function LearningStatsBar({ stats, variant = "banner" }: LearningStatsBarProps) {
  if (!stats || stats.totalLearned <= 0) return null

  if (variant === "card") {
    return (
      <div className="bg-gradient-to-r from-purple-50 to-blue-50 dark:from-purple-950 dark:to-blue-950 border border-purple-200 dark:border-purple-800 rounded-md p-3">
        <div className="flex items-center gap-2 mb-2">
          <Brain className="h-4 w-4 text-purple-600" />
          <span className="text-sm font-medium text-purple-700 dark:text-purple-300">Статистика обучения</span>
        </div>
        <div className="grid grid-cols-3 gap-2 text-xs">
          <div>
            <p className="text-muted-foreground">Выучено</p>
            <p className="font-bold text-purple-700 dark:text-purple-300">{stats.totalLearned}</p>
          </div>
          <div>
            <p className="text-muted-foreground">До обучения</p>
            <p className="font-bold">{(stats.successRateBefore * 100).toFixed(1)}%</p>
          </div>
          <div>
            <p className="text-muted-foreground">После</p>
            <p className="font-bold text-green-600">{(stats.successRateAfter * 100).toFixed(1)}%</p>
          </div>
        </div>
      </div>
    )
  }

  return (
    <div className="mb-4 rounded-lg border border-purple-200 bg-gradient-to-r from-purple-50 to-blue-50 shadow-sm overflow-hidden">
      <div className="flex items-center justify-between px-4 py-3">
        <div className="flex items-center gap-2">
          <Brain className="h-5 w-5 text-purple-600" />
          <span className="text-sm font-semibold text-purple-700">Статистика обучения парсера</span>
        </div>
        <div className="flex items-center gap-4 text-sm">
          <div>
            <span className="text-muted-foreground">Выучено: </span>
            <span className="font-bold text-purple-700">{stats.totalLearned}</span>
          </div>
          <div>
            <span className="text-muted-foreground">До: </span>
            <span className="font-bold">{(stats.successRateBefore * 100).toFixed(1)}%</span>
          </div>
          <div>
            <span className="text-muted-foreground">После: </span>
            <span className="font-bold text-green-600">{(stats.successRateAfter * 100).toFixed(1)}%</span>
          </div>
        </div>
      </div>
    </div>
  )
}
