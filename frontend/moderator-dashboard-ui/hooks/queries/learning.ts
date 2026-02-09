"use client"

import { useQuery } from "@tanstack/react-query"
import { getLearningStatistics, getLearnedSummary } from "@/lib/api"
import type { LearningStatistics } from "@/lib/api"

export const learningKeys = {
  all: ["learning"] as const,
  statistics: () => [...learningKeys.all, "statistics"] as const,
  summary: (limit?: number) => [...learningKeys.all, "summary", limit] as const,
}

export function useLearningStatistics() {
  return useQuery({
    queryKey: learningKeys.statistics(),
    queryFn: getLearningStatistics,
    staleTime: 30 * 1000,
    refetchInterval: 60 * 1000,
  })
}

export function useLearnedSummary(limit = 10) {
  return useQuery({
    queryKey: learningKeys.summary(limit),
    queryFn: () => getLearnedSummary(limit),
    staleTime: 60 * 1000,
  })
}
