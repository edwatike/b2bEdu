# PROJECT PLAYBOOK — B2B Supplier Discovery Platform

> **Single Source of Truth** | Обновлено: 2026-02-07 17:28 UTC+3  
> Frontend Build Gate: ✅ GREEN | `tsc --noEmit` exit 0 | `next build` exit 0 (44 pages)  
> Backend Auth Audit: ✅ **ALL ENDPOINTS PROTECTED** (26 gaps → 0)  
> Evidence: `docs/verification/backend/route_dump_after_auth.txt`, `docs/verification/backend/grep_evidence_backend_after.txt`

---

## 1. TL;DR

B2B-платформа: парсинг Google/Yandex → извлечение ИНН/email → управление поставщиками. Три сервиса, три роли. Backend auth hardened (2026-02-07).

| Сервис | Порт | Статус | Evidence |
|--------|------|--------|----------|
| Frontend (Next.js 16) | 3000 | **VERIFIED** | `next.config.mjs:33` |
| Backend (FastAPI) | 8000 | **VERIFIED** | `backend/app/main.py:1027-1072` |
| Parser | 9000 | **VERIFIED** | `next.config.mjs:48` CSP connect-src |

**Запуск:** `D:\b2b\B2BLauncher.exe` — **VERIFIED** (`D:\b2b\docs\launcher.md`, 5469 bytes)

**Роли** — **VERIFIED** (`components/auth-guard.tsx`):
- **admin** — суперсет (`auth-guard.tsx:42`)
- **moderator** — парсинг, поставщики, blacklist, keywords, settings
- **user** — только `/cabinet/*`

---

## 2. Архитектура (as-is)

### 2.1 Компоненты — **VERIFIED**

```
Browser → Frontend (Next.js 16, :3000)
              ↓ /api/proxy/[...path] (Bearer token из cookie)
          Backend (FastAPI, :8000) → PostgreSQL (asyncpg)
          Parser Service (:9000)  → Google/Yandex SERP + Domain Parser
```

Evidence: proxy `route.ts:1-186`, token `route.ts:39-42`, API client `lib/api.ts:21-34`, routers `main.py:1027-1072`

### 2.2 Потоки данных — **VERIFIED**

| Поток | Описание | Evidence |
|-------|----------|----------|
| Парсинг SERP | Keyword → Backend → Parser → domains_queue | `page-optimized.tsx:13` |
| Domain Parser | Домены → extract-batch → polling status | `page.tsx:1313-1383` |
| AutoSave | Parser done → frontend создаёт suppliers + Checko | `page.tsx:320-501` |
| Learning | Ручной ИНН → learn-manual-inn | `page.tsx:791-835` |

### 2.3 Хранение состояния — **PARTIAL**

| Хранилище | Что хранит | Статус | Evidence |
|-----------|-----------|--------|----------|
| PostgreSQL | suppliers, domains_queue, blacklist, parsing_runs, users | **VERIFIED** | `main.py:102-196` DDL |
| localStorage | `parser-results-{runId}` | **VERIFIED** | `page.tsx:225-261` |
| React Query cache | API-ответы | **VERIFIED** | `query-provider.tsx` |
| In-memory cache | Suppliers, blacklist (per-session) | **VERIFIED** | `lib/cache.ts` |

### 2.4 Security Headers — **VERIFIED**

Evidence: `next.config.mjs:40-71` — CSP `default-src 'self'`, connect-src `127.0.0.1:8000/9000`, `X-Frame-Options: DENY`, `nosniff`, HSTS

---

## 3. Сервисы и порты

| Сервис | Порт | Конфиг | Статус |
|--------|------|--------|--------|
| Frontend | 3000 | `next.config.mjs:33` | **VERIFIED** |
| Backend | 8000 | `backend/run_api.py`, `backend/app/main.py` | **VERIFIED** |
| Parser | 9000 | `parser_service/` | **PARTIAL** (конфиг не проверен) |
| PostgreSQL | 5432 | `docker-compose.yml` (5348 bytes) | **PARTIAL** |

---

## 4. RBAC

### 4.1 Frontend AuthGuard — **VERIFIED**

Evidence: `components/auth-guard.tsx:13-50`

