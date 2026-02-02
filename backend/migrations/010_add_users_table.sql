-- Add users table for authentication with bcrypt
-- Migration: 010_add_users_table.sql
-- Date: 2026-01-18 18:25

CREATE TABLE IF NOT EXISTS users (
    id SERIAL PRIMARY KEY,
    username VARCHAR(50) UNIQUE NOT NULL,
    email VARCHAR(100) UNIQUE,
    hashed_password VARCHAR(255) NOT NULL,
    role VARCHAR(20) DEFAULT 'moderator' NOT NULL,
    is_active BOOLEAN DEFAULT TRUE NOT NULL,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    updated_at TIMESTAMP WITH TIME ZONE,
    last_login TIMESTAMP WITH TIME ZONE
);

-- Create indexes for performance
CREATE INDEX IF NOT EXISTS ix_users_id ON users (id);
CREATE INDEX IF NOT EXISTS ix_users_username ON users (username);
CREATE INDEX IF NOT EXISTS ix_users_email ON users (email);

-- Insert default users (passwords will be updated with bcrypt hashes)
INSERT INTO users (username, hashed_password, role) VALUES 
('admin', '$2b$12$placeholder_hash_admin123', 'admin'),
('moderator', '$2b$12$placeholder_hash_moderator123', 'moderator')
ON CONFLICT (username) DO NOTHING;

COMMENT ON TABLE users IS 'Users table for authentication with bcrypt password hashing';
COMMENT ON COLUMN users.hashed_password IS 'BCrypt hash of user password';
COMMENT ON COLUMN users.role IS 'User role: admin or moderator';
COMMENT ON COLUMN users.is_active IS 'Whether user account is active';
COMMENT ON COLUMN users.last_login IS 'Last login timestamp for user';