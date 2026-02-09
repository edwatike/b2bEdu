-- Initial database schema for B2B Platform
-- PostgreSQL 15

-- Table: moderator_suppliers
CREATE TABLE IF NOT EXISTS moderator_suppliers (
    id SERIAL PRIMARY KEY,
    name VARCHAR(500) NOT NULL,
    inn VARCHAR(12),
    email VARCHAR(320),
    domain VARCHAR(255),
    address TEXT,
    type VARCHAR(32) NOT NULL DEFAULT 'supplier',
    
    -- Checko requisites
    ogrn VARCHAR(15),
    kpp VARCHAR(9),
    okpo VARCHAR(10),
    company_status VARCHAR(50),
    registration_date DATE,
    legal_address TEXT,
    
    -- Checko contacts
    phone VARCHAR(50),
    website VARCHAR(255),
    vk VARCHAR(100),
    telegram VARCHAR(100),
    
    -- Financial data
    authorized_capital BIGINT,
    revenue BIGINT,
    profit BIGINT,
    finance_year INTEGER,
    
    -- Legal cases
    legal_cases_count INTEGER,
    legal_cases_sum BIGINT,
    legal_cases_as_plaintiff INTEGER,
    legal_cases_as_defendant INTEGER,
    
    -- Full Checko data (JSON)
    checko_data TEXT,
    
    -- Metadata
    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    updated_at TIMESTAMP WITH TIME ZONE DEFAULT NOW()
);

CREATE INDEX idx_suppliers_inn ON moderator_suppliers(inn);
CREATE INDEX idx_suppliers_domain ON moderator_suppliers(domain);
CREATE INDEX idx_suppliers_type ON moderator_suppliers(type);

-- Table: keywords
CREATE TABLE IF NOT EXISTS keywords (
    id SERIAL PRIMARY KEY,
    keyword VARCHAR(255) NOT NULL UNIQUE,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW()
);

CREATE INDEX idx_keywords_keyword ON keywords(keyword);

-- Table: supplier_keywords (junction table)
CREATE TABLE IF NOT EXISTS supplier_keywords (
    supplier_id INTEGER NOT NULL,
    keyword_id INTEGER NOT NULL,
    url_count INTEGER DEFAULT 1 NOT NULL,
    parsing_run_id VARCHAR(255),
    first_url TEXT,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    
    PRIMARY KEY (supplier_id, keyword_id),
    FOREIGN KEY (supplier_id) REFERENCES moderator_suppliers(id) ON DELETE CASCADE,
    FOREIGN KEY (keyword_id) REFERENCES keywords(id) ON DELETE CASCADE
);

-- Table: blacklist
CREATE TABLE IF NOT EXISTS blacklist (
    domain VARCHAR(255) PRIMARY KEY,
    reason TEXT,
    added_by VARCHAR(255),
    added_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    parsing_run_id VARCHAR(255)
);

CREATE INDEX idx_blacklist_domain ON blacklist(domain);

-- Table: parsing_runs
CREATE TABLE IF NOT EXISTS parsing_runs (
    run_id VARCHAR(255) PRIMARY KEY,
    keyword VARCHAR(255) NOT NULL,
    status VARCHAR(50) NOT NULL,
    started_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    finished_at TIMESTAMP WITH TIME ZONE,
    error TEXT,
    results_count INTEGER,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW()
);

CREATE INDEX idx_parsing_runs_keyword ON parsing_runs(keyword);
CREATE INDEX idx_parsing_runs_status ON parsing_runs(status);

-- Table: domains_queue
CREATE TABLE IF NOT EXISTS domains_queue (
    domain VARCHAR(255) PRIMARY KEY,
    keyword VARCHAR(255) NOT NULL,
    url TEXT NOT NULL,
    parsing_run_id VARCHAR(255),
    status VARCHAR(50) DEFAULT 'pending' NOT NULL,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW()
);

CREATE INDEX idx_domains_queue_status ON domains_queue(status);
CREATE INDEX idx_domains_queue_keyword ON domains_queue(keyword);

