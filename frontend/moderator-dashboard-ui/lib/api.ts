import type {
  SupplierDTO,
  KeywordDTO,
  BlacklistEntryDTO,
  ParsingRunDTO,
  DomainQueueEntryDTO,
  ParsingLogsDTO,
  INNExtractionBatchResponse,
  DomainParserBatchResponse,
  DomainParserStatusResponse,
  CabinetMessageDTO,
  CabinetComposeRequest,
  AttachmentDTO,
  CabinetSettingsDTO,
  CabinetStatsDTO,
  CabinetParsingRequestDTO,
  CabinetRequestSupplierDTO,
  CabinetRequestSupplierMessageDTO,
} from "./types"

const USE_PROXY = true
const DIRECT_API_URL = (() => {
  const envUrl = process.env.NEXT_PUBLIC_API_URL
  if (!envUrl) return "http://localhost:8000"

  if (typeof window !== "undefined" && window.location?.hostname === "localhost") {
    return envUrl.replace("127.0.0.1", "localhost")
  }

  return envUrl
})()
const PROXY_API_URL = "/api/proxy"

const API_BASE_URL = USE_PROXY ? PROXY_API_URL : DIRECT_API_URL

function isAbortLikeError(error: unknown): boolean {
  if (!error) return false
  const anyErr = error as any
  const name = typeof anyErr?.name === "string" ? anyErr.name : ""
  const message = typeof anyErr?.message === "string" ? anyErr.message : ""
  if (name === "AbortError") return true
  if (/\bAbortError\b/i.test(message)) return true
  if (/\baborted\b/i.test(message)) return true
  if (/\bcancel(l)?ed\b/i.test(message)) return true
  return false
}

export class APIError extends Error {
  constructor(
    message: string,
    public status: number,
    public data?: unknown,
  ) {
    super(message)
    this.name = "APIError"
  }
}

export async function uploadAttachment(file: File): Promise<AttachmentDTO> {
  const url = `${DIRECT_API_URL}/attachments/upload`

  const form = new FormData()
  form.append("file", file, file.name)

  const response = await fetch(url, {
    method: "POST",
    body: form,
    credentials: "include",
  })

  const data = (await response.json().catch(() => null)) as any
  if (!response.ok) {
    throw new APIError(data?.detail || data?.message || data?.error || `HTTP ${response.status}`, response.status, data)
  }

  return data as AttachmentDTO
}

/**
 * Выполняет API запрос с retry механизмом.
 * Повторяет запрос до 3 раз при временных ошибках (503, 504, network errors).
 */
export async function apiFetchWithRetry<T>(endpoint: string, options?: RequestInit, retries = 3): Promise<T> {
  for (let attempt = 0; attempt < retries; attempt++) {
    try {
      return await apiFetch<T>(endpoint, options)
    } catch (error) {
      // Если это последняя попытка, пробрасываем ошибку
      if (attempt === retries - 1) {
        throw error
      }

      // Не ретраим отмененные запросы
      if (error instanceof APIError && error.status === 499) {
        throw error
      }

      // Retry только для временных ошибок
      if (error instanceof APIError) {
        // Не повторяем для клиентских ошибок (4xx), кроме 408 (timeout)
        if (error.status >= 400 && error.status < 500 && error.status !== 408) {
          throw error
        }
        // Повторяем для серверных ошибок (5xx) и timeout (408)
        if (error.status >= 500 || error.status === 408 || error.status === 503 || error.status === 504) {
          const delay = 1000 * (attempt + 1) // Экспоненциальная задержка: 1s, 2s, 3s
          console.log(`[API Retry] Attempt ${attempt + 1}/${retries} failed, retrying in ${delay}ms...`)
          await new Promise((resolve) => setTimeout(resolve, delay))
          continue
        }
      }

      // Retry для network errors (TypeError с fetch)
      if (error instanceof TypeError && error.message.includes("fetch")) {
        const delay = 1000 * (attempt + 1)
        console.log(`[API Retry] Network error, retrying in ${delay}ms...`)
        await new Promise((resolve) => setTimeout(resolve, delay))
        continue
      }

      // Для других ошибок не повторяем
      throw error
    }
  }

  throw new APIError("Max retries exceeded", 500)
}

