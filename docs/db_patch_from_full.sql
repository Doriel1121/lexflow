-- DB patch to align full.sql schema with app expectations
-- Safe to run after restoring full.sql
-- 1) userrole: uppercase -> lowercase
ALTER TABLE users ALTER COLUMN role DROP DEFAULT;
CREATE TYPE userrole_new AS ENUM ('admin','org_admin','lawyer','assistant','viewer');
ALTER TABLE users
  ALTER COLUMN role TYPE userrole_new
  USING (CASE role::text
    WHEN 'ADMIN' THEN 'admin'::userrole_new
    WHEN 'ORG_ADMIN' THEN 'org_admin'::userrole_new
    WHEN 'LAWYER' THEN 'lawyer'::userrole_new
    WHEN 'ASSISTANT' THEN 'assistant'::userrole_new
    WHEN 'VIEWER' THEN 'viewer'::userrole_new
    ELSE 'lawyer'::userrole_new
  END);
ALTER TABLE users ALTER COLUMN role SET DEFAULT 'lawyer';
DROP TYPE userrole;
ALTER TYPE userrole_new RENAME TO userrole;

-- 2) documentprocessingstatus: uppercase -> lowercase
ALTER TABLE documents ALTER COLUMN processing_status DROP DEFAULT;
CREATE TYPE documentprocessingstatus_new AS ENUM ('pending','processing','completed','failed');
ALTER TABLE documents
  ALTER COLUMN processing_status TYPE documentprocessingstatus_new
  USING (CASE processing_status
    WHEN 'PENDING' THEN 'pending'::documentprocessingstatus_new
    WHEN 'PROCESSING' THEN 'processing'::documentprocessingstatus_new
    WHEN 'COMPLETED' THEN 'completed'::documentprocessingstatus_new
    WHEN 'FAILED' THEN 'failed'::documentprocessingstatus_new
    ELSE 'completed'::documentprocessingstatus_new
  END);
ALTER TABLE documents ALTER COLUMN processing_status SET DEFAULT 'completed';
DROP TYPE documentprocessingstatus;
ALTER TYPE documentprocessingstatus_new RENAME TO documentprocessingstatus;

-- 3) deadlinetype: uppercase -> lowercase
CREATE TYPE deadlinetype_new AS ENUM (
  'hearing','filing','response','appeal','statute_of_limitations','other'
);
ALTER TABLE deadlines
  ALTER COLUMN deadline_type TYPE deadlinetype_new
  USING (CASE deadline_type
    WHEN 'HEARING' THEN 'hearing'::deadlinetype_new
    WHEN 'FILING' THEN 'filing'::deadlinetype_new
    WHEN 'RESPONSE' THEN 'response'::deadlinetype_new
    WHEN 'APPEAL' THEN 'appeal'::deadlinetype_new
    WHEN 'STATUTE_OF_LIMITATIONS' THEN 'statute_of_limitations'::deadlinetype_new
    WHEN 'OTHER' THEN 'other'::deadlinetype_new
    ELSE 'other'::deadlinetype_new
  END);
DROP TYPE deadlinetype;
ALTER TYPE deadlinetype_new RENAME TO deadlinetype;
