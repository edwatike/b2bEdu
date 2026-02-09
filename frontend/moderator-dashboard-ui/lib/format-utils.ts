// Utility functions for formatting data (from supplier-moderation-dashboard)

export function formatCurrency(value: number | null | undefined): string {
  if (!value) return "—"

  const abs = Math.abs(value)

  if (abs >= 1_000_000_000) {
    return `${(value / 1_000_000_000).toFixed(1)} млрд ₽`
  } else if (abs >= 1_000_000) {
    return `${(value / 1_000_000).toFixed(1)} млн ₽`
  } else if (abs >= 1_000) {
    return `${(value / 1_000).toFixed(1)} тыс. ₽`
  }

  return `${value.toLocaleString("ru-RU")} ₽`
}

export function formatDate(dateString: string | null | undefined): string {
  if (!dateString) return "—"

  try {
    const date = new Date(dateString)
    return date.toLocaleDateString("ru-RU", {
      year: "numeric",
      month: "long",
      day: "numeric",
    })
  } catch {
    return "—"
  }
}

export function calculatePercentageChange(current: number, previous: number): string {
  if (!previous) return ""

  const change = ((current - previous) / previous) * 100
  const sign = change > 0 ? "+" : ""

  return `${sign}${change.toFixed(1)}%`
}

export function getRiskLevel(asPlaintiff = 0, asDefendant = 0): "low" | "medium" | "high" {
  if (asDefendant === 0) return "low"

  const ratio = asPlaintiff / asDefendant

  if (ratio > 5) return "low"
  if (ratio > 2) return "medium"
  return "high"
}

export function getRiskColor(level: "low" | "medium" | "high"): string {
  switch (level) {
    case "low":
      return "text-green-600 bg-green-50"
    case "medium":
      return "text-yellow-600 bg-yellow-50"
    case "high":
      return "text-red-600 bg-red-50"
  }
}

export function getRiskEmoji(level: "low" | "medium" | "high"): string {
  switch (level) {
    case "low":
      return "🟢"
    case "medium":
      return "🟡"
    case "high":
      return "🔴"
  }
}

/**
 * Format OKVED code (e.g., "46.51.1" -> "46.51.1")
 */
export function formatOKVEDCode(code: string | undefined): string {
  if (!code) return "—"
  return code
}

export type ReliabilityLevel = 'low' | 'medium' | 'high'

export interface ReliabilityScoreResult {
  level: ReliabilityLevel
  score: number // 0-100
  reasons: string[]
  positive: string[]
  attention: string[]
  negative: string[]
}

interface CheckoDataForReliability {
  _finances?: Record<string, { "2110"?: number; "2400"?: number }>
  _legal?: {
    total?: number
    asPlaintiff?: number
    asDefendant?: number
    sum?: number
  }
  _inspections?: {
    total?: number
    violations?: number
  }
  _enforcements?: {
    count?: number
    amount?: number
  }
  Статус?: {
    Наим?: string
  }
  ДатаРег?: string
}

interface SupplierForReliability {
  registrationDate?: string | null
  companyStatus?: string | null
  legalCasesCount?: number | null
  legalCasesAsPlaintiff?: number | null
  legalCasesAsDefendant?: number | null
  legalCasesSum?: number | null
}

/**
 * Calculate reliability score based on Checko data
 * Implements transparent logic for reliability assessment
 */
