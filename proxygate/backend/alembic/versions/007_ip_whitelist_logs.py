"""Create ip_whitelist_logs table

Revision ID: 007_ip_whitelist_logs
Revises: 006_wireguard_missing_cols
Create Date: 2025-02-08
"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = '007_ip_whitelist_logs'
down_revision = '006_wireguard_missing_cols'
branch_labels = None
depends_on = None


def upgrade():
    op.create_table(
        'ip_whitelist_logs',
        sa.Column('id', sa.Integer(), primary_key=True),
        sa.Column('client_id', sa.Integer(), sa.ForeignKey('clients.id', ondelete='CASCADE'), nullable=False),
        sa.Column('ip_address', sa.String(45), nullable=False),
        sa.Column('action', sa.String(10), nullable=False),
        sa.Column('created_at', sa.DateTime(), server_default=sa.func.now(), nullable=False),
    )


def downgrade():
    op.drop_table('ip_whitelist_logs')
