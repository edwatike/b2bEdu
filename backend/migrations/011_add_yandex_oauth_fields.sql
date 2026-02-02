-- Add Yandex OAuth fields to users table
-- Migration: 011_add_yandex_oauth_fields.sql
-- Date: 2026-01-24 00:45

-- Add Yandex OAuth token fields
ALTER TABLE users 
ADD COLUMN IF NOT EXISTS yandex_access_token TEXT,
ADD COLUMN IF NOT EXISTS yandex_refresh_token TEXT,
ADD COLUMN IF NOT EXISTS yandex_token_expires_at TIMESTAMP WITH TIME ZONE;

-- Add indexes for OAuth fields
CREATE INDEX IF NOT EXISTS ix_users_yandex_access_token ON users (yandex_access_token) WHERE yandex_access_token IS NOT NULL;

-- Add comments
COMMENT ON COLUMN users.yandex_access_token IS 'Yandex OAuth access token for API calls';
COMMENT ON COLUMN users.yandex_refresh_token IS 'Yandex OAuth refresh token for token renewal';
COMMENT ON COLUMN users.yandex_token_expires_at IS 'Expiration time for Yandex access token';

-- Update email constraint to be UNIQUE (if not already)
-- This ensures each email can only be used once
DO $$
BEGIN
    IF NOT EXISTS (SELECT 1 FROM pg_constraint WHERE conname = 'users_email_unique') THEN
        ALTER TABLE users ADD CONSTRAINT users_email_unique UNIQUE (email);
    END IF;
END
$$;

-- Add auth_method tracking
ALTER TABLE users 
ADD COLUMN IF NOT EXISTS auth_method VARCHAR(20) DEFAULT 'password';

COMMENT ON COLUMN users.auth_method IS 'Authentication method: password, yandex_oauth, etc';

-- Create index for auth_method
CREATE INDEX IF NOT EXISTS ix_users_auth_method ON users (auth_method);