export async function apiFetch<T>(endpoint: string, options?: RequestInit): Promise<T> {
  // ВСЕГДА используем полный URL чтобы Next.js не перехватывал запросы
  const url = `${API_BASE_URL}${endpoint}`

  // Для DELETE запросов с body нужно явно указать Content-Type
  const headers: Record<string, string> = {
    ...((options?.headers as Record<string, string>) || {}),
  }

  // Check if using ngrok tunnel
  if (DIRECT_API_URL.includes("ngrok")) {
    headers["ngrok-skip-browser-warning"] = "true"
  }

  // Добавляем Content-Type только если есть body и метод не GET
  // Используем charset=utf-8 для корректной обработки кириллицы (из HANDOFF.md)
  const isFormDataBody = typeof FormData !== "undefined" && options?.body instanceof FormData

  if (options?.body && options.method !== "GET" && !isFormDataBody) {
    headers["Content-Type"] = "application/json; charset=utf-8"
  } else if (!options?.body && options?.method !== "GET" && options?.method !== "DELETE") {
    headers["Content-Type"] = "application/json; charset=utf-8"
  }

  // Добавляем credentials для включения cookies (включая auth_token)
  const credentials: RequestCredentials = "include"

  console.log("[v0] Fetching:", url)

  try {
    const response = await fetch(url, {
      ...options,
      headers,
      credentials,
    })

    // Для DELETE запросов со статусом 204 (No Content) возвращаем пустой объект
    // Для статуса 200 с body - парсим JSON (например, bulk delete возвращает {deleted, total})
    if (response.status === 204 && options?.method === "DELETE") {
      console.log(`[API Fetch] Success: ${response.status} for ${endpoint}`)
      return {} as T
    }

    if (!response.ok) {
      let errorData
      try {
        errorData = await response.json()
      } catch {
        const text = await response.text().catch(() => response.statusText)
        // Log to console for debugging
        console.error(`[API Error] ${response.status} ${response.statusText}:`, text)
        throw new APIError(`HTTP ${response.status}: ${response.statusText}`, response.status, { text })
      }

      // Extract detailed error message
      const errorMessage = errorData.detail || errorData.message || errorData.error || `HTTP ${response.status}`

      // Разные уровни логирования для разных статусов
      // 404 - ожидаемая ошибка (ресурс не найден), логируем как warning
      // 400 - ожидаемая ошибка (неверный запрос), логируем как warning
      // 401/403 - ожидаемая ошибка авторизации (например, сессия истекла), логируем как warning
      // 500+ - реальная ошибка сервера, логируем как error
      if (
        response.status === 404 ||
        response.status === 400 ||
        response.status === 401 ||
        response.status === 403
      ) {
        console.warn(`[API] ${response.status} ${errorMessage}:`, {
          endpoint: endpoint,
          url: url,
        })
      } else {
        console.error(`[API Error] ${response.status}:`, {
          message: errorMessage,
          data: errorData,
          url: url,
          endpoint: endpoint,
        })
      }

      throw new APIError(errorMessage, response.status, errorData)
    }

    // Пытаемся получить JSON, если есть
    const contentType = response.headers.get("content-type")
    if (contentType && contentType.includes("application/json")) {
      return await response.json()
    }

    // Если нет JSON, возвращаем пустой объект
    const text = await response.text()
    if (text) {
      try {
        return JSON.parse(text) as T
      } catch {
        return {} as T
      }
    }
    return {} as T
  } catch (error) {
    // Если это APIError, не логируем здесь - уже залогировано выше (строка 116)
    if (error instanceof APIError) {
      throw error
    }

    // Отмененные/прерванные запросы не считаем ошибкой "backend down" и не логируем как unexpected
    if (isAbortLikeError(error)) {
      throw new APIError("Request was cancelled", 499)
    }

    // В браузере same-origin запросы иногда падают как "TypeError: Failed to fetch" при net::ERR_ABORTED
    // (например, при быстрой навигации). Это не означает, что backend недоступен.
    if (
      typeof window !== "undefined" &&
      error instanceof TypeError &&
      typeof error.message === "string" &&
      error.message.toLowerCase().includes("failed to fetch") &&
      typeof url === "string" &&
      (url.startsWith("/") || url.startsWith(window.location.origin))
    ) {
      throw new APIError("Request was cancelled", 499)
    }

    // Более общий случай: same-origin GET может рваться как TypeError (любое fetch-сообщение)
    // при навигации/рендерах. Для GET это почти всегда отмена, а не реальная недоступность backend.
    if (
      typeof window !== "undefined" &&
      error instanceof TypeError &&
      typeof error.message === "string" &&
      error.message.toLowerCase().includes("fetch") &&
      (options?.method == null || options.method === "GET") &&
      typeof url === "string" &&
      (url.startsWith("/") || url.startsWith(window.location.origin))
    ) {
      throw new APIError("Request was cancelled", 499)
    }

    // Логируем только неожиданные ошибки
    if (error instanceof TypeError && error.message.includes("fetch")) {
      const connectionError = new APIError("Unable to connect to server. Please ensure the backend is running.", 503)
      console.error("[API Fetch] Connection error:", connectionError.message)
      throw connectionError
    }

    // Логируем только действительно неожиданные ошибки
    console.error("[API Fetch] Unexpected error:", {
      error: error,
      url: url,
      endpoint: endpoint,
      errorType: error instanceof Error ? error.constructor.name : typeof error,
      errorMessage: error instanceof Error ? error.message : String(error),
    })

    const unexpectedError = new APIError("An unexpected error occurred", 500)
    throw unexpectedError
  }
}

// Domains queue API
export async function getDomainsQueue(params?: {
  limit?: number
  offset?: number
  status?: string
  keyword?: string
  parsingRunId?: string
}): Promise<{
  entries: DomainQueueEntryDTO[]
  total: number
  limit: number
  offset: number
}> {
  const queryParams = new URLSearchParams()
  if (params?.limit) queryParams.append("limit", params.limit.toString())
  if (params?.offset) queryParams.append("offset", params.offset.toString())
  if (params?.status) queryParams.append("status", params.status)
  if (params?.keyword) queryParams.append("keyword", params.keyword)
  if (params?.parsingRunId) queryParams.append("parsingRunId", params.parsingRunId)

  const queryString = queryParams.toString()
  return apiFetch<{
    entries: DomainQueueEntryDTO[]
    total: number
    limit: number
    offset: number
  }>(`/domains/queue${queryString ? `?${queryString}` : ""}`)
}

