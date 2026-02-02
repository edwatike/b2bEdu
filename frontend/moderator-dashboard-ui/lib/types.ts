export interface SupplierDTO {
  id: number
  name: string
  inn: string | null
  email: string | null
  domain: string | null
  address: string | null
  type: "supplier" | "reseller"
  
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
  
  createdAt: string
  updatedAt: string
}

export interface SupplierKeyword {
  keyword: string
  urlCount: number
  runId: string | null
  firstUrl: string | null
}

export interface KeywordDTO {
  id: number
  keyword: string
  createdAt: string
}

export interface BlacklistEntryDTO {
  domain: string
  reason: string | null
  addedBy: string | null
  addedAt: string | null
  parsingRunId: string | null
}

export interface ParsingRunDTO {
  run_id?: string  // Backend возвращает snake_case
  runId?: string  // Для обратной совместимости
  keyword: string
  status: string  // Может быть любым статусом, не только "running" | "completed" | "failed"
  started_at?: string | null  // Backend возвращает snake_case
  startedAt?: string | null  // Для обратной совместимости
  finished_at?: string | null  // Backend возвращает snake_case
  finishedAt?: string | null  // Для обратной совместимости
  error_message?: string | null  // Backend возвращает snake_case
  error?: string | null  // Для обратной совместимости
  resultsCount: number | null
  created_at?: string  // Backend возвращает snake_case
  createdAt?: string  // Для обратной совместимости
  depth?: number  // Глубина парсинга
  source?: string | null  // Source for parsing: 'google', 'yandex', or 'both'
  process_log?: {
    total_domains?: number
    source_statistics?: {
      google: number
      yandex: number
      both: number
    }
    duration_seconds?: number
    captcha_detected?: boolean
    started_at?: string
    finished_at?: string
    error?: string
  } | null
  processLog?: {
    total_domains?: number
    source_statistics?: {
      google: number
      yandex: number
      both: number
    }
    duration_seconds?: number
    captcha_detected?: boolean
    started_at?: string
    finished_at?: string
    error?: string
    parsing_logs?: ParsingLogsDTO  // Structured parsing logs from parser service
  } | null  // Для обратной совместимости (camelCase)
}

export interface ParsingLogsDTO {
  google?: {
    links_by_page: Record<number, number>  // Page number -> number of links found
    total_links: number
    last_links: string[]  // Last 20 links found
    pages_processed: number
  }
  yandex?: {
    links_by_page: Record<number, number>  // Page number -> number of links found
    total_links: number
    last_links: string[]  // Last 20 links found
    pages_processed: number
  }
}

export interface DomainQueueEntryDTO {
  domain: string
  keyword: string
  url: string
  parsingRunId: string | null
  source?: string | null  // Source of the URL: google, yandex, or both
  status: string
  createdAt: string
}

export interface ParsingDomainGroup {
  domain: string
  urls: Array<{
    url: string
    keyword: string
    source?: string | null  // Source of the URL: google, yandex, or both
    status: string
    createdAt: string
  }>
  totalUrls: number
  supplierType?: "supplier" | "reseller" | null  // Тип поставщика, если домен найден в базе
  supplierId?: number | null  // ID поставщика для редактирования
  sources?: string[]  // Массив источников URL (google, yandex или оба)
}

export interface INNExtractionProof {
  url: string  // URL откуда взят ИНН
  context: string  // Фрагмент текста (50-100 символов вокруг ИНН)
  method: "regex" | "ollama"  // Метод извлечения
  confidence?: "high" | "medium" | "low"  // Уверенность (для Ollama)
}

export interface INNExtractionResult {
  domain: string
  status: "success" | "not_found" | "error"
  inn: string | null
  proof: INNExtractionProof | null
  error?: string
  processingTime?: number  // Время обработки в мс
}

export interface INNExtractionBatchResponse {
  results: INNExtractionResult[]
  total: number
  processed: number
  successful: number
  failed: number
  notFound: number
}


export interface DomainParserResult {
  domain: string
  inn: string | null
  emails: string[]
  sourceUrls: string[]
  error?: string | null
}

export interface DomainParserBatchResponse {
  runId: string
  parserRunId: string
}

export interface DomainParserStatusResponse {
  runId: string
  parserRunId: string
  status: "running" | "completed" | "failed"
  processed: number
  total: number
  results: DomainParserResult[]
}

export interface CometExtractionResult {
  domain: string
  inn?: string | null
  emails?: string[]
  phones?: string[]
  sourceUrl?: string
  error?: string
  status?: "success" | "error" | "not_found"
}

export interface CometExtractBatchResponse {
  runId: string
  cometRunId: string
}

export interface CabinetMessageDTO {
  id: string
  subject: string
  from_email: string
  to_email: string
  status: "sent" | "replied" | "waiting" | "received"
  date: string
  attachments_count: number
  body?: string // Добавлено для содержимого писем
  is_read?: boolean
  html?: string
  attachments?: AttachmentDTO[]
}

export interface AttachmentDTO {
  id: string
  filename: string
  content_type?: string | null
  size: number
}

export interface CabinetComposeRequest {
  to_email: string
  subject: string
  body: string
  attachments?: string[]
}

export interface CabinetSettingsDTO {
  email?: string | null
  app_password?: string | null
  two_fa_enabled: boolean
  organization_name?: string | null
  organization_verified: boolean
  openai_api_key?: string | null
  openai_api_key_configured?: boolean
  groq_api_key?: string | null
  groq_api_key_configured?: boolean
}

export interface CabinetStatsDTO {
  total_requests: number
  sent_messages: number
  replied_messages: number
  waiting_messages: number
  email_configured: boolean
  two_fa_enabled: boolean
  organization_verified: boolean
}

export interface CabinetParsingRequestDTO {
  id: number
  title?: string | null
  raw_keys_json?: string | null
  depth?: number | null
  source?: string | null
  comment?: string | null
  created_at?: string | null
  updated_at?: string | null
  submitted_to_moderator?: boolean
  submitted_at?: string | null
}

export interface CabinetRequestSupplierDTO {
  supplier_id: number
  name: string
  email?: string | null
  emails?: string[] | null
  phone?: string | null
  domain?: string | null
  status: "waiting" | "sent" | "replied"
  last_error?: string | null
}

export interface CabinetRequestSupplierMessageDTO {
  id: string
  direction: "out" | "in"
  subject: string
  body: string
  date: string
}
