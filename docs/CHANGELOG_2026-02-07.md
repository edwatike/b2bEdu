# Журнал изменений — 07.02.2026

> Все утверждения ниже основаны на коде. Где указано «работает сейчас» — это описание текущей реализации, а не предположение.

---

## 1. Парсер доменов — стабильность и фильтрация

### Как ДОЛЖНО работать
- Парсер **не должен** повторно обрабатывать домены, которые уже есть в базе поставщиков (`moderator_suppliers` / `supplier_domains`) или помечены «Требуется модерация» (`domain_moderation`).
- Субдомены (например `spb.lemanapro.ru`) должны считаться обработанными, если их корневой домен (`lemanapro.ru`) уже в базе.
- Парсер должен работать непрерывно без зависаний и бесконечных циклов.
- При перезапуске backend раны со статусом `running` должны сбрасываться в `queued`.
- Завершённые/упавшие раны с необработанными доменами должны повторно ставиться в очередь **только при старте** (не в каждом тике).

### Как работает СЕЙЧАС (по коду)

**Файл:** `backend/app/transport/routers/domain_parser.py`, строки 164–234

- Функция `_normalize_domain_full(domain)` — нормализует домен: lowercase, убирает `www.`, протокол, путь. **Не** обрезает субдомены.
- Функция `_normalize_domain(domain)` — алиас `normalize_domain_root()`, обрезает до корневого домена (`spb.lemanapro.ru` → `lemanapro.ru`).
- `_domain_exists_in_suppliers(domain)` — проверяет **оба** варианта: full domain И root domain. SQL-запрос к `moderator_suppliers LEFT JOIN supplier_domains`. Если хотя бы один вариант найден — домен считается обработанным.
- `_domain_requires_moderation(domain)` — аналогично проверяет оба варианта в таблице `domain_moderation` со статусом `requires_moderation`.

**Файл:** `backend/app/main.py`, строки 207–296 (startup recovery)

- **Recovery A** (строки 216–244): при старте сбрасывает `running` → `queued` для всех ранов с `process_log.domain_parser_auto.status = 'running'`.
- **Recovery B** (строки 246–293): при старте ищет `completed`/`failed` раны, у которых есть домены не в `moderator_suppliers` и не в `domain_moderation`. Ставит их обратно в `queued`. Выполняется **только при старте**, не в основном цикле — это предотвращает бесконечные циклы перепостановки.

**Файл:** `backend/app/main.py`, строки 297+ (основной цикл)

- Цикл `while True` с `asyncio.sleep(5)` между итерациями.
- Берёт самый старый ран со статусом `queued` (FIFO).
- Обрабатывает один ран за раз.
- Для каждого домена вызывает `_domain_exists_in_suppliers` и `_domain_requires_moderation` — пропускает уже обработанные.

---

## 2. Загрузка списка ранов (parsing-runs) — оптимизация

### Как ДОЛЖНО работать
- Список ранов `/parsing-runs` должен загружаться быстро (< 2 сек).
- Количество доменов для каждого рана должно подсчитываться эффективно.

### Как работает СЕЙЧАС (по коду)

**Файл:** `backend/app/transport/routers/parsing_runs.py`, строки 78–95

- **Batch-запрос** вместо N+1: один SQL `SELECT parsing_run_id, COUNT(*) FROM domains_queue WHERE parsing_run_id = ANY(:ids) GROUP BY parsing_run_id`.
- Ранее для каждого рана выполнялся отдельный `domain_queue_repo.list(limit=1, parsing_run_id=run.run_id)` — это N+1 проблема (100 ранов = 100 запросов).
- Сейчас все подсчёты выполняются одним запросом, результат кэшируется в `domain_counts: dict[str, int]`.
- В цикле конвертации DTO используется `domain_counts.get(run.run_id)` — O(1) lookup.

---

## 3. Страница поставщиков `/moderator/suppliers`

### Как ДОЛЖНО работать
- Таблица поставщиков отображает по **50 записей** на страницу с пагинацией.
- **Нет скроллбара** — таблица занимает полную высоту страницы.
- **Нет меню «3 точки»** (DropdownMenu с действиями «Редактировать», «Просмотр», «В блеклист»).
- Клик по строке поставщика → переход в карточку предприятия `/suppliers/{id}`.
- Все действия (редактирование, просмотр, блеклист) доступны через карточку предприятия.
- Поиск работает с debounce 400ms, **не перезагружает страницу** при каждой букве.

### Как работает СЕЙЧАС (по коду)

**Файл:** `frontend/moderator-dashboard-ui/components/supplier/SuppliersTableVirtualized.tsx`

- Компонент **полностью переписан** (120 строк вместо 389).
- Убрана виртуализация (`@tanstack/react-virtual` больше не используется).
- Убран `DropdownMenu` с `MoreVertical` (3 точки).
- Каждая строка таблицы — кликабельная: `onClick={() => router.push(\`/suppliers/${s.id}\`)}` с `cursor-pointer` и `hover:bg-muted/50`.
- Строка показывает: имя, ИНН, тип (badge), email, домен, иконку `ChevronRight`.
- Сортировка по полям: name, inn, type, email, domain — через `useMemo` и `handleSort`.

**Файл:** `frontend/moderator-dashboard-ui/app/suppliers/suppliers-client.tsx`

