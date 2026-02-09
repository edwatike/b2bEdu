# Smart Parser Architecture

## Overview
The Smart Parser architecture optimizes the domain enrichment process by implementing a multi-strategy approach. Instead of defaulting to the resource-intensive Playwright browser for every domain, the system now intelligently selects the most efficient extraction method.

## Strategy Tiers

### Tier 1: HTTP Probe (Fastest)
- **Method**: Async HTTP GET requests (`httpx`).
- **Target**: Main page + common contact pages (`/contacts`, `/about`, `/requisites`, `/legal`, etc.).
- **Cost**: Very low (~200-800ms).
- **Extraction**:
  - Plain text INN/Email extraction (Regex).
  - HTML meta tags and Microdata sniffing.
  - Link extraction for deeper probing.

### Tier 2: API Sniffing (Fast)
- **Method**: Analysis of embedded JSON data in HTML.
- **Targets**:
  - `__NEXT_DATA__` (Next.js hydration state).
  - `__NUXT__` (Nuxt.js state).
  - `application/ld+json` (Schema.org structured data).
  - `window.initialState` patterns.
- **Cost**: Zero additional overhead (performed on Tier 1 HTML).

### Tier 3: Playwright Browser (Fallback)
- **Method**: Full headless Chrome browser automation.
- **Triggers**: Only if Tier 1 & 2 fail to find an INN.
- **Features**:
  - SPA rendering (Single Page Applications).
  - Dynamic content loading.
  - Screenshot analysis (optional future).
- **Cost**: High (RAM, CPU, Time: ~10-30s).

## Architecture Components

### 1. Strategy Router (`DomainInfoParser.parse_domain`)
Orchestrates the execution flow:
1. Checks **Learning Engine** for cached domain strategy.
2. Executes **HTTP Probe**.
3. Analyzes results (INN found?).
4. If success: Returns immediately (skips Playwright).
5. If failure: Falls back to **Playwright**.

### 2. Learning Engine (`LearningEngine`)
- **Role**: Memorizes which strategy works for a specific domain.
- **Storage**: `learning_patterns.json` -> `strategy_cache`.
- **Logic**: If a domain was successfully parsed via HTTP in the past, the system notes this (telemetry) to prioritize HTTP paths.

### 3. Telemetry & logging
New fields added to `run_domains` and `process_log`:
- `strategy`: The strategy that successfully extracted data (`http`, `api_sniff:json-ld`, `playwright`).
- `strategyTimeMs`: Execution time in milliseconds.

## Performance Impact
- **Static Sites**: 10x faster (2s vs 20s).
- **Resource Usage**: Significant reduction in RAM/CPU usage by skipping browser launch for ~40-60% of domains (estimated).
- **Success Rate**: Maintained or improved (due to better coverage of technical pages via HTTP).

## Database Schema Changes
- **run_domains**: `attempted_urls` JSONB column now includes `strategy` and `strategyTimeMs`.
- **API DTOs**: Updated to return these fields to the frontend.
