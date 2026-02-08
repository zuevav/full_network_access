"""Add is_public column to domain_templates

Revision ID: 008_template_is_public
Revises: 007_ip_whitelist_logs
Create Date: 2026-02-08
"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = '008_template_is_public'
down_revision = '007_ip_whitelist_logs'
branch_labels = None
depends_on = None


def upgrade():
    op.add_column('domain_templates', sa.Column('is_public', sa.Boolean(), server_default=sa.text('false'), nullable=False))


def downgrade():
    op.drop_column('domain_templates', 'is_public')
