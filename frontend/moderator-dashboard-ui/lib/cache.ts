// Утилиты для кэширования данных
import type { SupplierDTO, BlacklistEntryDTO } from "./types"

const CACHE_KEYS = {
  SUPPLIERS: "cached_suppliers",
  BLACKLIST: "cached_blacklist",
  CACHE_TIMESTAMP: "cache_timestamp",
} as const

const CACHE_DURATION = 5 * 60 * 1000 // 5 минут

interface CacheEntry<T> {
  data: T
  timestamp: number
}

export function getCachedSuppliers(): SupplierDTO[] | null {
  try {
    const cached = localStorage.getItem(CACHE_KEYS.SUPPLIERS)
    const timestamp = localStorage.getItem(CACHE_KEYS.CACHE_TIMESTAMP)
    
    if (!cached || !timestamp) return null
    
    const age = Date.now() - Number.parseInt(timestamp, 10)
    if (age > CACHE_DURATION) {
      // Кэш устарел
      localStorage.removeItem(CACHE_KEYS.SUPPLIERS)
      localStorage.removeItem(CACHE_KEYS.CACHE_TIMESTAMP)
      return null
    }
    
    return JSON.parse(cached) as SupplierDTO[]
  } catch {
    return null
  }
}

export function setCachedSuppliers(suppliers: SupplierDTO[]): void {
  try {
    // Exclude checkoData from cache to avoid localStorage quota exceeded
    // checkoData is too large (can be 300KB+ per supplier) and causes QuotaExceededError
    const suppliersWithoutCheckoData = suppliers.map(supplier => {
      const { checkoData, ...supplierWithoutCheckoData } = supplier
      return supplierWithoutCheckoData
    })
    localStorage.setItem(CACHE_KEYS.SUPPLIERS, JSON.stringify(suppliersWithoutCheckoData))
    localStorage.setItem(CACHE_KEYS.CACHE_TIMESTAMP, Date.now().toString())
  } catch (error) {
    console.error("Error caching suppliers:", error)
    // If still fails, try to clear old cache and retry
    try {
      localStorage.removeItem(CACHE_KEYS.SUPPLIERS)
      localStorage.removeItem(CACHE_KEYS.CACHE_TIMESTAMP)
      const suppliersWithoutCheckoData = suppliers.map(supplier => {
        const { checkoData, ...supplierWithoutCheckoData } = supplier
        return supplierWithoutCheckoData
      })
      localStorage.setItem(CACHE_KEYS.SUPPLIERS, JSON.stringify(suppliersWithoutCheckoData))
      localStorage.setItem(CACHE_KEYS.CACHE_TIMESTAMP, Date.now().toString())
    } catch (retryError) {
      console.error("Error retrying cache after cleanup:", retryError)
    }
  }
}

export function getCachedBlacklist(): BlacklistEntryDTO[] | null {
  try {
    const cached = localStorage.getItem(CACHE_KEYS.BLACKLIST)
    const timestamp = localStorage.getItem(CACHE_KEYS.CACHE_TIMESTAMP)
    
    if (!cached || !timestamp) return null
    
    const age = Date.now() - Number.parseInt(timestamp, 10)
    if (age > CACHE_DURATION) {
      // Кэш устарел
      localStorage.removeItem(CACHE_KEYS.BLACKLIST)
      localStorage.removeItem(CACHE_KEYS.CACHE_TIMESTAMP)
      return null
    }
    
    return JSON.parse(cached) as BlacklistEntryDTO[]
  } catch {
    return null
  }
}

export function setCachedBlacklist(blacklist: BlacklistEntryDTO[]): void {
  try {
    localStorage.setItem(CACHE_KEYS.BLACKLIST, JSON.stringify(blacklist))
    localStorage.setItem(CACHE_KEYS.CACHE_TIMESTAMP, Date.now().toString())
  } catch (error) {
    console.error("Error caching blacklist:", error)
  }
}

export function invalidateCache(): void {
  try {
    localStorage.removeItem(CACHE_KEYS.SUPPLIERS)
    localStorage.removeItem(CACHE_KEYS.BLACKLIST)
    localStorage.removeItem(CACHE_KEYS.CACHE_TIMESTAMP)
  } catch (error) {
    console.error("Error invalidating cache:", error)
  }
}

export function invalidateSuppliersCache(): void {
  try {
    localStorage.removeItem(CACHE_KEYS.SUPPLIERS)
  } catch (error) {
    console.error("Error invalidating suppliers cache:", error)
  }
}

export function invalidateBlacklistCache(): void {
  try {
    localStorage.removeItem(CACHE_KEYS.BLACKLIST)
  } catch (error) {
    console.error("Error invalidating blacklist cache:", error)
  }
}
