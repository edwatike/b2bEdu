# B2B Platform — Запуск

## Строгое правило запуска

Проект запускается **строго через**:

- `D:\b2b\B2BLauncher.exe`

Не запускай сервисы вручную отдельными командами (backend/parser/frontend/CDP), если нет отдельной инструкции на отладку.

## Что делает B2BLauncher.exe

- Освобождает порты:
  - Backend: `8000`
  - Parser: `9000`
  - Frontend: `3000`
  - CDP (Comet): `7000`
- Запускает сервисы и печатает логи в одном окне.
- Показывает таблицу статусов (STARTING/READY/FAILED) и последнюю ошибку (`LastError`).
- Запускает Comet (CDP) **только после** того, как поднялись Backend + Parser + Frontend.

## Проверка после запуска

Ожидаемые URL:

- Frontend: `http://127.0.0.1:3000/login`
- Backend health: `http://127.0.0.1:8000/health`
- Parser health: `http://127.0.0.1:9000/health`
- CDP: `http://127.0.0.1:7000/json/version`

## Пересборка EXE (для разработчика)

Сборка выполняется из корня репозитория `D:\b2b`.

Используется venv для PyInstaller:
- `D:\b2b\TEMP\pyi_env`

Команда сборки (класть EXE в корень репозитория):

- `D:\b2b\TEMP\pyi_env\Scripts\python.exe -m PyInstaller --onefile --console --name B2BLauncher --distpath . tools\b2b_launcher\b2b_launcher.py`

Если Windows блокирует `B2BLauncher.exe` при пересборке (WinError 5), собирай во временный файл и заменяй:

- `D:\b2b\TEMP\pyi_env\Scripts\python.exe -m PyInstaller --onefile --console --name B2BLauncher_new --distpath TEMP\dist_alt --clean tools\b2b_launcher\b2b_launcher.py`
- остановить лаунчер
- заменить файл:
  - `del /f /q D:\b2b\B2BLauncher.exe`
  - `move /Y D:\b2b\TEMP\dist_alt\B2BLauncher_new.exe D:\b2b\B2BLauncher.exe`
