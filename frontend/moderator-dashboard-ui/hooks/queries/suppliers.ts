"use client"

import { useQuery, useMutation, useQueryClient } from "@tanstack/react-query"
import { toast } from "sonner"
import {
  getSuppliers,
  deleteSupplier,
  addToBlacklist,
  updateSupplier,
  getCheckoData,
  getCheckoHealth,
  apiFetchWithRetry,
} from "@/lib/api"
import type { SupplierDTO } from "@/lib/types"

// Query keys
export const supplierKeys = {
  all: ["suppliers"] as const,
  lists: () => [...supplierKeys.all, "list"] as const,
  list: (params?: any) => [...supplierKeys.lists(), params] as const,
  details: () => [...supplierKeys.all, "detail"] as const,
  detail: (id: string) => [...supplierKeys.details(), id] as const,
  checko: (id: string) => [...supplierKeys.detail(id), "checko"] as const,
}

// Hooks
export function useSuppliers(params?: any) {
  return useQuery({
    queryKey: supplierKeys.list(params),
    queryFn: () => getSuppliers(params),
    staleTime: 5 * 60 * 1000, // 5 minutes
    gcTime: 10 * 60 * 1000, // 10 minutes
  })
}

export function useSupplier(id: number) {
  return useQuery({
    queryKey: supplierKeys.detail(id.toString()),
    queryFn: () => getSuppliers().then(result => 
      result.suppliers.find(s => s.id === id)
    ),
    enabled: !!id,
    staleTime: 5 * 60 * 1000,
  })
}

export function useSupplierCheckoData(id: string) {
  return useQuery({
    queryKey: supplierKeys.checko(id),
    queryFn: () => getCheckoData(id),
    enabled: !!id,
    staleTime: 30 * 60 * 1000, // 30 minutes for checko data
    retry: 2,
  })
}

export function useDeleteSupplier() {
  const queryClient = useQueryClient()
  
  return useMutation({
    mutationFn: deleteSupplier,
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: supplierKeys.lists() })
      toast.success("Поставщик удален")
    },
    onError: (error: any) => {
      toast.error(error.message || "Ошибка при удалении поставщика")
    },
  })
}

export function useAddToBlacklist() {
  const queryClient = useQueryClient()
  
  return useMutation({
    mutationFn: addToBlacklist,
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: supplierKeys.lists() })
      queryClient.invalidateQueries({ queryKey: ["blacklist"] })
      toast.success("Добавлено в черный список")
    },
    onError: (error: any) => {
      toast.error(error.message || "Ошибка при добавлении в черный список")
    },
  })
}

export function useUpdateSupplier() {
  const queryClient = useQueryClient()
  
  return useMutation({
    mutationFn: ({ id, data }: { id: number; data: Partial<SupplierDTO> }) => 
      updateSupplier(id, data),
    onSuccess: (_, { id }) => {
      queryClient.invalidateQueries({ queryKey: supplierKeys.lists() })
      queryClient.invalidateQueries({ queryKey: supplierKeys.detail(id.toString()) })
      toast.success("Данные поставщика обновлены")
    },
    onError: (error: any) => {
      toast.error(error.message || "Ошибка при обновлении поставщика")
    },
  })
}
