-- Add submission status fields to parsing_requests
-- Migration: 013_parsing_requests_submission.sql
-- Date: 2026-01-26

ALTER TABLE parsing_requests
ADD COLUMN IF NOT EXISTS submitted_to_moderator BOOLEAN DEFAULT FALSE NOT NULL,
ADD COLUMN IF NOT EXISTS submitted_at TIMESTAMP WITH TIME ZONE;

CREATE INDEX IF NOT EXISTS ix_parsing_requests_created_by ON parsing_requests (created_by);
CREATE INDEX IF NOT EXISTS ix_parsing_requests_submitted_to_moderator ON parsing_requests (submitted_to_moderator);