| Механизм | Evidence |
|----------|----------|
| Auth check: `fetch("/api/auth/status")` | `auth-guard.tsx:24-26` |
| Role: `data.user.role` | `auth-guard.tsx:27` |
| Moderator gate: `can_access_moderator` | `auth-guard.tsx:28,31-37` |
| Admin суперсет: `role === "admin"` | `auth-guard.tsx:42` |

**Покрытие по страницам (100% frontend routes):**

| Route | allowedRoles | Evidence |
|-------|-------------|----------|
| `/moderator` | `["moderator"]` | `page-optimized.tsx:129,139` |
| `/keywords` | `["moderator"]` | `keywords/page.tsx:525` |
| `/parsing-runs` | `["moderator"]` | `parsing-runs/page.tsx:367` |
| `/parsing-runs/[runId]` | `["moderator"]` | `page.tsx:2613` |
| `/suppliers/*` (4 routes) | `["moderator"]` | `page.tsx:8`, `[id]/page.tsx:28`, `edit/page.tsx:20`, `new/page.tsx:10` |
| `/blacklist` | `["moderator"]` | `page.tsx:261` |
| `/domains` | `["moderator"]` | `page.tsx:20` |
| `/settings` | `["moderator"]` | `page.tsx:156` |
| `/manual-parsing` | `["moderator"]` | `page.tsx:216` |
| `/moderator/tasks` | `["moderator"]` | `tasks/page.tsx:448` |
| `/users` | `["moderator", "admin"]` | `page.tsx:293` |
| `/cabinet/*` (8 routes) | `["user", "moderator"]` | `cabinet/*/page.tsx` |

### 4.2 Backend Auth — **VERIFIED** ✅ HARDENED (2026-02-07)

Evidence: `docs/verification/backend/route_dump_after_auth.txt`, `docs/verification/backend/grep_evidence_backend_after.txt`

**Все endpoints защищены.** 14/14 router files имеют `Depends(get_current_user)`.

| Prefix | File | Auth | Статус |
|--------|------|------|--------|
| `/moderator/suppliers/*` | `moderator_suppliers.py` | AUTH+MOD | **VERIFIED** |
| `/moderator/users/*` | `moderator_users.py` | AUTH+MOD | **VERIFIED** (dev-bypass removed) |
| `/moderator/blacklist*` | `blacklist.py` | AUTH+MOD | **VERIFIED** |
| `/moderator/checko/*` | `checko.py` | AUTH+MOD | **VERIFIED** (was gap) |
| `/keywords/*` | `keywords.py` | AUTH+MOD | **VERIFIED** |
| `/domains/*` | `domains_queue.py` | AUTH+MOD | **VERIFIED** (dev-bypass removed) |
| `/parsing/*` | `parsing_runs.py`, `parsing.py` | AUTH+MOD | **VERIFIED** (was gap) |
| `/domain-parser/*` | `domain_parser.py` | AUTH+MOD | **VERIFIED** (was gap) |
| `/learning/*` | `learning.py` | AUTH+MOD | **VERIFIED** (was gap) |
| `/api/mail/yandex/*` | `mail.py` | AUTH+MOD | **VERIFIED** (was gap) |
| `/attachments/*` | `attachments.py` | AUTH+MOD | **VERIFIED** (was gap) |
| `/cabinet/*` | `cabinet.py` | AUTH | **VERIFIED** — user-level |
| `/api/auth/me` | `auth.py` | AUTH | **VERIFIED** |

**Intentionally public (4):** `/health`, `/api/auth/yandex-oauth`, `/api/auth/status`, `/api/auth/logout`

### 4.3 require_moderator — UNIFIED ✅

1 реализация в `app/utils/authz.py` (NO dev-bypass). Все роутеры импортируют из неё.

| До | После |
|----|-------|
| 5 локальных копий в 5 файлах | 1 в `app/utils/authz.py` |
| 2 с dev-bypass (moderator_users, domains_queue) | 0 dev-bypass |
| 7 файлов без auth | 0 файлов без auth |

---

## 5. Security Findings

### 5.1 RESOLVED (2026-02-07) ✅

