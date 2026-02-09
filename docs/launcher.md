# Лаунчер B2B (B2BLauncher.exe)

Ниже — понятная документация, как устроен лаунчер, что он запускает и какие настройки на него влияют.

## 1) Назначение
- Лаунчер — **единственный правильный способ** запускать проект.
- Он поднимает **4 сервиса** и следит за их состоянием.

## 2) Какие сервисы запускает (4/4)
- **Frontend**: `http://localhost:3000`
- **Backend**: `http://127.0.0.1:8000/health`
- **Parser**: `http://127.0.0.1:9000/health`
- **Chrome CDP**: `http://127.0.0.1:7000/json/version`

## 3) Стартовый сценарий (упрощенно)
1. Освобождает порты `3000/8000/9000` (и `7000`, если включено принудительно).
2. Запускает Parser, Backend, Frontend.
3. Ждет, когда `Parser/Backend/Frontend` станут `READY`.
4. **Только потом** запускает Chrome CDP.
5. Печатает таблицу со статусами `STARTING/READY/FAILED`.

## 4) Как он выбирает Python
Для Backend/Parser он пытается использовать:
1. `D:\b2b\.venv_clean\Scripts\python.exe`
2. `D:\b2b\.venv\Scripts\python.exe`
3. `backend\venv\Scripts\python.exe` / `parser_service\venv\Scripts\python.exe`
4. Системный `python`

## 5) Как запускается Frontend
Лаунчер запускает Frontend так:
- Если нет `.next\BUILD_ID` — делает `npm run build`
- Потом запускает `npm run start -- -p 3000`

Переменные, которые подаются фронту:
- `NODE_ENV=production`
- `PORT=3000`
- `NEXT_PUBLIC_API_URL=http://127.0.0.1:8000`
- `NEXT_PUBLIC_PARSER_URL=http://127.0.0.1:9000`
- `NODE_OPTIONS=--max-old-space-size=2048`
- `NEXT_TELEMETRY_DISABLED=1`

## 6) CDP: строго Chrome + один профиль (без прыжков)
Сейчас сделано **строгое правило**:
- **Только Chrome**
- **Только реальный профиль**
- **Без fallback в Comet**
- **Без временного профиля**

Если CDP не поднимается, в таблице будет:
`cdp /json/version timeout (profile <имя>)`

### Как выбирается профиль Chrome
1. Если задан `B2B_CDP_PROFILE_DIR` — используется он.
2. Иначе берётся последний активный профиль из Chrome `Local State`.
3. Если не найден — `Default`.

### Где ищется Chrome User Data
1. `B2B_CDP_USER_DATA_DIR`
2. `%LOCALAPPDATA%\\Google\\Chrome\\User Data`

Если папки профиля нет — CDP не стартует.

## 7) Логи лаунчера
Лаунчер пишет лог сюда:
- `D:\b2b\TEMP\launcher-ui-YYYYMMDD-HHMMSS.log`

Chrome CDP пишет лог сюда:
- `D:\b2b\TEMP\chrome-cdp.log`

## 8) Автовосстановление
Если сервис упал или health не отвечает:
- Лаунчер **перезапускает** конкретный сервис
- Есть защита от бесконечных рестартов (rate limit)

## 9) Настройки (ENV)
Ниже полный список переменных, которые реально учитывает лаунчер:

- `B2B_REPO_ROOT` — если репозиторий не в `D:\b2b`
- `B2B_CDP_FORCE_RESTART=1` — принудительно освобождает порт `7000`
- `B2B_CDP_ALLOW_RESTART=1` — разрешить повторный старт CDP после первого фейла
- `B2B_CDP_STARTUP_TIMEOUT=60` — таймаут ожидания CDP (сек)
- `B2B_CDP_PROFILE_DIR=Profile 1` — **жестко закрепить профиль**
- `B2B_CDP_USER_DATA_DIR=...` — путь к Chrome профилям
- `B2B_CDP_KILL_CHROME=1` — убивает все Chrome-процессы перед CDP
- `B2B_CDP_OPEN_URL=1` — открыть фронт при запуске Chrome
- `B2B_CDP_HEADLESS=1` — запуск без окна

## 10) Проверка, что 4/4 поднялись
Считаем проект «готов», если:
- `http://127.0.0.1:8000/health` → 200
- `http://127.0.0.1:9000/health` → 200
- `http://localhost:3000/login` → открывается
- `http://127.0.0.1:7000/json/version` → 200

## 11) Пересборка B2BLauncher.exe
Сборка через PyInstaller:
```
python -m PyInstaller --onefile --console --name B2BLauncher_new --distpath D:\b2b\TEMP\dist_alt --clean D:\b2b\tools\b2b_launcher\b2b_launcher.py
```
Затем заменить:
```
del /f /q D:\b2b\B2BLauncher.exe
move /Y D:\b2b\TEMP\dist_alt\B2BLauncher_new.exe D:\b2b\B2BLauncher.exe
```

## 12) Частые причины, почему CDP не поднимается
1. Профиль Chrome слишком тяжёлый или поврежден.
2. Chrome не закрывается корректно и профиль в «грязном» состоянии.
3. Профиль задан неверно (нет папки).
4. Два запущенных лаунчера одновременно.

Если CDP не стартует — смотрим:
- `D:\b2b\TEMP\launcher-ui-*.log`
- `D:\b2b\TEMP\chrome-cdp.log`