- `PAGE_SIZE = 50` (было 100).
- Debounce поиска: `useEffect` с `setTimeout(400ms)` → `setDebouncedSearch(searchQuery)` + `setPage(1)`.
- Загрузка данных: `useEffect([recentDays, page, debouncedSearch])` → `loadSuppliers()`.
- Пагинация: кнопки «Назад»/«Вперёд», отображение «Страница X из Y».
- `router.replace` обновляет URL только при клике на пагинацию, не при поиске.

**Файл:** `frontend/moderator-dashboard-ui/app/suppliers/page.tsx`

- Обёрнут в `<Suspense>` для корректной работы `useSearchParams()` в Next.js 16 (без Suspense — full-page re-render при каждом изменении).

---

## 4. Создание поставщика вручную — ошибка 422

### Как ДОЛЖНО работать
- При создании поставщика через `/suppliers/new` с валидным email (например `info@example.com`) не должно быть ошибки 422.
- Email-валидация должна корректно проверять формат.

### Как работает СЕЙЧАС (по коду)

**Файл:** `backend/app/transport/routers/moderator_suppliers.py`, строка ~193

- Regex для email: `r"^[^\s@]+@[^\s@]+\.[^\s@]+$"`
- **Исправлено:** ранее было `r"^[^\\s@]+@[^\\s@]+\\.[^\\s@]+$"` — двойной бэкслеш в raw string (`r"..."`) означает буквальный `\s`, а не класс whitespace. Это приводило к тому, что валидные email отклонялись.
- Функция `_validate_required_inn_email(inn, email)` вызывается в endpoint `create_supplier` и возвращает HTTP 422 при невалидном формате.

---

## 5. Дашборд модератора — блок «Доменов в очереди»

### Как ДОЛЖНО работать
- Блок «Доменов в очереди» на `/moderator` должен быть **кликабельным**.
- Клик → переход к `/domains?status=pending` (список доменов без статуса, ожидающих обработки).
- Счётчик показывает количество записей в таблице `pending`.

### Как работает СЕЙЧАС (по коду)

**Файл:** `frontend/moderator-dashboard-ui/app/moderator/page-optimized.tsx`, строки 164–178

- Карточка `<Card>` с `className="cursor-pointer hover:shadow-md transition-shadow"`.
- `onClick={() => router.push("/domains?status=pending")}`.
- Значение: `stats?.domains_in_queue || 0`.
- Подпись: «Ожидают извлечения данных».

**Файл:** `backend/app/transport/routers/moderator_users.py`, строка ~321

- SQL: `(SELECT COUNT(*) FROM pending) AS domains_in_queue` — считает все записи в таблице `pending`.

---

## 6. Парсер — логирование извлечения данных

### Как ДОЛЖНО работать
- Для каждого домена парсер должен сохранять `extraction_log` — список страниц, которые были посещены, и что на каждой найдено/не найдено (ИНН, email).

### Как работает СЕЙЧАС (по коду)

**Файл:** `domain_info_parser/parser.py`, метод `parse_domain`

- Создаёт `extraction_log: list[dict]` в начале парсинга.
- Для каждой посещённой страницы добавляет запись: `{"url": url, "inn_found": inn_value_or_null, "emails_found": [list], "error": error_or_null}`.
- Возвращает `extraction_log` в результатах парсинга.

**Файл:** `backend/app/transport/routers/domain_parser.py`, строки 608–632

- `extraction_log` передаётся из результатов парсера в сохраняемые данные домена.

---

## 7. B2BLauncher — запуск 4/4 сервисов

### Как ДОЛЖНО работать
- `B2BLauncher.exe` запускает 4 сервиса: PARSER (9000), BACKEND (8000), FRONTEND (3000), CDP (7000).
- Все 4 должны перейти в статус READY.

### Как работает СЕЙЧАС (по коду)

**Файл:** `tools/b2b_launcher/b2b_launcher.py`

- Использует `_venv_python(service_dir)` для определения Python — ищет `.venv_clean/Scripts/python.exe`, затем `.venv`, затем `venv`, затем `sys.executable`.
- **Проблема (исправлена):** пакет `slowapi` отсутствовал в `.venv_clean`. Backend падал с `ModuleNotFoundError: No module named 'slowapi'`. CDP не запускался, т.к. ждал core services READY.
- **Решение:** `slowapi` установлен в `.venv_clean` через `d:\b2b\.venv_clean\Scripts\python.exe -m pip install slowapi`.
- Frontend запускается через `npm run start -- -p 3000` (production build).
- CDP запускает Chrome с `--remote-debugging-port=7000` и реальным профилем пользователя.

---

## Файлы, затронутые изменениями

| Файл | Что изменено |
|---|---|
| `backend/app/transport/routers/domain_parser.py` | Добавлена `_normalize_domain_full`, обновлены `_domain_exists_in_suppliers` и `_domain_requires_moderation` для проверки full+root domain |
| `backend/app/main.py` | Recovery B перенесён в startup-only, убран из основного цикла |
| `backend/app/transport/routers/parsing_runs.py` | N+1 → batch query для domain counts |
| `backend/app/transport/routers/moderator_suppliers.py` | Исправлен regex email-валидации |
| `frontend/.../SuppliersTableVirtualized.tsx` | Полная переписка: убрана виртуализация, скролл, 3 точки; добавлен клик→карточка |
| `frontend/.../suppliers-client.tsx` | PAGE_SIZE=50 |
| `frontend/.../app/suppliers/page.tsx` | Добавлен `<Suspense>` для useSearchParams |
| `frontend/.../app/moderator/page-optimized.tsx` | Блок «Доменов в очереди» кликабельный → /domains?status=pending |
| `domain_info_parser/parser.py` | Добавлен extraction_log в результаты parse_domain |
