"use client"

import { useQuery, useMutation, useQueryClient } from "@tanstack/react-query"
import { toast } from "sonner"
import {
  getParsingRuns,
  getParsingRun,
  getParsingLogs,
  getDomainsQueue,
  getModeratorDashboardStats,
  startParsing,
  getDomainParserStatus,
} from "@/lib/api"
import type { ParsingRunDTO, DomainQueueEntryDTO, ParsingLogsDTO } from "@/lib/types"

// Query keys
export const parsingKeys = {
  all: ["parsing"] as const,
  runs: () => [...parsingKeys.all, "runs"] as const,
  runList: (params?: any) => [...parsingKeys.runs(), "list", params] as const,
  run: (id: string) => [...parsingKeys.runs(), "detail", id] as const,
  logs: (id: string) => [...parsingKeys.run(id), "logs"] as const,
  domainParser: (parserRunId: string) => [...parsingKeys.all, "domainParser", parserRunId] as const,
  queue: () => [...parsingKeys.all, "queue"] as const,
  queueList: (params?: any) => [...parsingKeys.queue(), "list", params] as const,
  stats: () => [...parsingKeys.all, "stats"] as const,
}

// Hooks
export function useParsingRuns(params?: any) {
  return useQuery({
    queryKey: parsingKeys.runList(params),
    queryFn: () => getParsingRuns(params),
    staleTime: 2 * 60 * 1000, // 2 minutes
    refetchInterval: 30 * 1000, // Auto-refresh every 30 seconds
  })
}

export function useParsingRun(id: string) {
  return useQuery({
    queryKey: parsingKeys.run(id),
    queryFn: () => getParsingRun(id),
    enabled: !!id,
    staleTime: 10 * 1000, // 10 seconds for active runs
    refetchInterval: (query) => {
      const data = query.state.data
      if (!data) return false
      return ["running", "starting"].includes(data.status) ? 5000 : false
    },
  })
}

export function useParsingLogs(id: string, enabled?: boolean) {
  return useQuery({
    queryKey: parsingKeys.logs(id),
    queryFn: () => getParsingLogs(id),
    enabled: !!id && (enabled ?? true),
    staleTime: 5 * 1000, // 5 seconds
    refetchInterval: (query) => {
      if (!enabled) return false
      const data = query.state.data as any
      if (!data?.run) return false
      
      return ["running", "starting"].includes(data.run.status) ? 3000 : false
    },
  })
}

export function useDomainParserStatus(parserRunId: string, enabled?: boolean) {
  return useQuery({
    queryKey: parsingKeys.domainParser(parserRunId),
    queryFn: () => getDomainParserStatus(parserRunId),
    enabled: !!parserRunId && (enabled ?? true),
    staleTime: 5 * 1000,
    refetchInterval: (query) => {
      if (!enabled) return false
      const data = query.state.data as any
      if (!data) return 8000
      if (data.status === "completed" || data.status === "failed") return false
      return 8000
    },
  })
}

export function useDomainsQueue(params?: any) {
  return useQuery({
    queryKey: parsingKeys.queueList(params),
    queryFn: () => getDomainsQueue(params),
    staleTime: 30 * 1000, // 30 seconds
    refetchInterval: 10 * 1000, // Refresh every 10 seconds
  })
}

export function useModeratorStats() {
  return useQuery({
    queryKey: parsingKeys.stats(),
    queryFn: getModeratorDashboardStats,
    staleTime: 60 * 1000, // 1 minute
    refetchInterval: 60 * 1000, // Refresh every minute
  })
}

export function useStartParsing() {
  const queryClient = useQueryClient()
  
  return useMutation({
    mutationFn: startParsing,
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: parsingKeys.runs() })
      queryClient.invalidateQueries({ queryKey: parsingKeys.queue() })
      queryClient.invalidateQueries({ queryKey: parsingKeys.stats() })
      toast.success("Парсинг запущен")
    },
    onError: (error: any) => {
      toast.error(error.message || "Ошибка при запуске парсинга")
    },
  })
}