// Parsing runs API
export async function getParsingRuns(params?: {
  limit?: number
  offset?: number
  status?: string
  keyword?: string
  sort?: string
  order?: "asc" | "desc"
}): Promise<{
  runs: ParsingRunDTO[]
  total: number
  limit: number
  offset: number
}> {
  const queryParams = new URLSearchParams()
  if (params?.limit) queryParams.append("limit", params.limit.toString())
  if (params?.offset) queryParams.append("offset", params.offset.toString())
  if (params?.status) queryParams.append("status", params.status)
  if (params?.keyword) queryParams.append("keyword", params.keyword)
  if (params?.sort) queryParams.append("sort", params.sort)
  if (params?.order) queryParams.append("order", params.order)

  const queryString = queryParams.toString()
  return apiFetch<{
    runs: ParsingRunDTO[]
    total: number
    limit: number
    offset: number
  }>(`/parsing/runs${queryString ? `?${queryString}` : ""}`)
}

export async function getParsingRun(runId: string): Promise<ParsingRunDTO> {
  return apiFetch<ParsingRunDTO>(`/parsing/runs/${runId}`)
}

export async function getParsingLogs(runId: string): Promise<{ run_id: string; parsing_logs: ParsingLogsDTO }> {
  const url = `${API_BASE_URL}/parsing/runs/${runId}/logs`

  try {
    const response = await fetch(url, {
      method: "GET",
      headers: {
        "Content-Type": "application/json; charset=utf-8",
      },
    })

    if (!response.ok) {
      // Для 404 ошибки не логируем в консоль - это нормальная ситуация, если run еще не создан
      if (response.status === 404) {
        throw new APIError("Parsing run not found", 404, {})
      }

      // Для других ошибок логируем
      let errorData
      try {
        errorData = await response.json()
      } catch {
        const text = await response.text().catch(() => response.statusText)
        throw new APIError(`HTTP ${response.status}: ${response.statusText}`, response.status, { text })
      }

      const errorMessage = errorData.detail || errorData.message || errorData.error || `HTTP ${response.status}`
      console.error(`[API Error] ${response.status}:`, {
        message: errorMessage,
        data: errorData,
        url: url,
        endpoint: `/parsing/runs/${runId}/logs`,
      })

      throw new APIError(errorMessage, response.status, errorData)
    }

    // Парсим JSON ответ
    const contentType = response.headers.get("content-type")
    if (contentType && contentType.includes("application/json")) {
      return await response.json()
    }

    // Если нет JSON, возвращаем пустой объект
    const text = await response.text()
    if (text) {
      try {
        return JSON.parse(text) as { run_id: string; parsing_logs: ParsingLogsDTO }
      } catch {
        return { run_id: runId, parsing_logs: {} as ParsingLogsDTO }
      }
    }
    return { run_id: runId, parsing_logs: {} as ParsingLogsDTO }
  } catch (error) {
    // Если это APIError с 404, пробрасываем его дальше без логирования
    if (error instanceof APIError && error.status === 404) {
      throw error
    }

    // Для других ошибок логируем
    console.error("[API Fetch] Unexpected error:", {
      error: error,
      url: url,
      endpoint: `/parsing/runs/${runId}/logs`,
      errorType: error instanceof Error ? error.constructor.name : typeof error,
      errorMessage: error instanceof Error ? error.message : String(error),
    })
    throw error
  }
}

// Suppliers API
export async function getSuppliers(params?: {
  limit?: number
  offset?: number
  type?: string
  recentDays?: number
  search?: string
}): Promise<{
  suppliers: SupplierDTO[]
  total: number
  limit: number
  offset: number
}> {
  const queryParams = new URLSearchParams()
  if (params?.limit) queryParams.append("limit", params.limit.toString())
  if (params?.offset) queryParams.append("offset", params.offset.toString())
  if (params?.type) queryParams.append("type", params.type)
  if (params?.recentDays) queryParams.append("recentDays", params.recentDays.toString())
  if (params?.search) queryParams.append("search", params.search)

  const queryString = queryParams.toString()
  return apiFetch<{
    suppliers: SupplierDTO[]
    total: number
    limit: number
    offset: number
  }>(`/moderator/suppliers${queryString ? `?${queryString}` : ""}`)
}

export async function getPendingDomains(params?: {
  limit?: number
  offset?: number
  search?: string
}): Promise<{
  entries: Array<{ domain: string; occurrences: number; last_seen_at?: string | null }>
  total: number
  limit: number
  offset: number
}> {
  const queryParams = new URLSearchParams()
  if (params?.limit) queryParams.append("limit", params.limit.toString())
  if (params?.offset) queryParams.append("offset", params.offset.toString())
  if (params?.search) queryParams.append("search", params.search)
  const queryString = queryParams.toString()
  return apiFetch(`/domains/pending${queryString ? `?${queryString}` : ""}`)
}

