-- Миграция: Добавление индексов для оптимизации производительности
-- Дата создания: 2025-12-29
-- Описание: Добавляет индексы на часто используемые поля для ускорения запросов

-- ============================================
-- Индексы для таблицы domains_queue
-- ============================================

-- Индекс для поиска по keyword (используется при загрузке URL для ключей)
CREATE INDEX IF NOT EXISTS idx_domains_queue_keyword ON domains_queue(keyword);

-- Индекс для поиска по domain (используется при фильтрации blacklist и группировке)
CREATE INDEX IF NOT EXISTS idx_domains_queue_domain ON domains_queue(domain);

-- Индекс для поиска по parsing_run_id (используется при загрузке результатов парсинга)
CREATE INDEX IF NOT EXISTS idx_domains_queue_parsing_run_id ON domains_queue(parsing_run_id);

-- Композитный индекс для частых запросов (keyword + parsing_run_id)
CREATE INDEX IF NOT EXISTS idx_domains_queue_keyword_run_id ON domains_queue(keyword, parsing_run_id);

-- ============================================
-- Индексы для таблицы moderator_suppliers
-- ============================================

-- Индекс для поиска по domain (используется при определении статуса домена)
CREATE INDEX IF NOT EXISTS idx_suppliers_domain ON moderator_suppliers(domain);

-- Индекс для поиска по type (используется при фильтрации поставщиков/реселлеров)
CREATE INDEX IF NOT EXISTS idx_suppliers_type ON moderator_suppliers(type);

-- ============================================
-- Индексы для таблицы blacklist
-- ============================================

-- Индекс для поиска по domain (используется при фильтрации blacklist)
CREATE INDEX IF NOT EXISTS idx_blacklist_domain ON blacklist(domain);

-- ============================================
-- Комментарии к индексам
-- ============================================

COMMENT ON INDEX idx_domains_queue_keyword IS 'Ускоряет поиск URL по ключевому слову';
COMMENT ON INDEX idx_domains_queue_domain IS 'Ускоряет фильтрацию и группировку по доменам';
COMMENT ON INDEX idx_domains_queue_parsing_run_id IS 'Ускоряет загрузку результатов парсинга';
COMMENT ON INDEX idx_domains_queue_keyword_run_id IS 'Ускоряет комбинированные запросы по keyword и parsing_run_id';
COMMENT ON INDEX idx_suppliers_domain IS 'Ускоряет поиск поставщиков по домену';
COMMENT ON INDEX idx_suppliers_type IS 'Ускоряет фильтрацию по типу (supplier/reseller)';
COMMENT ON INDEX idx_blacklist_domain IS 'Ускоряет проверку доменов в blacklist';