| # | Finding | Resolution | Evidence |
|---|---------|------------|----------|
| S1 | `/parsing/*` — 9 endpoints без auth | ✅ FIXED: AUTH+MOD added | `route_dump_after_auth.txt` |
| S2 | `/domain-parser/*` — 3 endpoints без auth | ✅ FIXED: AUTH+MOD added | `route_dump_after_auth.txt` |
| S3 | `/learning/*` — 3 endpoints без auth | ✅ FIXED: AUTH+MOD added | `route_dump_after_auth.txt` |
| S4 | `/api/mail/yandex/*` — 6 endpoints без auth | ✅ FIXED: AUTH+MOD added | `route_dump_after_auth.txt` |
| S7 | `/moderator/checko/*` — 2 endpoints без auth | ✅ FIXED: AUTH+MOD added | `route_dump_after_auth.txt` |
| S8 | `/attachments/*` — 3 endpoints без auth | ✅ FIXED: AUTH+MOD added | `route_dump_after_auth.txt` |
| S9 | `_require_moderator` dev-bypass в 2/5 файлах | ✅ FIXED: unified, no bypass | `grep_evidence_backend_after.txt` |
| S10 | 5 копий `_require_moderator` (DRY violation) | ✅ FIXED: 1 in `authz.py` | `grep_evidence_backend_after.txt` |

### 5.2 RESOLVED (P1 pass, 2026-02-07) ✅

| # | Finding | Resolution | Evidence |
|---|---------|------------|----------|
| S11 | Rate limiting отсутствует | ✅ FIXED: slowapi + PathRateLimitMiddleware | `rate_limit_notes.txt` |
| S12 | Request timeout для heavy endpoints | ✅ VERIFIED: already handled (BackgroundTasks + asyncio.wait_for) | `timeout_or_jobs_notes.txt` |
| S13 | Inconsistent error format | ✅ FIXED: unified {error,detail,status,path,timestamp} | `error_format_examples.txt` |

### 5.3 REMAINING

| # | Finding | Impact | Status |
|---|---------|--------|--------|
| S5 | Frontend proxy не проверяет роли | Только пробрасывает token | **OPEN** — backend now enforces |
| S6 | Нет `middleware.ts` | Нет server-side route protection | **OPEN** — P1 |

### 5.4 DB Constraints — **VERIFIED**

Evidence: `backend/app/main.py:102-153`

| Constraint | Type | Evidence |
|-----------|------|----------|
| `ux_suppliers_inn_unique` | UNIQUE INDEX (conditional) | `main.py:147-153` |
| `uq_supplier_domains_supplier_domain` | UNIQUE | `main.py:116` |
| `uq_supplier_emails_supplier_email` | UNIQUE | `main.py:141` |

---

## 6. Engineering Gate — **VERIFIED**

### 6.1 Frontend Build Gate

```bash
# 1. Type-check
npx tsc --noEmit
# 2. Build (с защитой от OOM)
$env:NODE_OPTIONS="--max-old-space-size=4096"; npx next build
```

**Последний прогон: 2026-02-07 17:03 UTC+3**

| Команда | Результат | Evidence |
|---------|-----------|----------|
| `tsc --noEmit` | ✅ exit 0, 0 errors | `docs/verification/frontend_build_2026-02-07.log` |
| `next build` | ✅ exit 0, 44 pages | `docs/verification/frontend_build_2026-02-07.log` |

### 6.2 Build Parameters — **VERIFIED**

| Параметр | Значение | Evidence |
|----------|----------|----------|
| `webpackMemoryOptimizations` | `true` | `next.config.mjs:24` |
| `productionBrowserSourceMaps` | `false` | `next.config.mjs:20` |
| `optimizeCss` | `true` | `next.config.mjs:22` |
| `optimizePackageImports` | `['lucide-react', '@radix-ui/react-dialog']` | `next.config.mjs:23` |
| `ignoreBuildErrors` | `false` | `next.config.mjs:27` |

### 6.3 Backend Security / Reliability Gate — **VERIFIED** ✅