export async function enrichPendingDomain(domain: string): Promise<{
  domain: string
  inn?: string | null
  emails?: string[]
  status: string
  error?: string | null
  sourceUrls?: string[]
  extractionLog?: Array<{ url?: string; inn?: string; emails?: string[]; error?: string }>
  supplierType?: string | null
  dataStatus?: string | null
  reason?: string | null
}> {
  return apiFetch(`/domains/pending/enrich`, {
    method: "POST",
    body: JSON.stringify({ domain }),
  })
}

export async function clearPendingDomains(domains?: string[]): Promise<{ deleted: number }> {
  return apiFetch(`/domains/pending/clear`, {
    method: "POST",
    body: JSON.stringify({ domains: domains?.length ? domains : null }),
  })
}

// Blacklist API
export async function getBlacklist(params?: {
  limit?: number
  offset?: number
}): Promise<{
  entries: BlacklistEntryDTO[]
  total: number
  limit: number
  offset: number
}> {
  const queryParams = new URLSearchParams()
  if (params?.limit) queryParams.append("limit", params.limit.toString())
  if (params?.offset) queryParams.append("offset", params.offset.toString())

  const queryString = queryParams.toString()
  return apiFetch<{
    entries: BlacklistEntryDTO[]
    total: number
    limit: number
    offset: number
  }>(`/moderator/blacklist${queryString ? `?${queryString}` : ""}`)
}

export async function addToBlacklist(data: {
  domain: string
  reason?: string | null
  addedBy?: string | null
  parsingRunId?: string | null
}): Promise<BlacklistEntryDTO> {
  return apiFetch<BlacklistEntryDTO>("/moderator/blacklist", {
    method: "POST",
    body: JSON.stringify(data),
  })
}

export async function removeFromBlacklist(domain: string): Promise<void> {
  return apiFetch<void>(`/moderator/blacklist/${encodeURIComponent(domain)}`, {
    method: "DELETE",
  })
}

// Parsing API
export async function startParsing(data: {
  keyword: string
  depth: number
  source: "google" | "yandex" | "both"
}): Promise<ParsingRunDTO> {
  return apiFetch<ParsingRunDTO>("/parsing/start", {
    method: "POST",
    body: JSON.stringify(data),
  })
}

export async function deleteParsingRun(runId: string): Promise<void> {
  return apiFetch<void>(`/parsing/runs/${runId}`, {
    method: "DELETE",
  })
}

export async function deleteParsingRunsBulk(runIds: string[]): Promise<{
  deleted: number
  total: number
  errors?: string[]
}> {
  return apiFetch<{
    deleted: number
    total: number
    errors?: string[]
  }>("/parsing/runs/bulk", {
    method: "DELETE",
    body: JSON.stringify(runIds),
  })
}

// Checko API
export interface CheckoDataResponse {
  name?: string | null
  ogrn?: string | null
  kpp?: string | null
  okpo?: string | null
  companyStatus?: string | null
  registrationDate?: string | null
  legalAddress?: string | null
  phone?: string | null
  website?: string | null
  vk?: string | null
  telegram?: string | null
  authorizedCapital?: number | null
  revenue?: number | null
  profit?: number | null
  financeYear?: number | null
  legalCasesCount?: number | null
  legalCasesSum?: number | null
  legalCasesAsPlaintiff?: number | null
  legalCasesAsDefendant?: number | null
  checkoData: string
}

export interface CheckoHealthResponse {
  configured: boolean
  keysLoaded: number
}

export async function getCheckoHealth(): Promise<CheckoHealthResponse> {
  return apiFetchWithRetry<CheckoHealthResponse>("/moderator/checko/health", undefined, 2)
}

export async function getCheckoData(inn: string, forceRefresh?: boolean): Promise<CheckoDataResponse> {
  const params = new URLSearchParams()
  if (forceRefresh) {
    params.append("force_refresh", "true")
  }
  const queryString = params.toString()
  const url = `/moderator/checko/${inn}${queryString ? `?${queryString}` : ""}`
  return apiFetchWithRetry<CheckoDataResponse>(url, undefined, 3)
}

// Suppliers API
export async function createSupplier(data: {
  name: string
  inn?: string | null
  email?: string | null
  domain?: string | null
  emails?: string[] | null
  domains?: string[] | null
  address?: string | null
  type: "supplier" | "reseller"
  allowDuplicateInn?: boolean | null
  dataStatus?: string | null
  // Checko fields
  ogrn?: string | null
  kpp?: string | null
  okpo?: string | null
  companyStatus?: string | null
  registrationDate?: string | null
  legalAddress?: string | null
  phone?: string | null
  website?: string | null
  vk?: string | null
  telegram?: string | null
  authorizedCapital?: number | null
  revenue?: number | null
  profit?: number | null
  financeYear?: number | null
  legalCasesCount?: number | null
  legalCasesSum?: number | null
  legalCasesAsPlaintiff?: number | null
  legalCasesAsDefendant?: number | null
  checkoData?: string | null
}): Promise<SupplierDTO> {
  return apiFetch<SupplierDTO>("/moderator/suppliers", {
    method: "POST",
    body: JSON.stringify(data),
  })
}

