-- Store dense vectors as JSONB (float array); works on stock PostgreSQL (no pgvector).
ALTER TABLE chunks
    ADD COLUMN IF NOT EXISTS chunk_index INTEGER NOT NULL DEFAULT 0,
    ADD COLUMN IF NOT EXISTS embedding_model VARCHAR(200),
    ADD COLUMN IF NOT EXISTS embedding JSONB;

CREATE INDEX IF NOT EXISTS idx_chunks_doc_chunk_index ON chunks (document_id, chunk_index);
CREATE INDEX IF NOT EXISTS idx_chunks_has_embedding ON chunks (document_id) WHERE embedding IS NOT NULL;
