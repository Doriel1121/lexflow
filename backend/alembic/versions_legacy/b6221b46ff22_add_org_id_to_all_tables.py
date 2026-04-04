"""add_org_id_to_all_tables

Revision ID: b6221b46ff22
Revises: a1b2c3d4e5f6
Create Date: 2026-02-27 08:10:40.252230

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = 'b6221b46ff22'
down_revision: Union[str, Sequence[str], None] = 'a1b2c3d4e5f6'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Add organization_id to all tenant-scoped tables."""
    # SQLite requires batch mode for adding foreign keys
    with op.batch_alter_table('clients', schema=None) as batch_op:
        batch_op.add_column(sa.Column('organization_id', sa.Integer(), nullable=True))
        batch_op.create_index(batch_op.f('ix_clients_organization_id'), ['organization_id'], unique=False)
        batch_op.create_foreign_key('fk_clients_organization_id', 'organisations', ['organization_id'], ['id'])
    
    with op.batch_alter_table('tags', schema=None) as batch_op:
        batch_op.add_column(sa.Column('organization_id', sa.Integer(), nullable=True))
        batch_op.create_index(batch_op.f('ix_tags_organization_id'), ['organization_id'], unique=False)
        batch_op.create_foreign_key('fk_tags_organization_id', 'organisations', ['organization_id'], ['id'])
    
    with op.batch_alter_table('summaries', schema=None) as batch_op:
        batch_op.add_column(sa.Column('organization_id', sa.Integer(), nullable=True))
        batch_op.create_index(batch_op.f('ix_summaries_organization_id'), ['organization_id'], unique=False)
        batch_op.create_foreign_key('fk_summaries_organization_id', 'organisations', ['organization_id'], ['id'])
    
    with op.batch_alter_table('audit_logs', schema=None) as batch_op:
        batch_op.add_column(sa.Column('organization_id', sa.Integer(), nullable=True))
        batch_op.create_index(batch_op.f('ix_audit_logs_organization_id'), ['organization_id'], unique=False)
        batch_op.create_foreign_key('fk_audit_logs_organization_id', 'organisations', ['organization_id'], ['id'])
    
    with op.batch_alter_table('case_notes', schema=None) as batch_op:
        batch_op.add_column(sa.Column('organization_id', sa.Integer(), nullable=True))
        batch_op.create_index(batch_op.f('ix_case_notes_organization_id'), ['organization_id'], unique=False)
        batch_op.create_foreign_key('fk_case_notes_organization_id', 'organisations', ['organization_id'], ['id'])


def downgrade() -> None:
    """Remove organization_id from all tables."""
    with op.batch_alter_table('case_notes', schema=None) as batch_op:
        batch_op.drop_constraint('fk_case_notes_organization_id', type_='foreignkey')
        batch_op.drop_index(batch_op.f('ix_case_notes_organization_id'))
        batch_op.drop_column('organization_id')
    
    with op.batch_alter_table('audit_logs', schema=None) as batch_op:
        batch_op.drop_constraint('fk_audit_logs_organization_id', type_='foreignkey')
        batch_op.drop_index(batch_op.f('ix_audit_logs_organization_id'))
        batch_op.drop_column('organization_id')
    
    with op.batch_alter_table('summaries', schema=None) as batch_op:
        batch_op.drop_constraint('fk_summaries_organization_id', type_='foreignkey')
        batch_op.drop_index(batch_op.f('ix_summaries_organization_id'))
        batch_op.drop_column('organization_id')
    
    with op.batch_alter_table('tags', schema=None) as batch_op:
        batch_op.drop_constraint('fk_tags_organization_id', type_='foreignkey')
        batch_op.drop_index(batch_op.f('ix_tags_organization_id'))
        batch_op.drop_column('organization_id')
    
    with op.batch_alter_table('clients', schema=None) as batch_op:
        batch_op.drop_constraint('fk_clients_organization_id', type_='foreignkey')
        batch_op.drop_index(batch_op.f('ix_clients_organization_id'))
        batch_op.drop_column('organization_id')