export function calculateReliabilityScore(
  checkoData: CheckoDataForReliability | null,
  supplier: SupplierForReliability | null
): ReliabilityScoreResult {
  const reasons: string[] = []
  const positive: string[] = []
  const attention: string[] = []
  const negative: string[] = []
  
  // Start with base score
  let score = 70
  
  // Extract data from checkoData or supplier
  const finances = checkoData?._finances || {}
  const legal = checkoData?._legal || {}
  const inspections = checkoData?._inspections || {}
  const enforcements = checkoData?._enforcements || {}
  
  // Get legal data - prefer supplier fields, fallback to checkoData
  const totalCases = (supplier as any)?.legalCasesCount ?? legal.total ?? 0
  const asClaimant = (supplier as any)?.legalCasesAsPlaintiff ?? legal.asPlaintiff ?? 0
  const asDefendant = (supplier as any)?.legalCasesAsDefendant ?? legal.asDefendant ?? 0
  const totalAmount = (supplier as any)?.legalCasesSum ?? legal.sum ?? 0
  
  const inspectionsCount = inspections.total ?? 0
  const inspectionsWithViolations = inspections.violations ?? 0
  
  const enforcementsCount = enforcements.count ?? 0
  const enforcementsAmount = enforcements.amount ?? 0
  
  // Company status
  const companyStatus = supplier?.companyStatus || checkoData?.Статус?.Наим || ""
  const isActive = !companyStatus.toLowerCase().includes("ликвидир") && 
                   !companyStatus.toLowerCase().includes("банкрот")
  
  // Company age
  const registrationDate = supplier?.registrationDate || checkoData?.ДатаРег
  let companyAge = 0
  if (registrationDate) {
    try {
      const regDate = new Date(registrationDate)
      const now = new Date()
      companyAge = Math.floor((now.getTime() - regDate.getTime()) / (1000 * 60 * 60 * 24 * 365))
    } catch {
      // Ignore date parsing errors
    }
  }
  
  // POSITIVE FACTORS
  if (isActive && companyAge > 3) {
    score += 10
    const reason = `Компания действует ${companyAge} лет`
    positive.push(reason)
    reasons.push(reason)
  }
  
  // Check revenue growth (2 years in a row)
  const financeYears = Object.keys(finances).sort().reverse()
  if (financeYears.length >= 2) {
    let revenueGrowing2Years = true
    for (let i = 0; i < Math.min(2, financeYears.length - 1); i++) {
      const currentYear = finances[financeYears[i]]
      const prevYear = finances[financeYears[i + 1]]
      if (currentYear?.["2110"] && prevYear?.["2110"]) {
        if (currentYear["2110"] <= prevYear["2110"]) {
          revenueGrowing2Years = false
          break
        }
      } else {
        revenueGrowing2Years = false
        break
      }
    }
    if (revenueGrowing2Years) {
      score += 5
      const reason = "Выручка растёт 2 года подряд"
      positive.push(reason)
      reasons.push(reason)
    }
  }
  
  if (enforcementsCount === 0) {
    score += 5
    const reason = "Нет исполнительных производств"
    positive.push(reason)
    reasons.push(reason)
  }
  
  if (inspectionsWithViolations === 0 && inspectionsCount > 0) {
    score += 5
    const reason = `Проверок без нарушений: ${inspectionsCount}`
    positive.push(reason)
    reasons.push(reason)
  }
  
  // NEGATIVE FACTORS
  if (enforcementsCount > 0) {
    score -= 20
    const reason = `Есть исполнительные производства: ${enforcementsCount}`
    negative.push(reason)
    reasons.push(reason)
  }
  
  const largeEnforcementThreshold = 5_000_000 // 5 млн руб
  if (enforcementsAmount > largeEnforcementThreshold) {
    score -= 10
    const reason = `Большая сумма долгов: ${formatCurrency(enforcementsAmount)}`
    negative.push(reason)
    reasons.push(reason)
  }
  
  const largeClaimThreshold = 100_000_000 // 100 млн руб
  if (totalAmount > largeClaimThreshold) {
    score -= 10
    const reason = `Большая сумма исков: ${formatCurrency(totalAmount)}`
    negative.push(reason)
    reasons.push(reason)
  }
  
  if (totalCases > 50 && asDefendant > 0) {
    score -= 10
    const reason = `Много арбитражных дел: всего ${totalCases}, ответчик в ${asDefendant}`
    negative.push(reason)
    reasons.push(reason)
  }
  
  if (inspectionsWithViolations > 0) {
    score -= 5
    const reason = `Проверок с нарушениями: ${inspectionsWithViolations}`
    attention.push(reason)
    reasons.push(reason)
  }
  
  // Company status penalty
  if (!isActive) {
    score = Math.min(score, 30)
    const reason = `Компания в статусе: ${companyStatus}`
    negative.push(reason)
    reasons.push(reason)
  }
  
  // Normalize score to 0-100
  score = Math.max(0, Math.min(100, score))
  
  // Determine level
  let level: ReliabilityLevel
  if (score >= 75) {
    level = 'high'
  } else if (score >= 50) {
    level = 'medium'
  } else {
    level = 'low'
  }
  
  return {
    level,
    score,
    reasons: reasons.slice(0, 5), // Max 5 reasons
    positive,
    attention,
    negative,
  }
}

/**
 * Calculate reliability rating based on Checko data (legacy function for backward compatibility)
 * Returns rating from 0 to 100, or uses rating from API if available
 */
export function calculateReliabilityRating(
  checkoData: any,
  supplier: any
): number {
  // If rating exists in API data, use it
  if (checkoData?.rating !== undefined && checkoData.rating !== null) {
    return checkoData.rating
  }
  if (checkoData?.Рейтинг !== undefined && checkoData.Рейтинг !== null) {
    return checkoData.Рейтинг
  }
  
  // Use new calculation function
  const result = calculateReliabilityScore(checkoData, supplier)
  return result.score
}

/**
 * Convert reliability rating (0-100) to stars (0-5)
 */
export function ratingToStars(rating: number): number {
  if (rating >= 80) return 5
  if (rating >= 60) return 4
  if (rating >= 40) return 3
  if (rating >= 20) return 2
  if (rating > 0) return 1
  return 0
}