| Check | Status | Evidence |
|-------|--------|----------|
| `get_current_user` on all endpoints | ✅ 14/14 routers | `grep_evidence_backend_after.txt` |
| `require_moderator` unified (no dev-bypass) | ✅ 1 in `authz.py` | `grep_evidence_backend_after.txt` |
| Rate limiting on auth/parsing/mail | ✅ slowapi + middleware | `rate_limit_notes.txt` |
| Timeouts on long-running endpoints | ✅ BackgroundTasks + asyncio.wait_for | `timeout_or_jobs_notes.txt` |
| Unified error format | ✅ `{error,detail,status,path,timestamp}` | `error_format_examples.txt` |
| App loads with all changes | ✅ 91 routes | `commands.log` |
| E2E chain (2 keywords, depth 2) | ✅ 41 results, 20 suppliers | `e2e_report.txt` |

### 6.4 Definition of Done

1. `tsc --noEmit` — exit 0
2. `next build` — exit 0, all pages
3. Grep-пруфы (file:line) для каждого утверждения
4. Артефакты в `docs/verification/` (txt/json/log only)
5. `PROJECT_PLAYBOOK.md` обновлён в том же commit
6. Backend: 0 unprotected endpoints, rate limits on heavy routes, unified error format

### 6.5 Окружение — **VERIFIED**

Evidence: `docs/verification/env.txt`

| Компонент | Версия |
|-----------|--------|
| Node.js | v24.11.1 (x64) |
| npm | 11.6.2 |
| Next.js | ^16.0.0 |
| React | ^18.2.0 |
| @tanstack/react-query | ^5.90.20 |
| @tanstack/react-virtual | ^3.13.18 |
| Python | 3.12 (backend) |
| OS | Windows |

---

## 7. Единый стандарт проекта

### 7.1 Frontend — Data Fetching — **VERIFIED**

| Правило | Статус | Evidence |
|---------|--------|----------|
| React Query only | **PARTIAL** | `hooks/queries/` ✅; `loadData()` `page.tsx:548` — прямые вызовы |
| 0 `setInterval` | **VERIFIED** | grep: 0 в `app/`, `components/`, `hooks/`, `lib/` |
| 0 `setTimeout` для polling | **VERIFIED** | grep: только backoff (`page.tsx:471,902`) |
| `refetchInterval` polling | **VERIFIED** | `keywords.ts:22`, `parsing.ts:35,45,59,75,90,99` |

### 7.2 Frontend — Виртуализация — **VERIFIED**

| Компонент | Evidence |
|-----------|----------|
| `/keywords` | `keywords/page.tsx:32,64` — `useVirtualizer` |
| `ParsingResultsTable` | `ParsingResultsTable.tsx:40,382` |
| `SuppliersTableVirtualized` | `SuppliersTableVirtualized.tsx:6,101` |

### 7.3 Frontend — Unified UI — **PARTIAL** (3/15 страниц)

`PageShell`: `/moderator`, `/suppliers`. `LoadingState`: + `/keywords`. `EmptyState`: `/suppliers`, `/keywords`.
Остальные ~12 страниц — inline loading/error.

### 7.4 Backend — Auth Coverage — ✅ HARDENED

| Правило | Статус | Evidence |
|---------|--------|----------|
| `get_current_user` на всех endpoints | **VERIFIED** ✅ | 14/14 routers protected (`grep_evidence_backend_after.txt`) |
| `require_moderator` на moderator endpoints | **VERIFIED** ✅ | All moderator endpoints use `authz.require_moderator` |
| Единый `require_moderator` | **VERIFIED** ✅ | 1 реализация в `app/utils/authz.py`, 0 dev-bypass |
| Rate limiting | **UNVERIFIED** | Не найден |

### 7.5 Правила для агентов

**❌ ЗАПРЕЩЕНО:**
1. "optimized" версия рядом с оригиналом
2. `setInterval`/`setTimeout` для polling
3. Новые markdown-отчёты (кроме txt/json/log в `docs/verification/`)
4. "готово/работает" без пруфов
5. Компоненты >500 строк без плана разбиения
6. Inline loading/error (использовать `LoadingState`/`EmptyState`)
7. Хардкод `limit: 1000` без обоснования
8. Backend endpoints без `Depends(get_current_user)`

