"""init

Revision ID: b76aa1711216
Revises: 
Create Date: 2026-02-07 15:18:18.792327

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql
import pgvector

# revision identifiers, used by Alembic.
revision: str = 'b76aa1711216'
down_revision: Union[str, Sequence[str], None] = None
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    # asyncpg requires one statement per execute call
    op.execute("DROP TABLE IF EXISTS summaries CASCADE")
    op.execute("DROP TABLE IF EXISTS document_tag_association CASCADE")
    op.execute("DROP TABLE IF EXISTS documents CASCADE")
    op.execute("DROP TABLE IF EXISTS case_notes CASCADE")
    op.execute("DROP TABLE IF EXISTS cases CASCADE")
    op.execute("DROP TABLE IF EXISTS audit_logs CASCADE")
    op.execute("DROP TABLE IF EXISTS users CASCADE")
    op.execute("DROP TABLE IF EXISTS tags CASCADE")
    op.execute("DROP TABLE IF EXISTS clients CASCADE")
    op.execute("DROP TYPE IF EXISTS casestatus CASCADE")

    op.execute("""CREATE TABLE clients (
        id SERIAL NOT NULL, name VARCHAR NOT NULL, contact_person VARCHAR,
        contact_email VARCHAR, phone_number VARCHAR, address VARCHAR,
        created_at TIMESTAMP WITHOUT TIME ZONE, updated_at TIMESTAMP WITHOUT TIME ZONE,
        PRIMARY KEY (id))""")
    op.execute("CREATE INDEX ix_clients_id ON clients (id)")
    op.execute("CREATE INDEX ix_clients_name ON clients (name)")

    op.execute("""CREATE TABLE tags (
        id SERIAL NOT NULL, name VARCHAR NOT NULL, PRIMARY KEY (id))""")
    op.execute("CREATE UNIQUE INDEX ix_tags_name ON tags (name)")
    op.execute("CREATE INDEX ix_tags_id ON tags (id)")

    op.execute("""CREATE TABLE users (
        id SERIAL NOT NULL, email VARCHAR NOT NULL, hashed_password VARCHAR NOT NULL,
        full_name VARCHAR, is_active BOOLEAN, is_superuser BOOLEAN,
        created_at TIMESTAMP WITHOUT TIME ZONE, updated_at TIMESTAMP WITHOUT TIME ZONE,
        PRIMARY KEY (id))""")
    op.execute("CREATE UNIQUE INDEX ix_users_email ON users (email)")
    op.execute("CREATE INDEX ix_users_id ON users (id)")

    op.execute("""CREATE TABLE audit_logs (
        id SERIAL NOT NULL, user_id INTEGER NOT NULL, action VARCHAR NOT NULL,
        details JSONB, timestamp TIMESTAMP WITHOUT TIME ZONE NOT NULL,
        ip_address VARCHAR, user_agent VARCHAR,
        FOREIGN KEY(user_id) REFERENCES users (id), PRIMARY KEY (id))""")
    op.execute("CREATE INDEX ix_audit_logs_id ON audit_logs (id)")

    op.execute("CREATE TYPE casestatus AS ENUM ('OPEN', 'CLOSED', 'PENDING')")

    op.execute("""CREATE TABLE cases (
        id SERIAL NOT NULL, title VARCHAR NOT NULL, description TEXT,
        status casestatus NOT NULL, client_id INTEGER NOT NULL,
        created_by_user_id INTEGER NOT NULL,
        created_at TIMESTAMP WITHOUT TIME ZONE, updated_at TIMESTAMP WITHOUT TIME ZONE,
        FOREIGN KEY(client_id) REFERENCES clients (id),
        FOREIGN KEY(created_by_user_id) REFERENCES users (id), PRIMARY KEY (id))""")
    op.execute("CREATE INDEX ix_cases_id ON cases (id)")
    op.execute("CREATE INDEX ix_cases_title ON cases (title)")

    op.execute("""CREATE TABLE case_notes (
        id SERIAL NOT NULL, case_id INTEGER NOT NULL, user_id INTEGER NOT NULL,
        content TEXT NOT NULL, created_at TIMESTAMP WITHOUT TIME ZONE,
        updated_at TIMESTAMP WITHOUT TIME ZONE,
        FOREIGN KEY(case_id) REFERENCES cases (id),
        FOREIGN KEY(user_id) REFERENCES users (id), PRIMARY KEY (id))""")
    op.execute("CREATE INDEX ix_case_notes_id ON case_notes (id)")

    op.execute("""CREATE TABLE documents (
        id SERIAL NOT NULL, filename VARCHAR NOT NULL, s3_url VARCHAR NOT NULL,
        case_id INTEGER NOT NULL, uploaded_by_user_id INTEGER NOT NULL,
        content TEXT, classification VARCHAR, language VARCHAR,
        created_at TIMESTAMP WITHOUT TIME ZONE, updated_at TIMESTAMP WITHOUT TIME ZONE,
        FOREIGN KEY(case_id) REFERENCES cases (id),
        FOREIGN KEY(uploaded_by_user_id) REFERENCES users (id), PRIMARY KEY (id))""")
    op.execute("CREATE INDEX ix_documents_id ON documents (id)")

    op.execute("""CREATE TABLE document_tag_association (
        document_id INTEGER NOT NULL, tag_id INTEGER NOT NULL,
        FOREIGN KEY(document_id) REFERENCES documents (id),
        FOREIGN KEY(tag_id) REFERENCES tags (id),
        PRIMARY KEY (document_id, tag_id))""")

    op.execute("""CREATE TABLE summaries (
        id SERIAL NOT NULL, document_id INTEGER NOT NULL, content TEXT NOT NULL,
        key_dates JSONB, parties JSONB, missing_documents_suggestion TEXT,
        created_at TIMESTAMP WITHOUT TIME ZONE, updated_at TIMESTAMP WITHOUT TIME ZONE,
        FOREIGN KEY(document_id) REFERENCES documents (id),
        UNIQUE (document_id), PRIMARY KEY (id))""")
    op.execute("CREATE INDEX ix_summaries_id ON summaries (id)")


def downgrade() -> None:
    """Downgrade schema."""
    # ### commands auto generated by Alembic - please adjust! ###
    op.drop_index(op.f('ix_summaries_id'), table_name='summaries')
    op.drop_table('summaries')
    op.drop_table('document_tag_association')
    op.drop_index(op.f('ix_documents_id'), table_name='documents')
    op.drop_table('documents')
    op.drop_index(op.f('ix_case_notes_id'), table_name='case_notes')
    op.drop_table('case_notes')
    op.drop_index(op.f('ix_cases_title'), table_name='cases')
    op.drop_index(op.f('ix_cases_id'), table_name='cases')
    op.drop_table('cases')
    op.drop_index(op.f('ix_audit_logs_id'), table_name='audit_logs')
    op.drop_table('audit_logs')
    op.drop_index(op.f('ix_users_id'), table_name='users')
    op.drop_index(op.f('ix_users_email'), table_name='users')
    op.drop_table('users')
    op.drop_index(op.f('ix_tags_name'), table_name='tags')
    op.drop_index(op.f('ix_tags_id'), table_name='tags')
    op.drop_table('tags')
    op.drop_index(op.f('ix_clients_name'), table_name='clients')
    op.drop_index(op.f('ix_clients_id'), table_name='clients')
    op.drop_table('clients')
    # ### end Alembic commands ###
