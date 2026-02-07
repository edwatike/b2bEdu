'use client'

import { apiFetch, apiFetchWithRetry, APIError } from './api'
import type {
  SupplierDTO,
  KeywordDTO,
  BlacklistEntryDTO,
  ParsingRunDTO,
  CabinetSettingsDTO,
  CabinetStatsDTO,
  CabinetMessageDTO,
} from './types'
import {
  mockSuppliers,
  mockKeywords,
  mockBlacklist,
  mockParsingRuns,
  mockCabinetStats,
  mockCabinetMessages,
  mockCabinetSettings,
  mockUser,
  mockAdmin,
  delay,
} from './mock-data'

const USE_MOCK_DATA = process.env.NEXT_PUBLIC_USE_MOCK_DATA === 'true'
const ENABLE_FALLBACK = process.env.NEXT_PUBLIC_ENABLE_FALLBACK !== 'false' // Default: true

interface FallbackOptions {
  useMock?: boolean
  enableFallback?: boolean
  mockDelay?: number
}

// Wrapper функция для API запросов с fallback
export async function apiFetchWithFallback<T>(
  endpoint: string,
  options?: RequestInit,
  fallbackData?: T,
  fallbackOptions?: FallbackOptions,
): Promise<T> {
  const useMock = fallbackOptions?.useMock ?? USE_MOCK_DATA
  const enableFallback = fallbackOptions?.enableFallback ?? ENABLE_FALLBACK
  const mockDelay = fallbackOptions?.mockDelay ?? 300

  // Если явно включен mock режим, используем mock данные
  if (useMock) {
    console.log(`[v0] Using mock data for: ${endpoint}`)
    await delay(mockDelay)
    return fallbackData || ({} as T)
  }

  // Пытаемся получить реальные данные
  try {
    return await apiFetchWithRetry<T>(endpoint, options)
  } catch (error) {
    // Если у нас есть fallback данные и fallback включен, используем их
    if (enableFallback && fallbackData) {
      console.warn(`[v0] API failed (${endpoint}), using fallback data:`, error)
      await delay(mockDelay)
      return fallbackData
    }

    // Если нет fallback данных, пробрасываем ошибку
    throw error
  }
}

// API функции с fallback поддержкой

export async function getSuppliers(params?: {
  limit?: number
  offset?: number
  status?: string
  search?: string
}): Promise<{ entries: SupplierDTO[]; total: number; limit: number; offset: number }> {
  const query = new URLSearchParams()
  if (params?.limit) query.append('limit', params.limit.toString())
  if (params?.offset) query.append('offset', params.offset.toString())
  if (params?.status) query.append('status', params.status)
  if (params?.search) query.append('search', params.search)

  const fallbackData = {
    entries: mockSuppliers,
    total: mockSuppliers.length,
    limit: params?.limit || 10,
    offset: params?.offset || 0,
  }

  return apiFetchWithFallback(
    `/suppliers?${query.toString()}`,
    { method: 'GET' },
    fallbackData,
  )
}

export async function getKeywords(params?: {
  limit?: number
  offset?: number
  category?: string
}): Promise<{ entries: KeywordDTO[]; total: number; limit: number; offset: number }> {
  const query = new URLSearchParams()
  if (params?.limit) query.append('limit', params.limit.toString())
  if (params?.offset) query.append('offset', params.offset.toString())
  if (params?.category) query.append('category', params.category)

  const fallbackData = {
    entries: mockKeywords,
    total: mockKeywords.length,
    limit: params?.limit || 10,
    offset: params?.offset || 0,
  }

  return apiFetchWithFallback(
    `/keywords?${query.toString()}`,
    { method: 'GET' },
    fallbackData,
  )
}

