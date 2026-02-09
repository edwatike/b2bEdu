ALTER TABLE users
ADD COLUMN IF NOT EXISTS openai_api_key_encrypted TEXT;

CREATE INDEX IF NOT EXISTS ix_users_openai_api_key_encrypted ON users (openai_api_key_encrypted);
