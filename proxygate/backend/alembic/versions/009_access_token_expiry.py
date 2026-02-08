"""Add access_token_expires_at column to clients

Revision ID: 009_access_token_expiry
Revises: 008_template_is_public
Create Date: 2026-02-08
"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = '009_access_token_expiry'
down_revision = '008_template_is_public'
branch_labels = None
depends_on = None


def upgrade():
    op.add_column('clients', sa.Column('access_token_expires_at', sa.DateTime(), nullable=True))


def downgrade():
    op.drop_column('clients', 'access_token_expires_at')