export async function getBlacklist(params?: {
  limit?: number
  offset?: number
}): Promise<{ entries: BlacklistEntryDTO[]; total: number; limit: number; offset: number }> {
  const query = new URLSearchParams()
  if (params?.limit) query.append('limit', params.limit.toString())
  if (params?.offset) query.append('offset', params.offset.toString())

  const fallbackData = {
    entries: mockBlacklist,
    total: mockBlacklist.length,
    limit: params?.limit || 10,
    offset: params?.offset || 0,
  }

  return apiFetchWithFallback(
    `/blacklist?${query.toString()}`,
    { method: 'GET' },
    fallbackData,
  )
}

export async function getParsingRuns(params?: {
  limit?: number
  offset?: number
}): Promise<{ entries: ParsingRunDTO[]; total: number; limit: number; offset: number }> {
  const query = new URLSearchParams()
  if (params?.limit) query.append('limit', params.limit.toString())
  if (params?.offset) query.append('offset', params.offset.toString())

  const fallbackData = {
    entries: mockParsingRuns,
    total: mockParsingRuns.length,
    limit: params?.limit || 10,
    offset: params?.offset || 0,
  }

  return apiFetchWithFallback(
    `/parsing-runs?${query.toString()}`,
    { method: 'GET' },
    fallbackData,
  )
}

export async function getCabinetStats(): Promise<CabinetStatsDTO> {
  return apiFetchWithFallback(
    '/cabinet/stats',
    { method: 'GET' },
    mockCabinetStats,
  )
}

export async function getCabinetMessages(params?: {
  limit?: number
  offset?: number
  unread_only?: boolean
}): Promise<{ entries: CabinetMessageDTO[]; total: number; limit: number; offset: number }> {
  const query = new URLSearchParams()
  if (params?.limit) query.append('limit', params.limit.toString())
  if (params?.offset) query.append('offset', params.offset.toString())
  if (params?.unread_only) query.append('unread_only', 'true')

  const fallbackData = {
    entries: mockCabinetMessages,
    total: mockCabinetMessages.length,
    limit: params?.limit || 10,
    offset: params?.offset || 0,
  }

  return apiFetchWithFallback(
    `/cabinet/messages?${query.toString()}`,
    { method: 'GET' },
    fallbackData,
  )
}

export async function getCabinetSettings(): Promise<CabinetSettingsDTO> {
  return apiFetchWithFallback(
    '/cabinet/settings',
    { method: 'GET' },
    mockCabinetSettings,
  )
}

export async function updateCabinetSettings(settings: Partial<CabinetSettingsDTO>): Promise<CabinetSettingsDTO> {
  return apiFetchWithFallback(
    '/cabinet/settings',
    {
      method: 'PUT',
      body: JSON.stringify(settings),
    },
    { ...mockCabinetSettings, ...settings },
  )
}

export async function getAuthStatus(): Promise<{ authenticated: boolean; user?: any; role?: string }> {
  return apiFetchWithFallback(
    '/auth/status',
    { method: 'GET' },
    {
      authenticated: false,
    },
  )
}

export async function getAuthMe(): Promise<any> {
  return apiFetchWithFallback(
    '/auth/me',
    { method: 'GET' },
    mockUser,
  )
}

// Вспомогательная функция для переключения на mock режим
export function enableMockMode() {
  localStorage.setItem('NEXT_PUBLIC_USE_MOCK_DATA', 'true')
  window.location.reload()
}

// Вспомогательная функция для отключения mock режима
export function disableMockMode() {
  localStorage.removeItem('NEXT_PUBLIC_USE_MOCK_DATA')
  window.location.reload()
}

// Вспомогательная функция для проверки текущего режима
export function isMockModeEnabled(): boolean {
  if (typeof window === 'undefined') return USE_MOCK_DATA
  return localStorage.getItem('NEXT_PUBLIC_USE_MOCK_DATA') === 'true' || USE_MOCK_DATA
}

// Вспомогательная функция для проверки fallback режима
export function isFallbackEnabled(): boolean {
  return ENABLE_FALLBACK
}