**✅ ОБЯЗАТЕЛЬНО:**
1. `AuthGuard` на каждой новой странице
2. React Query hooks в `hooks/queries/{domain}.ts`
3. `useVirtualizer` для списков ≥200
4. `PageShell` + `LoadingState` + `EmptyState`
5. Build Gate перед merge
6. Обновить `PROJECT_PLAYBOOK.md` при структурных изменениях
7. Backend: `Depends(get_current_user)` + `require_moderator` (из `app/utils/authz.py`)

### 7.6 Как добавлять фичи

**Новая страница:** `app/{route}/page.tsx` → `AuthGuard` → `PageShell` → React Query hooks

**Список ≥200:** `useVirtualizer` + `estimateSize` + `measureElement` + `overscan: 10-20`

**Polling:** только `refetchInterval`, условная остановка через callback

**Новый API (frontend):** `lib/api.ts` → `hooks/queries/{domain}.ts` → `queryKey` factory

**Новый API (backend):** `Depends(get_current_user)` + `require_moderator` (из `app/utils/authz.py`)

---

## 8. Известные долги

| # | Долг | Severity | Evidence |
|---|------|----------|----------|
| ~~D1~~ | ~~26 backend endpoints без auth~~ | ~~P0 CRITICAL~~ | ✅ **RESOLVED** 2026-02-07 (`route_dump_after_auth.txt`) |
| ~~D2~~ | ~~`_require_moderator` — 5 копий, 2 dev-bypass~~ | ~~P1 HIGH~~ | ✅ **RESOLVED** 2026-02-07 (`grep_evidence_backend_after.txt`) |
| D3 | Нет `middleware.ts` (server-side route protection) | **P1 HIGH** | Файл отсутствует |
| D4 | `/parsing-runs/[runId]/page.tsx` — 2618 строк (монолит) | **P1 HIGH** | Файл существует |
| D5 | `getSuppliers({ limit: 1000 })` — жёсткий лимит | **P1 HIGH** | `page.tsx:338,483,558,1326` |
| D6 | `loadData()` — прямые API-вызовы вместо React Query | **P2 MEDIUM** | `page.tsx:548` |
| D7 | Unified UI на 3/15 страниц | **P2 MEDIUM** | grep `PageShell`: 4 использования |
| D8 | `parserStatus.results` не виртуализирован | **P2 MEDIUM** | `page.tsx:1984` |
| D9 | `process_log` JSONB без ротации | **P2 MEDIUM** | `page.tsx:2196-2341` |
| D10 | `supplier-card.tsx` — 47KB | **P2 MEDIUM** | Через dynamic import |
| D11 | Дубликат useEffect (localStorage) | **P3 LOW** | `page.tsx:254-261` = `page.tsx:307-314` |
| D12 | Мёртвый код: `supplier-card-optimized.tsx` (22KB) | **P3 LOW** | 0 импортов |
| D13 | Мёртвый код: `cabinet/settings/page_temp.tsx` | **P3 LOW** | Дубликат |

---

## 9. OPEN QUESTIONS (Business)

1. **AutoSave:** Должен ли AutoSave (после Domain Parser) требовать подтверждения модератора?
2. **Лимит 1000:** Ожидается ли >1000 поставщиков? Если да — нужен delta API.
3. **Ротация process_log:** Допустима ли архивация старых parsing runs?
4. **Роль "user":** Какие данные видит user в `/cabinet`?
5. ~~**Mail endpoints:** `/api/mail/yandex/*` без auth — by design (internal) или gap?~~ → ✅ RESOLVED: AUTH+MOD added
6. ~~**Checko endpoints:** `/moderator/checko/{inn}` без auth — допустимо?~~ → ✅ RESOLVED: AUTH+MOD added

---

## 10. TECH QUESTIONS (to Backend/Infra Agent)

### 10.1 ~~P0 — Критические~~ ✅ RESOLVED (2026-02-07)

```
✅ RESOLVED: Все 26 endpoints теперь защищены Depends(get_current_user) + require_moderator.
✅ RESOLVED: _require_moderator унифицирован в app/utils/authz.py (1 реализация, 0 dev-bypass).
Evidence: docs/verification/backend/route_dump_after_auth.txt
         docs/verification/backend/grep_evidence_backend_after.txt

REMAINING:
3. Rate limiting — НЕ НАЙДЕН. Рекомендация: slowapi или middleware. (P1)
4. Request timeout для /parsing/start и /domain-parser/extract-batch — НЕ РЕАЛИЗОВАН. (P2)
```

