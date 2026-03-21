-- Link + metadata: S3 holds bytes; DB holds URI and searchable fields.
ALTER TABLE documents
    ADD COLUMN IF NOT EXISTS storage_type VARCHAR(16) NOT NULL DEFAULT 'local',
    ADD COLUMN IF NOT EXISTS original_filename VARCHAR(500),
    ADD COLUMN IF NOT EXISTS content_type VARCHAR(255),
    ADD COLUMN IF NOT EXISTS byte_size BIGINT,
    ADD COLUMN IF NOT EXISTS s3_bucket VARCHAR(255),
    ADD COLUMN IF NOT EXISTS s3_key VARCHAR(2048),
    ADD COLUMN IF NOT EXISTS file_metadata JSONB NOT NULL DEFAULT '{}'::jsonb;

COMMENT ON COLUMN documents.file_path IS 'Canonical storage URI: local relative path under UPLOAD_DIR, or s3://bucket/key';
COMMENT ON COLUMN documents.storage_type IS 'local | s3';
COMMENT ON COLUMN documents.file_metadata IS 'Extra JSON (e.g. region, endpoint, custom tags)';

CREATE INDEX IF NOT EXISTS idx_documents_storage_type ON documents (storage_type);
