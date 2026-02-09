-- Add indexes to speed up cabinet requests and runs lookups

CREATE INDEX IF NOT EXISTS idx_parsing_requests_created_by ON parsing_requests(created_by);
CREATE INDEX IF NOT EXISTS idx_parsing_runs_request_id ON parsing_runs(request_id);
