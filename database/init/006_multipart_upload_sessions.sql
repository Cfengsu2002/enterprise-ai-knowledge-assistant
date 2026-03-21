-- Track S3 multipart uploads for resume / server-side validation
CREATE TABLE IF NOT EXISTS multipart_upload_sessions (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    s3_upload_id VARCHAR(1024) NOT NULL,
    s3_key VARCHAR(2048) NOT NULL,
    bucket VARCHAR(255) NOT NULL,
    enterprise_id INTEGER NOT NULL REFERENCES enterprises(id) ON DELETE CASCADE,
    user_id INTEGER REFERENCES users(id) ON DELETE SET NULL,
    original_filename VARCHAR(500) NOT NULL,
    title VARCHAR(500),
    file_size BIGINT NOT NULL,
    content_type VARCHAR(255),
    part_size_bytes BIGINT NOT NULL,
    status VARCHAR(32) NOT NULL DEFAULT 'in_progress',
    created_at TIMESTAMPTZ DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMPTZ DEFAULT CURRENT_TIMESTAMP
);

CREATE INDEX IF NOT EXISTS idx_multipart_sessions_enterprise
    ON multipart_upload_sessions (enterprise_id);
CREATE INDEX IF NOT EXISTS idx_multipart_sessions_status
    ON multipart_upload_sessions (status);