export async function updateSupplier(
  supplierId: number,
  data: {
    name?: string
    inn?: string | null
    email?: string | null
    domain?: string | null
    emails?: string[] | null
    domains?: string[] | null
    address?: string | null
    type?: "supplier" | "reseller"
    allowDuplicateInn?: boolean | null
    dataStatus?: string | null
    // Checko fields
    ogrn?: string | null
    kpp?: string | null
    okpo?: string | null
    companyStatus?: string | null
    registrationDate?: string | null
    legalAddress?: string | null
    phone?: string | null
    website?: string | null
    vk?: string | null
    telegram?: string | null
    authorizedCapital?: number | null
    revenue?: number | null
    profit?: number | null
    financeYear?: number | null
    legalCasesCount?: number | null
    legalCasesSum?: number | null
    legalCasesAsPlaintiff?: number | null
    legalCasesAsDefendant?: number | null
    checkoData?: string | null
  },
): Promise<SupplierDTO> {
  return apiFetch<SupplierDTO>(`/moderator/suppliers/${supplierId}`, {
    method: "PUT",
    body: JSON.stringify(data),
  })
}

export async function attachDomainToSupplier(
  supplierId: number,
  payload: { domain: string; email?: string | null },
): Promise<SupplierDTO> {
  return apiFetch<SupplierDTO>(`/moderator/suppliers/${supplierId}/attach-domain`, {
    method: "POST",
    body: JSON.stringify(payload),
  })
}

export async function deleteSupplier(supplierId: number): Promise<void> {
  return apiFetch<void>(`/moderator/suppliers/${supplierId}`, {
    method: "DELETE",
  })
}

// Keywords API
export async function getKeywords(): Promise<{
  keywords: KeywordDTO[]
}> {
  return apiFetch<{
    keywords: KeywordDTO[]
  }>("/keywords")
}

export async function createKeyword(keyword: string): Promise<KeywordDTO> {
  return apiFetch<KeywordDTO>("/keywords", {
    method: "POST",
    body: JSON.stringify({ keyword }),
  })
}

export async function deleteKeyword(keywordId: number): Promise<void> {
  return apiFetch<void>(`/keywords/${keywordId}`, {
    method: "DELETE",
  })
}

// INN Extraction API
export async function extractINNBatch(domains: string[]): Promise<INNExtractionBatchResponse> {
  return apiFetch<INNExtractionBatchResponse>("/inn-extraction/extract-batch", {
    method: "POST",
    headers: {
      "Content-Type": "application/json",
    },
    body: JSON.stringify({ domains }),
  })
}

export async function startDomainParserBatch(runId: string, domains: string[], force?: boolean): Promise<DomainParserBatchResponse> {
  return apiFetch<DomainParserBatchResponse>("/domain-parser/extract-batch", {
    method: "POST",
    headers: {
      "Content-Type": "application/json",
    },
    body: JSON.stringify({ runId, domains, force: force || false }),
  })
}

export async function getDomainParserStatus(parserRunId: string): Promise<DomainParserStatusResponse> {
  return apiFetch<DomainParserStatusResponse>(`/domain-parser/status/${parserRunId}`)
}

export async function getDomainModerationDomains(limit = 5000): Promise<{ domains: string[]; total: number }> {
  return apiFetch<{ domains: string[]; total: number }>(`/domain-parser/moderation-domains?limit=${limit}`)
}

export async function pauseDomainParserWorker(): Promise<{ paused: boolean; message: string }> {
  return apiFetch<{ paused: boolean; message: string }>("/domain-parser/pause", { method: "POST" })
}

export async function resumeDomainParserWorker(): Promise<{ paused: boolean; message: string }> {
  return apiFetch<{ paused: boolean; message: string }>("/domain-parser/resume", { method: "POST" })
}

export interface DomainParserWorkerStatus {
  paused: boolean
  currentRun: {
    parserRunId: string
    runId: string
    keyword: string
    processed: number
    total: number
    currentDomain: string | null
    currentSourceUrls: string[]
    startedAt: string | null
  } | null
}

export async function getDomainParserWorkerStatus(): Promise<DomainParserWorkerStatus> {
  return apiFetch<DomainParserWorkerStatus>("/domain-parser/worker-status")
}

// Learning API
export interface LearnedItem {
  domain: string
  type: "inn" | "email"
  value: string
  sourceUrls: string[]
  urlPatterns: string[]
  learning: string
}

export interface LearningStatistics {
  totalLearned: number
  successRateBefore: number
  successRateAfter: number
}

export interface LearnManualInnResponse {
  runId: string
  learningSessionId: string | null
  learnedItems: LearnedItem[]
  statistics: LearningStatistics
}

export async function learnManualInn(
  runId: string,
  domain: string,
  inn: string,
  sourceUrl: string,
  learningSessionId?: string,
  sourceUrls?: string[],
): Promise<LearnManualInnResponse> {
  return apiFetch<LearnManualInnResponse>("/learning/learn-manual-inn", {
    method: "POST",
    headers: {
      "Content-Type": "application/json",
    },
    body: JSON.stringify({ runId, domain, inn, sourceUrl, sourceUrls, learningSessionId }),
  })
}

