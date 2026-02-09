-- Добавление OAuth полей в таблицу users
-- Миграция для поддержки Яндекс OAuth авторизации

-- Добавляем колонки для OAuth если их нет
ALTER TABLE users 
ADD COLUMN IF NOT EXISTS auth_method VARCHAR(50) DEFAULT 'password',
ADD COLUMN IF NOT EXISTS yandex_access_token TEXT,
ADD COLUMN IF NOT EXISTS yandex_refresh_token TEXT,
ADD COLUMN IF NOT EXISTS yandex_token_expires_at TIMESTAMP;

-- Создаем индекс для auth_method для быстрого поиска
CREATE INDEX IF NOT EXISTS idx_users_auth_method ON users(auth_method);

-- Создаем индекс для email если его нет (для OAuth поиска)
CREATE INDEX IF NOT EXISTS idx_users_email ON users(email);

-- Добавляем комментарий
COMMENT ON COLUMN users.auth_method IS 'Метод авторизации: password, yandex_oauth';
COMMENT ON COLUMN users.yandex_access_token IS 'OAuth access token от Яндекса';
COMMENT ON COLUMN users.yandex_refresh_token IS 'OAuth refresh token от Яндекса';
COMMENT ON COLUMN users.yandex_token_expires_at IS 'Время истечения access token';
