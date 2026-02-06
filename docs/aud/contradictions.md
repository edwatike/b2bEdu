# Конфигурационный стандарт (разночтения устранены)

Дата обновления: 05.02.2026

## Единый стандарт
ENV — основной флаг окружения для backend.
PARSER_SERVICE_URL — единый URL парсера для backend.
PARSER_PORT — 9000 во всех местах.
NEXT_PUBLIC_PARSER_URL — http://localhost:9000 для фронта.
CORS_ORIGINS — строка через запятую.
DATABASE_URL — формат postgresql+asyncpg://...

## Где это задано
backend/app/config.py — читает ENV, PARSER_SERVICE_URL, CORS_ORIGINS, DATABASE_URL.
parser_service/run_api.py — использует PARSER_HOST и PARSER_PORT.
docker-compose.yml — все сервисы используют порт парсера 9000 и ENV.
.env.example — эталонные значения и формат переменных.
tools/b2b_launcher/b2b_launcher.py — локальный порт парсера 9000.

## Примечание
NEXT_PUBLIC_ENVIRONMENT остается только для фронтенда и не влияет на backend.
