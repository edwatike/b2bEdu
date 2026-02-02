-- Add cabinet access flag to users and seed moderator account
-- Migration: 012_user_cabinet_access_and_seed.sql
-- Date: 2026-01-26

ALTER TABLE users
ADD COLUMN IF NOT EXISTS cabinet_access_enabled BOOLEAN DEFAULT FALSE NOT NULL;

CREATE INDEX IF NOT EXISTS ix_users_cabinet_access_enabled ON users (cabinet_access_enabled);

-- Seed moderator user for moderator cabinet
-- username: edwatik
-- password: 12059001
INSERT INTO users (username, email, hashed_password, role, is_active, cabinet_access_enabled)
VALUES (
  'edwatik',
  'edwatik@yandex.ru',
  '$2b$12$Cd7irvE8vn9Zl8dAVFyLN.QxXo13b7WjAp4rQpjJ9fIWk0GsNl4Xy',
  'moderator',
  TRUE,
  TRUE
)
ON CONFLICT (username) DO UPDATE SET
  role = EXCLUDED.role,
  is_active = EXCLUDED.is_active,
  cabinet_access_enabled = EXCLUDED.cabinet_access_enabled;
