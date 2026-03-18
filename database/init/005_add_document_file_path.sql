-- Add file_path to documents for uploaded file storage location
ALTER TABLE documents
ADD COLUMN IF NOT EXISTS file_path VARCHAR(1000);
