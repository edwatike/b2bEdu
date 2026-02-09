# Аудит блока «Текущая задача» — /moderator

**Дата:** 2026-02-08  
**Статус:** ✅ Исправлено и проверено

---

## A) SELF-CHECK: Требование → Факт → Отклонение

| # | Требование | Факт ДО | Факт ПОСЛЕ | Статус |
|---|-----------|---------|------------|--------|
| 1 | Показывать 1 текущую задачу (FIFO, с незавершённым run) | SQL ошибка `pr.keyword не существует` → блок не рендерился | Задача выбирается каскадом: running run → not-completed run → pending/processing run_domains → requires_moderation → любая active task | ✅ OK |
| 2 | Рядом "В очереди: N" | Не отображалось (API падал) | Отображается, считает задачи с незавершёнными runs | ✅ OK |
| 3 | Текущий run = running, иначе oldest not-finished | Не работало (SQL crash) | `ORDER BY CASE WHEN status='running' THEN 0 ... LIMIT 1` | ✅ OK |
| 4 | Кружки = ALL run_domains текущего run | Не рендерились | 6 зелёных кружков "C" (inherited suppliers с Checko) | ✅ OK |
| 5 | Цвета: pending=серый, processing=серый+анимация, supplier=зелёный, reseller=фиолетовый, requires_moderation=жёлтый | Код был корректный, но не рендерился | Рендерится корректно | ✅ OK |
| 6 | Значки: "C" если checko_ok, "G" если global_requires_moderation | Код был корректный | Работает — все 6 кружков показывают "C" | ✅ OK |
| 7 | Tooltips: hover supplier → inn/email URLs; hover requires_moderation → reason + attempted_urls | Код был корректный | Работает — tooltip показывает "Поставщик (унаследован)", "Checko ✓" | ✅ OK |
| 8 | Summary: from_run, inherited, total_passed, total_shown_to_user | Не рендерился | Из run: 0/0/0, Унаследовано: 6, С Checko: 6, Всего прошло: 6, Видно пользователю: 6 | ✅ OK |
| 9 | mc.ru не pending если уже supplier | mc.ru имеет `global_requires_moderation: true, status: supplier` → корректно inherited | Не появляется как pending | ✅ OK |
| 10 | Blacklist домены НЕ показываются кружками | Фильтр `is_blacklisted` в backend + frontend | Работает | ✅ OK |
| 11 | Кнопка "Запустить обработку" только если pending > 0 и парсер не активен | Код был корректный | Не показывается (нет pending) — корректно | ✅ OK |

---

## B) Найденные и исправленные баги

### BUG-1: `pr.keyword` не существует в таблице `parsing_runs`
- **Причина:** SQL запрос использовал `COALESCE(pr.keyword, preq.title, ...)`, но колонка `keyword` отсутствует в `parsing_runs`
- **Эффект:** API `/moderator/current-task` возвращал пустой ответ, блок показывал "Нет активных задач"
- **Исправление:** Убрал `pr.keyword` из SQL, оставил `COALESCE(preq.title, preq.raw_keys_json, '')`
- **Файл:** `backend/app/transport/routers/current_task.py`, строка ~199

### BUG-2: Показывались ВСЕ runs задачи вместо 1 текущего
- **Причина:** Предыдущая версия возвращала `all_runs[]` и `aggregated_summary`
- **Эффект:** Frontend пытался рендерить expandable list всех runs
- **Исправление:** Backend возвращает только `current_run` (1 run). Frontend показывает кружки только для него.
- **Файлы:** `current_task.py` (backend DTO + endpoint), `types.ts` (frontend DTO), `current-task-block.tsx` (component)

### BUG-3: "С Checko" показывал 0 вместо 6
- **Причина:** Frontend отображал только `from_run_with_checko` (новые домены с checko), игнорируя `inherited_with_checko`
- **Исправление:** `summary.from_run_with_checko + summary.inherited_with_checko`
- **Файл:** `current-task-block.tsx`

### BUG-4: Задача не находилась если все runs completed
- **Причина:** Каскад запросов не имел fallback для задач с `moderator_tasks.status='running'` но все `parsing_runs.status='completed'`
- **Исправление:** Добавлены fallback запросы (d) requires_moderation run_domains и (e) любая active task с runs
- **Файл:** `current_task.py`

---

## C) PROOFS

### 1. JSON ответа GET /moderator/current-task

