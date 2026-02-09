"use client"

import { useQuery, useMutation, useQueryClient } from "@tanstack/react-query"
import { toast } from "sonner"
import { getCurrentTask, manualResolveDomain, startDomainParserForRun, getUnprocessedRuns, resumeAllProcessing } from "@/lib/api"
import type { ManualResolveRequest } from "@/lib/types"

export const currentTaskKeys = {
  all: ["currentTask"] as const,
  detail: () => [...currentTaskKeys.all, "detail"] as const,
  unprocessedRuns: () => [...currentTaskKeys.all, "unprocessedRuns"] as const,
}

export function useCurrentTask() {
  return useQuery({
    queryKey: currentTaskKeys.detail(),
    queryFn: getCurrentTask,
    staleTime: 5 * 1000,
    refetchInterval: 4 * 1000,
  })
}

export function useManualResolveDomain() {
  const queryClient = useQueryClient()

  return useMutation({
    mutationFn: ({ runDomainId, data }: { runDomainId: number; data: ManualResolveRequest }) =>
      manualResolveDomain(runDomainId, data),
    onSuccess: (result) => {
      queryClient.invalidateQueries({ queryKey: currentTaskKeys.all })
      const checkoMsg = result.checko_ok ? " (Checko ✓)" : " (Checko не получен)"
      toast.success(`Домен сохранён как ${result.status}${checkoMsg}`)
    },
    onError: (error: any) => {
      toast.error(error.message || "Ошибка при сохранении")
    },
  })
}

export function useStartDomainParser() {
  const queryClient = useQueryClient()

  return useMutation({
    mutationFn: (runId: string) => startDomainParserForRun(runId),
    onSuccess: (result) => {
      queryClient.invalidateQueries({ queryKey: currentTaskKeys.all })
      toast.success(`Парсер запущен: ${result.pending_count} доменов в обработке`)
    },
    onError: (error: any) => {
      toast.error(error.message || "Ошибка запуска парсера")
    },
  })
}

export function useUnprocessedRuns() {
  return useQuery({
    queryKey: currentTaskKeys.unprocessedRuns(),
    queryFn: getUnprocessedRuns,
    staleTime: 5 * 1000,
    refetchInterval: 6 * 1000,
  })
}

export function useResumeAllProcessing() {
  const queryClient = useQueryClient()

  return useMutation({
    mutationFn: () => resumeAllProcessing(),
    onSuccess: (result) => {
      queryClient.invalidateQueries({ queryKey: currentTaskKeys.all })
      if (result.already_running) {
        toast.info("Парсер уже работает")
      } else if (result.success) {
        toast.success(`Обработка запущена: ${result.pending_count} доменов`)
      } else {
        toast.info(result.message || "Нет необработанных доменов")
      }
    },
    onError: (error: any) => {
      toast.error(error.message || "Ошибка запуска обработки")
    },
  })
}
