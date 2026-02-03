"""Add security tables for brute force protection

Revision ID: 002_security
Revises: 001_initial
Create Date: 2024-01-01 00:00:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = '002_security'
down_revision: Union[str, None] = '001_initial'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # Failed login attempts
    op.create_table(
        'failed_logins',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('ip_address', sa.String(45), nullable=False),
        sa.Column('username', sa.String(255), nullable=True),
        sa.Column('user_agent', sa.Text(), nullable=True),
        sa.Column('endpoint', sa.String(100), nullable=False),
        sa.Column('attempt_time', sa.DateTime(), nullable=False, server_default=sa.func.now()),
        sa.PrimaryKeyConstraint('id')
    )
    op.create_index('ix_failed_logins_ip_address', 'failed_logins', ['ip_address'])
    op.create_index('ix_failed_logins_attempt_time', 'failed_logins', ['attempt_time'])

    # Blocked IPs
    op.create_table(
        'blocked_ips',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('ip_address', sa.String(45), nullable=False),
        sa.Column('reason', sa.String(255), nullable=False),
        sa.Column('failed_attempts', sa.Integer(), default=0),
        sa.Column('blocked_at', sa.DateTime(), nullable=False, server_default=sa.func.now()),
        sa.Column('blocked_until', sa.DateTime(), nullable=True),
        sa.Column('is_permanent', sa.Boolean(), default=False),
        sa.Column('unblocked_at', sa.DateTime(), nullable=True),
        sa.Column('unblocked_by', sa.String(100), nullable=True),
        sa.Column('is_active', sa.Boolean(), default=True),
        sa.Column('notes', sa.Text(), nullable=True),
        sa.PrimaryKeyConstraint('id'),
        sa.UniqueConstraint('ip_address')
    )
    op.create_index('ix_blocked_ips_ip_address', 'blocked_ips', ['ip_address'])
    op.create_index('ix_blocked_ips_is_active', 'blocked_ips', ['is_active'])

    # Security events
    op.create_table(
        'security_events',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('event_type', sa.String(50), nullable=False),
        sa.Column('ip_address', sa.String(45), nullable=True),
        sa.Column('username', sa.String(255), nullable=True),
        sa.Column('details', sa.Text(), nullable=True),
        sa.Column('created_at', sa.DateTime(), nullable=False, server_default=sa.func.now()),
        sa.PrimaryKeyConstraint('id')
    )
    op.create_index('ix_security_events_event_type', 'security_events', ['event_type'])
    op.create_index('ix_security_events_created_at', 'security_events', ['created_at'])


def downgrade() -> None:
    op.drop_table('security_events')
    op.drop_table('blocked_ips')
    op.drop_table('failed_logins')