export async function getLearningStatistics(): Promise<LearningStatistics> {
  return apiFetch<LearningStatistics>("/learning/statistics")
}

export async function getLearnedSummary(limit = 10): Promise<{
  total_patterns: number
  inn_url_patterns: string[]
  email_url_patterns: string[]
  domains_learned: number
  statistics: LearningStatistics
}> {
  return apiFetch(`/learning/learned-summary?limit=${limit}`)
}

// Cabinet API
export async function getCabinetMessages(): Promise<CabinetMessageDTO[]> {
  return apiFetch<CabinetMessageDTO[]>("/cabinet/messages")
}

export async function getYandexMailMessages(params?: {
  limit?: number
  page?: number
  folder?: string
}): Promise<{
  messages: CabinetMessageDTO[]
  total: number
  page: number
  limit: number
  demo?: boolean
  error?: string
}> {
  const queryParams = new URLSearchParams()
  if (params?.limit) queryParams.append("limit", params.limit.toString())
  if (params?.page) queryParams.append("page", params.page.toString())
  if (params?.folder) queryParams.append("folder", params.folder)

  const queryString = queryParams.toString()
  const resp = await fetch(`/api/yandex/mail${queryString ? `?${queryString}` : ""}`, {
    method: "GET",
    headers: {
      "Content-Type": "application/json",
    },
    cache: "no-store",
  })

  const data = (await resp.json().catch(() => null)) as any
  if (!resp.ok) {
    return {
      messages: [],
      total: 0,
      page: params?.page || 1,
      limit: params?.limit || 20,
      demo: false,
      error: data?.error || data?.detail || `HTTP ${resp.status}`,
    }
  }

  return data
}

export async function getYandexMailMessage(id: string): Promise<{
  id: string
  subject: string
  from_email: string
  to_email: string
  date: string
  body?: string
  html?: string
  attachments_count?: number
  attachments?: AttachmentDTO[]
}> {
  const resp = await fetch(`/api/yandex/mail/${encodeURIComponent(id)}`, {
    method: "GET",
    headers: {
      "Content-Type": "application/json",
    },
    cache: "no-store",
  })

  const data = (await resp.json().catch(() => null)) as any
  if (!resp.ok) {
    return {
      id,
      subject: "",
      from_email: "",
      to_email: "",
      date: "",
      body: "",
      html: "",
      attachments_count: 0,
      attachments: [],
    }
  }

  return data
}

export async function unspamYandexMailMessage(id: string): Promise<{ success: boolean; moved?: boolean }> {
  const resp = await fetch(`/api/yandex/mail/${encodeURIComponent(id)}/unspam`, {
    method: "POST",
    headers: {
      "Content-Type": "application/json",
    },
    cache: "no-store",
  })

  const data = (await resp.json().catch(() => null)) as any
  if (!resp.ok) {
    throw new APIError(data?.error || data?.detail || `HTTP ${resp.status}`, resp.status, data)
  }

  return data
}

export async function sendYandexEmail(payload: {
  to_email: string
  subject: string
  body: string
}): Promise<{ success: boolean; message_id: string; status: string; demo?: boolean }> {
  const resp = await fetch("/api/yandex/mail", {
    method: "POST",
    headers: {
      "Content-Type": "application/json; charset=utf-8",
    },
    body: JSON.stringify(payload),
    cache: "no-store",
  })

  const data = (await resp.json().catch(() => null)) as any
  if (!resp.ok) {
    throw new APIError(data?.error || data?.detail || `HTTP ${resp.status}`, resp.status, data)
  }

  return data
}

export async function composeCabinetMessage(payload: CabinetComposeRequest): Promise<CabinetMessageDTO> {
  return apiFetch<CabinetMessageDTO>("/cabinet/messages/compose", {
    method: "POST",
    body: JSON.stringify(payload),
  })
}

export async function getCabinetSettings(): Promise<CabinetSettingsDTO> {
  return apiFetch<CabinetSettingsDTO>("/cabinet/settings")
}

export async function updateCabinetSettings(payload: CabinetSettingsDTO): Promise<CabinetSettingsDTO> {
  return apiFetch<CabinetSettingsDTO>("/cabinet/settings", {
    method: "PUT",
    body: JSON.stringify(payload),
  })
}

export async function changeCabinetPassword(oldPassword: string, newPassword: string): Promise<{ message: string }> {
  const query = new URLSearchParams({ old_password: oldPassword, new_password: newPassword }).toString()
  return apiFetch<{ message: string }>(`/cabinet/settings/change-password?${query}`, {
    method: "POST",
  })
}

export async function getCabinetStats(): Promise<CabinetStatsDTO> {
  return apiFetch<CabinetStatsDTO>("/cabinet/stats")
}

export async function getGroqStatus(): Promise<{ configured: boolean; available: boolean }> {
  return apiFetch<{ configured: boolean; available: boolean }>("/cabinet/groq/status")
}

export async function getCabinetRequests(params?: {
  limit?: number
  offset?: number
  submitted?: boolean
}): Promise<CabinetParsingRequestDTO[]> {
  const query = new URLSearchParams()
  if (params?.limit != null) query.set("limit", String(params.limit))
  if (params?.offset != null) query.set("offset", String(params.offset))
  if (params?.submitted != null) query.set("submitted", String(params.submitted))
  const qs = query.toString()
  return apiFetch<CabinetParsingRequestDTO[]>(`/cabinet/requests${qs ? `?${qs}` : ""}`)
}