### 10.2 Верификационные

```
5. ✅ OpenAPI сгенерирован: py -c "from app.main import app; app.openapi()" →
   docs/verification/backend/openapi_verified.json (75 paths)
   docs/verification/backend/openapi_verified.sha256.txt
   SHA256: 1fa4ead8611a70351060ee58c785f518a1bfa621fdd864928a3750e0a42dd139

6. Формат ошибок API — единый ли?
   Frontend обрабатывает 3 варианта: error.detail || error.message || error.error
   (lib/api.ts:73)

7. Ротация process_log JSONB — есть ли пагинация/лимит?
   Frontend рендерит processLog целиком (page.tsx:2196-2341)
```

---

## Appendix A. Инвентаризация документов

### A.1 Актуальные

| Документ | Путь | Тип |
|----------|------|-----|
| **PROJECT_PLAYBOOK.md** | `docs/PROJECT_PLAYBOOK.md` | Canon (SSoT) |
| Frontend build log | `docs/verification/frontend_build_2026-02-07.log` | Evidence |
| Backend route dump (before) | `docs/verification/backend/route_dump_verified.txt` | Evidence (historical) |
| Backend grep evidence (before) | `docs/verification/backend/grep_evidence_backend.txt` | Evidence (historical) |
| Backend route dump (after) | `docs/verification/backend/route_dump_after_auth.txt` | Evidence (current) |
| Backend grep evidence (after) | `docs/verification/backend/grep_evidence_backend_after.txt` | Evidence (current) |
| OpenAPI schema | `docs/verification/backend/openapi_verified.json` | Evidence (75 paths) |
| OpenAPI SHA256 | `docs/verification/backend/openapi_verified.sha256.txt` | Evidence |
| Rate limit notes | `docs/verification/backend/rate_limit_notes.txt` | Evidence |
| Timeout/jobs notes | `docs/verification/backend/timeout_or_jobs_notes.txt` | Evidence |
| Error format examples | `docs/verification/backend/error_format_examples.txt` | Evidence |
| Smoke tests | `docs/verification/backend/curl_smoke_tests.txt` | Evidence |
| Commands log | `docs/verification/backend/commands.log` | Evidence |
| E2E report | `docs/verification/backend/e2e_report.txt` | Evidence |
| P2 Verification | `docs/verification/P2_VERIFICATION_REPORT.md` | Evidence |
| RBAC Check | `docs/verification/RBAC_CHECK.md` | Evidence |
| Optimization Report | `docs/perf/OPTIMIZATION_REPORT.md` | Evidence |
| env.txt | `docs/verification/env.txt` | Evidence |
| Build logs (8) | `docs/verification/build*.txt` | Historical |
| Grep logs (5) | `docs/verification/grep*.txt` | Historical |
| Command logs (3) | `docs/verification/*.log` | Historical |
| Lint logs (4) | `docs/verification/lint*.txt` | Historical |
| Type-check logs (5) | `docs/verification/type_check*.txt` | Historical |
| Launcher docs | `D:\b2b\docs\launcher.md` | Root-level |
| System Specification | `D:\b2b\docs\system-specification.md` | Root-level (не проверен) |

### A.2 DEPRECATED

| Документ | Причина |
|----------|---------|
| `docs/verification/VERIFICATION_REPORT.md` | Заменён P2 report |
| `docs/verification/VERIFICATION_REPORT_FINAL.md` | Заменён P2 report |
| `docs/verification/integration_map.md` | Перенесено в Playbook |

### A.3 Ранее упоминавшиеся, но не существующие

| Артефакт | Статус |
|----------|--------|
| `docs/backend/` | **НЕ СУЩЕСТВУЕТ** |
| `docs/backend/API_VERIFICATION_REPORT.md` | **НЕ СУЩЕСТВУЕТ** |
| ~~OpenAPI артефакт~~ | ✅ **СУЩЕСТВУЕТ** `docs/verification/backend/openapi_verified.json` |
| `README.md` в корне frontend | **НЕ СУЩЕСТВУЕТ** |
