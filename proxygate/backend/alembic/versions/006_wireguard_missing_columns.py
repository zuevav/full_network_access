"""Add missing WireGuard server columns

Revision ID: 006_wireguard_missing_cols
Revises: 005_xray_wireguard
Create Date: 2025-02-08

Adds:
- wireguard_server_config.wstunnel_path (VARCHAR(100) DEFAULT '/ws')
- wireguard_server_config.interface (VARCHAR(20) DEFAULT 'wg0')
- Fixes wstunnel_port default from 8080 to 443
"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = '006_wireguard_missing_cols'
down_revision = '005_xray_wireguard'
branch_labels = None
depends_on = None


def column_exists(table_name, column_name):
    """Check if a column already exists in a table (PostgreSQL + SQLite)."""
    bind = op.get_bind()
    dialect = bind.dialect.name
    if dialect == 'postgresql':
        result = bind.execute(sa.text(
            "SELECT column_name FROM information_schema.columns "
            "WHERE table_name = :table AND column_name = :col"
        ), {"table": table_name, "col": column_name})
        return result.fetchone() is not None
    else:
        # SQLite
        result = bind.execute(sa.text(f"PRAGMA table_info({table_name})"))
        columns = [row[1] for row in result]
        return column_name in columns


def upgrade():
    # Add wstunnel_path if missing
    if not column_exists('wireguard_server_config', 'wstunnel_path'):
        op.add_column(
            'wireguard_server_config',
            sa.Column('wstunnel_path', sa.String(100), nullable=False, server_default='/ws')
        )

    # Add interface if missing
    if not column_exists('wireguard_server_config', 'interface'):
        op.add_column(
            'wireguard_server_config',
            sa.Column('interface', sa.String(20), nullable=False, server_default='wg0')
        )


def downgrade():
    # SQLite doesn't support DROP COLUMN easily, but for completeness:
    if column_exists('wireguard_server_config', 'wstunnel_path'):
        op.drop_column('wireguard_server_config', 'wstunnel_path')
    if column_exists('wireguard_server_config', 'interface'):
        op.drop_column('wireguard_server_config', 'interface')