export type ModeratorTaskDTO = {
  id: number
  request_id: number
  created_by: number
  title?: string | null
  status: string
  source: string
  depth: number
  created_at: string
  parsing_runs?: Array<{ run_id: string; status: string; created_at?: string | null; keyword?: string | null }>
}

export async function getModeratorTasks(params?: { limit?: number; offset?: number }): Promise<ModeratorTaskDTO[]> {
  const query = new URLSearchParams()
  if (params?.limit != null) query.set("limit", String(params.limit))
  if (params?.offset != null) query.set("offset", String(params.offset))
  const qs = query.toString()
  return apiFetch<ModeratorTaskDTO[]>(`/moderator/tasks${qs ? `?${qs}` : ""}`)
}

export type ModeratorDashboardStatsDTO = {
  domains_in_queue: number
  enrichment_domains_in_queue: number
  new_suppliers: number
  new_suppliers_week: number
  active_runs: number
  blacklist_count: number
  open_tasks: number
}

export async function getModeratorDashboardStats(): Promise<ModeratorDashboardStatsDTO> {
  return apiFetch<ModeratorDashboardStatsDTO>("/moderator/dashboard-stats")
}

export async function getCabinetRequest(requestId: number): Promise<CabinetParsingRequestDTO> {
  return apiFetch<CabinetParsingRequestDTO>(`/cabinet/requests/${encodeURIComponent(String(requestId))}`)
}

export async function createCabinetRequest(payload: {
  title: string
  keys?: string[]
  depth?: number
  source?: string
  comment?: string
}): Promise<CabinetParsingRequestDTO> {
  return apiFetch<CabinetParsingRequestDTO>("/cabinet/requests", {
    method: "POST",
    headers: {
      "Content-Type": "application/json",
    },
    body: JSON.stringify({
      title: payload.title,
      keys: payload.keys || [],
      depth: payload.depth ?? 5,
      source: payload.source ?? "google",
      comment: payload.comment ?? null,
    }),
  })
}

export async function updateCabinetRequest(
  requestId: number,
  payload: {
    title?: string
    keys?: string[]
    depth?: number
    source?: string
    comment?: string
  },
): Promise<CabinetParsingRequestDTO> {
  return apiFetch<CabinetParsingRequestDTO>(`/cabinet/requests/${encodeURIComponent(String(requestId))}`, {
    method: "PUT",
    headers: {
      "Content-Type": "application/json",
    },
    body: JSON.stringify(payload),
  })
}

export async function submitCabinetRequest(requestId: number): Promise<CabinetParsingRequestDTO> {
  return apiFetch<CabinetParsingRequestDTO>(`/cabinet/requests/${encodeURIComponent(String(requestId))}/submit`, {
    method: "POST",
  })
}

export async function bulkDeleteCabinetRequests(
  requestIds: number[],
): Promise<{ requested: number; deleted: number; skipped_submitted: number; not_found: number }> {
  return apiFetch<{ requested: number; deleted: number; skipped_submitted: number; not_found: number }>(
    `/cabinet/requests/bulk-delete`,
    {
      method: "POST",
      headers: {
        "Content-Type": "application/json",
      },
      body: JSON.stringify({
        ids: requestIds,
      }),
    },
  )
}

export async function uploadCabinetRequestPositions(requestId: number, file: File): Promise<CabinetParsingRequestDTO> {
  const form = new FormData()
  form.append("file", file, file.name)

  return apiFetch<CabinetParsingRequestDTO>(
    `/cabinet/requests/${encodeURIComponent(String(requestId))}/positions/upload`,
    {
      method: "POST",
      body: form,
    },
  )
}

export async function sendCabinetRequestEmailToSuppliersBulk(
  requestId: number,
  supplierIds: number[],
  payload?: { subject?: string; body?: string },
): Promise<{
  total_suppliers: number
  total_emails: number
  batches_sent: number
  results: Array<{ supplier_id: number; ok: boolean; emails: string[]; error?: string | null }>
}> {
  return apiFetch(
    `/cabinet/requests/${encodeURIComponent(String(requestId))}/suppliers/send-bulk`,
    {
      method: "POST",
      headers: {
        "Content-Type": "application/json",
      },
      body: JSON.stringify({
        supplier_ids: supplierIds,
        subject: payload?.subject ?? null,
        body: payload?.body ?? null,
      }),
    },
  )
}

export async function uploadCabinetRequestPositionsWithEngine(
  requestId: number,
  file: File,
  engine: "auto" | "structured" | "ocr" | "docling" = "auto",
): Promise<CabinetParsingRequestDTO> {
  const form = new FormData()
  form.append("file", file, file.name)

  const qs = `engine=${encodeURIComponent(engine)}`
  return apiFetch<CabinetParsingRequestDTO>(
    `/cabinet/requests/${encodeURIComponent(String(requestId))}/positions/upload?${qs}`,
    {
      method: "POST",
      body: form,
    },
  )
}

