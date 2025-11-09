-- Form Analysis Database Initialization Script
-- This script sets up the basic database structure and initial data

-- Create extensions if they don't exist
CREATE EXTENSION IF NOT EXISTS "uuid-ossp";

-- Create the forms table for storing uploaded form data
CREATE TABLE IF NOT EXISTS forms (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    filename VARCHAR(255) NOT NULL,
    original_filename VARCHAR(255) NOT NULL,
    file_size BIGINT NOT NULL,
    file_type VARCHAR(100),
    upload_time TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,
    processing_status VARCHAR(50) DEFAULT 'pending',
    analysis_result JSONB,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP
);

-- Create indexes for better performance
CREATE INDEX IF NOT EXISTS idx_forms_upload_time ON forms(upload_time);
CREATE INDEX IF NOT EXISTS idx_forms_processing_status ON forms(processing_status);
CREATE INDEX IF NOT EXISTS idx_forms_filename ON forms(filename);

-- Create the analysis_results table for detailed analysis data
CREATE TABLE IF NOT EXISTS analysis_results (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    form_id UUID REFERENCES forms(id) ON DELETE CASCADE,
    field_name VARCHAR(255),
    field_type VARCHAR(100),
    field_value TEXT,
    confidence_score DECIMAL(5,4),
    bounding_box JSONB,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP
);

-- Create indexes for analysis_results
CREATE INDEX IF NOT EXISTS idx_analysis_results_form_id ON analysis_results(form_id);
CREATE INDEX IF NOT EXISTS idx_analysis_results_field_name ON analysis_results(field_name);

-- Insert some initial configuration data if needed
INSERT INTO forms (id, filename, original_filename, file_size, file_type, processing_status, analysis_result)
VALUES (
    uuid_generate_v4(),
    'system_check.txt',
    'Database Initialization Check',
    0,
    'text/plain',
    'completed',
    json_build_object(
        'message', 'Database initialized successfully',
        'timestamp', CURRENT_TIMESTAMP
    )::jsonb
) ON CONFLICT DO NOTHING;

-- Log the successful initialization
DO $$
BEGIN
    RAISE NOTICE 'Form Analysis Database initialized successfully at %', CURRENT_TIMESTAMP;
END $$;