-- Add output_paths to store multiple CSV outputs (e.g., extracted from ZIP)
--
-- This project uses a lightweight SQL migration approach.
-- Apply manually when deploying to an environment with persistent DB.

ALTER TABLE pdf_conversion_jobs
ADD COLUMN IF NOT EXISTS output_paths JSONB NULL;

ALTER TABLE pdf_conversion_jobs
ADD COLUMN IF NOT EXISTS ingested_upload_jobs JSONB NULL;