export async function uploadCabinetRequestPositionsWithEngineProof(
  requestId: number,
  file: File,
  engine: "auto" | "structured" | "ocr" | "docling" = "auto",
): Promise<{
  data: CabinetParsingRequestDTO
  groqUsed: boolean
  groqKeySource: string | null
  groqError: string | null
}> {
  const form = new FormData()
  form.append("file", file, file.name)

  const qs = `engine=${encodeURIComponent(engine)}`
  const endpoint = `/cabinet/requests/${encodeURIComponent(String(requestId))}/positions/upload?${qs}`
  const url = `${API_BASE_URL}${endpoint}`

  const response = await fetch(url, {
    method: "POST",
    body: form,
    credentials: "include",
  })

  const groqUsed = response.headers.get("x-groq-used") === "1"
  const groqKeySource = response.headers.get("x-groq-key-source")
  const groqError = response.headers.get("x-groq-error")

  const payload = (await response.json().catch(() => null)) as any
  if (!response.ok) {
    const errorMessage = payload?.detail || payload?.message || payload?.error || `HTTP ${response.status}`
    throw new APIError(errorMessage, response.status, payload)
  }

  return {
    data: payload as CabinetParsingRequestDTO,
    groqUsed,
    groqKeySource: groqKeySource ?? null,
    groqError: groqError ?? null,
  }
}

export async function getCabinetRequestSuppliers(requestId: number): Promise<CabinetRequestSupplierDTO[]> {
  return apiFetch<CabinetRequestSupplierDTO[]>(`/cabinet/requests/${encodeURIComponent(String(requestId))}/suppliers`)
}

export async function getCabinetRequestSupplierMessages(
  requestId: number,
  supplierId: number,
): Promise<CabinetRequestSupplierMessageDTO[]> {
  return apiFetch<CabinetRequestSupplierMessageDTO[]>(
    `/cabinet/requests/${encodeURIComponent(String(requestId))}/suppliers/${encodeURIComponent(String(supplierId))}/messages`,
  )
}

export async function sendCabinetRequestEmailToSupplier(
  requestId: number,
  supplierId: number,
  payload?: { subject?: string; body?: string },
): Promise<CabinetRequestSupplierDTO> {
  return apiFetch<CabinetRequestSupplierDTO>(
    `/cabinet/requests/${encodeURIComponent(String(requestId))}/suppliers/${encodeURIComponent(String(supplierId))}/send`,
    {
      method: "POST",
      body: JSON.stringify({
        subject: payload?.subject ?? null,
        body: payload?.body ?? null,
      }),
    },
  )
}

// Current Task API
export async function getCurrentTask(): Promise<import("./types").CurrentTaskDTO> {
  return apiFetch<import("./types").CurrentTaskDTO>("/moderator/current-task")
}

export async function getRunDomains(
  runId: string,
): Promise<{
  run_id: string
  domains: Array<{
    id: number
    run_id: string
    domain: string
    status: string
    reason: string | null
    attempted_urls: string[]
    inn_source_url: string | null
    email_source_url: string | null
    supplier_id: number | null
    checko_ok: boolean
    global_requires_moderation: boolean
  }>
  total: number
}> {
  return apiFetch(`/moderator/run-domains/${encodeURIComponent(runId)}`)
}

export async function manualResolveDomain(
  runDomainId: number,
  data: import("./types").ManualResolveRequest,
): Promise<import("./types").ManualResolveResponse> {
  return apiFetch<import("./types").ManualResolveResponse>(
    `/moderator/run-domains/${runDomainId}/manual-resolve`,
    {
      method: "POST",
      body: JSON.stringify(data),
    },
  )
}

// Domain Logs API
export interface DomainLogEntry {
  id: number
  domain: string
  run_id: string | null
  action: string
  message: string | null
  details: any
  created_at: string | null
}

export async function getDomainHistory(domain: string, limit = 50): Promise<{ domain: string; total: number; logs: DomainLogEntry[] }> {
  return apiFetch<{ domain: string; total: number; logs: DomainLogEntry[] }>(
    `/domain-logs/history/${encodeURIComponent(domain)}?limit=${limit}`,
  )
}

export async function startDomainParserForRun(
  runId: string,
): Promise<{ success: boolean; parser_run_id: string; pending_count: number; run_id: string }> {
  return apiFetch<{ success: boolean; parser_run_id: string; pending_count: number; run_id: string }>(
    `/moderator/current-task/${encodeURIComponent(runId)}/start-domain-parser`,
    { method: "POST" },
  )
}

export interface UnprocessedRun {
  run_id: string
  status: string
  created_at: string | null
  keyword: string
  total_domains: number
  pending_count: number
  processing_count: number
  supplier_count: number
  reseller_count: number
  moderation_count: number
  parser_active: boolean
}

export async function getUnprocessedRuns(): Promise<{ runs: UnprocessedRun[]; total: number }> {
  return apiFetch<{ runs: UnprocessedRun[]; total: number }>("/moderator/unprocessed-runs")
}

export async function resumeAllProcessing(): Promise<{
  success: boolean
  message: string
  run_id: string | null
  parser_run_id?: string
  pending_count?: number
  already_running?: boolean
}> {
  return apiFetch("/moderator/current-task/resume-all", { method: "POST" })
}
