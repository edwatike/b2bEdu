"use client"

import { useQuery, useMutation, useQueryClient } from "@tanstack/react-query"
import { toast } from "sonner"
import { getBlacklist, removeFromBlacklist } from "@/lib/api"
import type { BlacklistEntryDTO } from "@/lib/types"

// Query keys
export const blacklistKeys = {
  all: ["blacklist"] as const,
  lists: () => [...blacklistKeys.all, "list"] as const,
  list: (params?: any) => [...blacklistKeys.lists(), params] as const,
}

// Hooks
export function useBlacklist(params?: any) {
  return useQuery({
    queryKey: blacklistKeys.list(params),
    queryFn: () => getBlacklist(params),
    staleTime: 5 * 60 * 1000, // 5 minutes
    gcTime: 10 * 60 * 1000, // 10 minutes
  })
}

export function useRemoveFromBlacklist() {
  const queryClient = useQueryClient()
  
  return useMutation({
    mutationFn: removeFromBlacklist,
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: blacklistKeys.lists() })
      queryClient.invalidateQueries({ queryKey: ["suppliers"] })
      toast.success("Удалено из черного списка")
    },
    onError: (error: any) => {
      toast.error(error.message || "Ошибка при удалении из черного списка")
    },
  })
}
