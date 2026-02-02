-- Оптимизация БД: Добавление индексов для B2B Platform
-- Дата: 16.01.2026

-- Индексы для moderator_suppliers
CREATE INDEX IF NOT EXISTS idx_suppliers_inn ON moderator_suppliers(inn);
CREATE INDEX IF NOT EXISTS idx_suppliers_domain ON moderator_suppliers(domain);
CREATE INDEX IF NOT EXISTS idx_suppliers_type ON moderator_suppliers(type);
CREATE INDEX IF NOT EXISTS idx_suppliers_created_at ON moderator_suppliers(created_at DESC);
CREATE INDEX IF NOT EXISTS idx_suppliers_type_created ON moderator_suppliers(type, created_at DESC);

-- Индексы для blacklist
CREATE INDEX IF NOT EXISTS idx_blacklist_domain ON blacklist(domain);
CREATE INDEX IF NOT EXISTS idx_blacklist_added_at ON blacklist(added_at DESC);

-- Индексы для parsing_runs
CREATE INDEX IF NOT EXISTS idx_parsing_runs_status ON parsing_runs(status);
CREATE INDEX IF NOT EXISTS idx_parsing_runs_keyword ON parsing_runs(keyword);
CREATE INDEX IF NOT EXISTS idx_parsing_runs_created_at ON parsing_runs(created_at DESC);
CREATE INDEX IF NOT EXISTS idx_parsing_runs_keyword_status ON parsing_runs(keyword, status);

-- Индексы для keywords
CREATE INDEX IF NOT EXISTS idx_keywords_keyword ON keywords(keyword);
CREATE INDEX IF NOT EXISTS idx_keywords_created_at ON keywords(created_at DESC);

-- Индексы для domains_queue
CREATE INDEX IF NOT EXISTS idx_domains_queue_domain ON domains_queue(domain);
CREATE INDEX IF NOT EXISTS idx_domains_queue_keyword ON domains_queue(keyword);
CREATE INDEX IF NOT EXISTS idx_domains_queue_parsing_run_id ON domains_queue(parsing_run_id);

-- Анализ таблиц после создания индексов
ANALYZE moderator_suppliers;
ANALYZE blacklist;
ANALYZE parsing_runs;
ANALYZE keywords;
ANALYZE domains_queue;
