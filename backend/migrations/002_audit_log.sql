-- Migration: Add audit_log table for tracking data changes
-- Created: 2025-12-26

-- Table: audit_log
CREATE TABLE IF NOT EXISTS audit_log (
    id SERIAL PRIMARY KEY,
    table_name VARCHAR(255) NOT NULL,
    operation VARCHAR(10) NOT NULL, -- INSERT, UPDATE, DELETE
    record_id VARCHAR(255) NOT NULL,
    old_data JSONB,
    new_data JSONB,
    changed_by VARCHAR(255),
    changed_at TIMESTAMP WITH TIME ZONE DEFAULT NOW()
);

-- Indexes for audit_log
CREATE INDEX idx_audit_log_table_name ON audit_log(table_name);
CREATE INDEX idx_audit_log_operation ON audit_log(operation);
CREATE INDEX idx_audit_log_record_id ON audit_log(record_id);
CREATE INDEX idx_audit_log_changed_at ON audit_log(changed_at);

-- Комментарии
COMMENT ON TABLE audit_log IS 'Audit log for tracking all data changes in the system';
COMMENT ON COLUMN audit_log.table_name IS 'Name of the table that was modified';
COMMENT ON COLUMN audit_log.operation IS 'Type of operation: INSERT, UPDATE, DELETE';
COMMENT ON COLUMN audit_log.record_id IS 'ID of the record that was modified';
COMMENT ON COLUMN audit_log.old_data IS 'Previous data (for UPDATE and DELETE)';
COMMENT ON COLUMN audit_log.new_data IS 'New data (for INSERT and UPDATE)';
COMMENT ON COLUMN audit_log.changed_by IS 'User or system that made the change';
COMMENT ON COLUMN audit_log.changed_at IS 'Timestamp when the change was made';



















