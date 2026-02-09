"use client"

import { useQuery, useMutation, useQueryClient } from "@tanstack/react-query"
import { toast } from "sonner"
import { getKeywords, createKeyword, deleteKeyword } from "@/lib/api"
import type { KeywordDTO } from "@/lib/types"

// Query keys
export const keywordKeys = {
  all: ["keywords"] as const,
  lists: () => [...keywordKeys.all, "list"] as const,
  list: (params?: any) => [...keywordKeys.lists(), params] as const,
}

// Hooks
export function useKeywords(options?: { refetchInterval?: number | false }) {
  return useQuery({
    queryKey: keywordKeys.list(),
    queryFn: () => getKeywords(),
    staleTime: 30 * 1000, // 30 seconds (matches polling cadence)
    gcTime: 10 * 60 * 1000, // 10 minutes
    refetchInterval: options?.refetchInterval ?? 30_000, // Auto-refresh every 30s by default
  })
}

export function useAddKeyword() {
  const queryClient = useQueryClient()
  
  return useMutation({
    mutationFn: createKeyword,
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: keywordKeys.lists() })
      toast.success("Ключевое слово добавлено")
    },
    onError: (error: any) => {
      toast.error(error.message || "Ошибка при добавлении ключевого слова")
    },
  })
}

export function useDeleteKeyword() {
  const queryClient = useQueryClient()
  
  return useMutation({
    mutationFn: deleteKeyword,
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: keywordKeys.lists() })
      toast.success("Ключевое слово удалено")
    },
    onError: (error: any) => {
      toast.error(error.message || "Ошибка при удалении ключевого слова")
    },
  })
}