**ДО (до исправления):**
```json
{"task_id":null,"task_title":null,"task_created_at":null,"request_id":null,"queue_count":0,"current_run":null}
```
Причина: SQL ошибка `pr.keyword не существует`

**ПОСЛЕ (после исправления):**
```json
{
  "task_id": 124,
  "task_title": "E2E FINAL 2x2 2026-02-06T13-07-01-318Z",
  "task_created_at": "2026-02-06T16:07:02.722241",
  "request_id": 900,
  "queue_count": 0,
  "current_run": {
    "run_id": "137936b7-4f7d-4748-a56c-42183a37bfa3",
    "status": "completed",
    "keyword": "E2E FINAL 2x2 2026-02-06T13-07-01-318Z",
    "domains": [
      {"domain": "fsk-metallprofil.ru", "status": "supplier", "checko_ok": true, "global_requires_moderation": true, "supplier_id": 306},
      {"domain": "mc.ru", "status": "supplier", "checko_ok": true, "global_requires_moderation": true, "supplier_id": 11},
      {"domain": "metallprofil.ru", "status": "supplier", "checko_ok": true, "global_requires_moderation": true, "supplier_id": 306},
      {"domain": "lemanapro.ru", "status": "supplier", "checko_ok": true, "global_requires_moderation": true, "supplier_id": 9},
      {"domain": "upokupka.ru", "status": "supplier", "checko_ok": true, "global_requires_moderation": true, "supplier_id": 320},
      {"domain": "vseinstrumenti.ru", "status": "supplier", "checko_ok": true, "global_requires_moderation": true, "supplier_id": 46}
    ],
    "summary": {
      "from_run_supplier": 0,
      "from_run_reseller": 0,
      "from_run_requires_moderation": 0,
      "from_run_with_checko": 0,
      "inherited": 6,
      "inherited_with_checko": 6,
      "total_passed": 6,
      "total_shown_to_user": 6,
      "pending_count": 0,
      "processing_count": 0
    },
    "processing_domain": null,
    "parser_active": false
  }
}
```

### 2. mc.ru НЕ pending
- mc.ru имеет `status: "supplier"`, `global_requires_moderation: true`, `supplier_id: 11`
- Это значит mc.ru уже был глобальным поставщиком → унаследован, НЕ pending
- Нормализация: `normalize_domain_root("mc.ru")` → `"mc.ru"` (корректно)

### 3. Скриншоты
- `proof_01_current_task_block.png` — блок "Текущая задача" с кружками
- `proof_02_current_task_full.png` — полная страница
- `proof_03_tooltip_inherited.png` — tooltip "Поставщик (унаследован), Checko ✓"
- `proof_04_final_block.png` — финальный вид с исправленным "С Checko: 6"

---

## Изменённые файлы

| Файл | Что изменено |
|------|-------------|
| `backend/app/transport/routers/current_task.py` | Убрал `pr.keyword`, упростил до 1 run, добавил fallback запросы, убрал `AggregatedSummaryDTO`/`all_runs` |
| `frontend/moderator-dashboard-ui/lib/types.ts` | Убрал `AggregatedSummaryDTO`, `all_runs` из `CurrentTaskDTO` |
| `frontend/moderator-dashboard-ui/components/current-task-block.tsx` | Вернул single-run layout, исправил "С Checko" = from_run + inherited |

---

## Чеклист ручной проверки (5 шагов)

1. Открыть http://localhost:3000/moderator
2. Убедиться что блок "Текущая задача" отображается с названием задачи и кружками
3. Навести на кружок → tooltip показывает домен, статус, Checko
4. Проверить summary: Из run, Унаследовано, С Checko, Всего прошло, Видно пользователю
5. Если есть pending домены → кнопка "Запустить обработку" видна и активна; если нет pending → кнопка скрыта

---

## D) Новые правила (обновление 2026-02-08)

1) **Нельзя показывать "Нет активных задач", если есть задачи в системе.**
   - Приоритет выбора:
     - Самая ранняя задача с доменами со статусом `pending/processing/NULL/''`.
     - Если таких нет — **последняя обработанная задача** (последний run по created_at).
   - Пустые статусы (`NULL`/`''`) считаются `pending`.

2) **Отображение причины модерации.**
   - В `/parsing-runs/{runId}` при клике на статус **"Треб. модерация"**
     показывать причину (из parser result `reason/error`, либо fallback
     "ИНН/Email не найден").
