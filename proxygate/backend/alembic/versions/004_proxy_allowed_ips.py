"""Add allowed_ips to proxy_accounts

Revision ID: 004_proxy_allowed_ips
Revises: 003_admin_email_and_templates
Create Date: 2025-02-04
"""
from alembic import op
import sqlalchemy as sa

# revision identifiers, used by Alembic.
revision = '004_proxy_allowed_ips'
down_revision = '003_admin_email'
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column('proxy_accounts', sa.Column('allowed_ips', sa.Text(), nullable=True))


def downgrade() -> None:
    op.drop_column('proxy_accounts', 'allowed_ips')
