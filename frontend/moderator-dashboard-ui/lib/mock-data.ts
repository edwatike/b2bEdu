'use client'

import type {
  SupplierDTO,
  KeywordDTO,
  BlacklistEntryDTO,
  ParsingRunDTO,
  DomainQueueEntryDTO,
  ParsingLogsDTO,
  CabinetSettingsDTO,
  CabinetStatsDTO,
  CabinetMessageDTO,
} from './types'

// Mock пользователь
export const mockUser = {
  id: 'mock-user-1',
  email: 'test@example.com',
  name: 'Test User',
  is_moderator: false,
  is_admin: false,
  created_at: new Date().toISOString(),
}

// Mock админ
export const mockAdmin = {
  id: 'mock-admin-1',
  email: 'admin@example.com',
  name: 'Admin User',
  is_moderator: true,
  is_admin: true,
  created_at: new Date().toISOString(),
}

// Mock поставщики
export const mockSuppliers: SupplierDTO[] = [
  {
    id: 'supplier-1',
    name: 'ООО "Эко-Продукты"',
    email: 'info@eco-products.ru',
    phone: '+7 (495) 123-45-67',
    website: 'https://eco-products.ru',
    inn: '7712345678',
    status: 'active',
    category: 'Пищевые продукты',
    created_at: new Date(Date.now() - 30 * 24 * 60 * 60 * 1000).toISOString(),
    rating: 4.5,
    reviews_count: 128,
  },
  {
    id: 'supplier-2',
    name: 'ПАО "Текстиль-Про"',
    email: 'sales@textile-pro.ru',
    phone: '+7 (812) 456-78-90',
    website: 'https://textile-pro.ru',
    inn: '7801234567',
    status: 'active',
    category: 'Текстиль',
    created_at: new Date(Date.now() - 60 * 24 * 60 * 60 * 1000).toISOString(),
    rating: 4.2,
    reviews_count: 95,
  },
  {
    id: 'supplier-3',
    name: 'ЗАО "Электротех"',
    email: 'contact@elektrotech.ru',
    phone: '+7 (343) 789-01-23',
    website: 'https://elektrotech.ru',
    inn: '6609876543',
    status: 'pending',
    category: 'Электротехника',
    created_at: new Date(Date.now() - 5 * 24 * 60 * 60 * 1000).toISOString(),
    rating: 3.8,
    reviews_count: 42,
  },
]

// Mock ключевые слова
export const mockKeywords: KeywordDTO[] = [
  {
    id: 'kw-1',
    text: 'органические продукты',
    category: 'еда',
    search_volume: 12500,
    competition: 0.65,
    created_at: new Date().toISOString(),
  },
  {
    id: 'kw-2',
    text: 'оптовая продажа текстиля',
    category: 'текстиль',
    search_volume: 8300,
    competition: 0.48,
    created_at: new Date().toISOString(),
  },
  {
    id: 'kw-3',
    text: 'промышленная электротехника',
    category: 'электроника',
    search_volume: 5200,
    competition: 0.72,
    created_at: new Date().toISOString(),
  },
]

// Mock черный список
export const mockBlacklist: BlacklistEntryDTO[] = [
  {
    id: 'bl-1',
    supplier_id: 'supplier-bad-1',
    supplier_name: 'ООО "Неблагонадежные Продавцы"',
    reason: 'Мошеннические схемы',
    added_by: 'admin@example.com',
    added_at: new Date(Date.now() - 90 * 24 * 60 * 60 * 1000).toISOString(),
  },
  {
    id: 'bl-2',
    supplier_id: 'supplier-bad-2',
    supplier_name: 'ИП "Подделка-Ком"',
    reason: 'Поддельная продукция',
    added_by: 'moderator@example.com',
    added_at: new Date(Date.now() - 45 * 24 * 60 * 60 * 1000).toISOString(),
  },
]

// Mock parsing runs
export const mockParsingRuns: ParsingRunDTO[] = [
  {
    id: 'run-1',
    name: 'Поиск поставщиков - Этап 1',
    status: 'completed',
    total_domains: 1250,
    processed_domains: 1250,
    found_suppliers: 87,
    started_at: new Date(Date.now() - 24 * 60 * 60 * 1000).toISOString(),
    completed_at: new Date(Date.now() - 12 * 60 * 60 * 1000).toISOString(),
    error_count: 3,
  },
  {
    id: 'run-2',
    name: 'Поиск поставщиков - Этап 2',
    status: 'in_progress',
    total_domains: 2100,
    processed_domains: 1456,
    found_suppliers: 142,
    started_at: new Date(Date.now() - 4 * 60 * 60 * 1000).toISOString(),
    completed_at: null,
    error_count: 7,
  },
]

// Mock статистика кабинета
export const mockCabinetStats: CabinetStatsDTO = {
  total_suppliers: 234,
  active_suppliers: 198,
  pending_suppliers: 36,
  total_messages: 1250,
  unread_messages: 14,
  parsing_runs: 12,
  last_parsing_date: new Date(Date.now() - 24 * 60 * 60 * 1000).toISOString(),
  total_keywords: 567,
  favorite_count: 45,
}

// Mock сообщения кабинета
export const mockCabinetMessages: CabinetMessageDTO[] = [
  {
    id: 'msg-1',
    from_user_id: 'supplier-1',
    from_user_name: 'Иван Петров',
    subject: 'Вопрос о ценах',
    preview: 'Могли бы вы предоставить оптовые цены?',
    read: false,
    created_at: new Date(Date.now() - 2 * 60 * 60 * 1000).toISOString(),
  },
  {
    id: 'msg-2',
    from_user_id: 'supplier-2',
    from_user_name: 'Анна Сидорова',
    subject: 'Доставка продукции',
    preview: 'Готовы ли вы принять заказ на минимальное количество?',
    read: true,
    created_at: new Date(Date.now() - 5 * 60 * 60 * 1000).toISOString(),
  },
]

// Mock настройки кабинета
export const mockCabinetSettings: CabinetSettingsDTO = {
  notifications_enabled: true,
  email_notifications: true,
  sms_notifications: false,
  language: 'ru',
  theme: 'dark',
  auto_parse_enabled: false,
}

// Функция для имитации задержки
export function delay(ms: number): Promise<void> {
  return new Promise((resolve) => setTimeout(resolve, ms))
}

// Функция для генерации случайной ошибки (для тестирования)
export function shouldFail(failRate: number = 0.1): boolean {
  return Math.random() < failRate
}
