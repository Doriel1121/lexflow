-- Add organization_id column to all tables
-- Run this in Docker: docker exec -i ai-lawyer-db-1 psql -U admin -d lexflow_db < fix_database.sql

-- Cases table
ALTER TABLE cases ADD COLUMN IF NOT EXISTS organization_id INTEGER;
ALTER TABLE cases ADD CONSTRAINT fk_cases_organization FOREIGN KEY (organization_id) REFERENCES organizations(id) ON DELETE CASCADE;
CREATE INDEX IF NOT EXISTS idx_cases_organization_id ON cases(organization_id);

-- Documents table
ALTER TABLE documents ADD COLUMN IF NOT EXISTS organization_id INTEGER;
ALTER TABLE documents ADD CONSTRAINT fk_documents_organization FOREIGN KEY (organization_id) REFERENCES organizations(id) ON DELETE CASCADE;
CREATE INDEX IF NOT EXISTS idx_documents_organization_id ON documents(organization_id);

-- Clients table
ALTER TABLE clients ADD COLUMN IF NOT EXISTS organization_id INTEGER;
ALTER TABLE clients ADD CONSTRAINT fk_clients_organization FOREIGN KEY (organization_id) REFERENCES organizations(id) ON DELETE CASCADE;
CREATE INDEX IF NOT EXISTS idx_clients_organization_id ON clients(organization_id);

-- Tags table
ALTER TABLE tags ADD COLUMN IF NOT EXISTS organization_id INTEGER;
ALTER TABLE tags ADD CONSTRAINT fk_tags_organization FOREIGN KEY (organization_id) REFERENCES organizations(id) ON DELETE CASCADE;
CREATE INDEX IF NOT EXISTS idx_tags_organization_id ON tags(organization_id);

-- Summaries table
ALTER TABLE summaries ADD COLUMN IF NOT EXISTS organization_id INTEGER;
ALTER TABLE summaries ADD CONSTRAINT fk_summaries_organization FOREIGN KEY (organization_id) REFERENCES organizations(id) ON DELETE CASCADE;
CREATE INDEX IF NOT EXISTS idx_summaries_organization_id ON summaries(organization_id);

-- Audit logs table
ALTER TABLE audit_logs ADD COLUMN IF NOT EXISTS organization_id INTEGER;
ALTER TABLE audit_logs ADD CONSTRAINT fk_audit_logs_organization FOREIGN KEY (organization_id) REFERENCES organizations(id) ON DELETE CASCADE;
CREATE INDEX IF NOT EXISTS idx_audit_logs_organization_id ON audit_logs(organization_id);

-- Case notes table (if exists)
DO $$ 
BEGIN
    IF EXISTS (SELECT FROM information_schema.tables WHERE table_name = 'case_notes') THEN
        ALTER TABLE case_notes ADD COLUMN IF NOT EXISTS organization_id INTEGER;
        ALTER TABLE case_notes ADD CONSTRAINT fk_case_notes_organization FOREIGN KEY (organization_id) REFERENCES organizations(id) ON DELETE CASCADE;
        CREATE INDEX IF NOT EXISTS idx_case_notes_organization_id ON case_notes(organization_id);
    END IF;
END $$;

-- Verify changes
SELECT 
    table_name, 
    column_name, 
    data_type 
FROM information_schema.columns 
WHERE column_name = 'organization_id' 
ORDER BY table_name;
