"""Add XRay and WireGuard tables

Revision ID: 005_xray_wireguard
Revises: 004_proxy_allowed_ips
Create Date: 2025-02-05

"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = '005_xray_wireguard'
down_revision = '004_proxy_allowed_ips'
branch_labels = None
depends_on = None


def upgrade():
    # XRay server config
    op.create_table(
        'xray_server_config',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('port', sa.Integer(), nullable=False, default=443),
        sa.Column('private_key', sa.String(64), nullable=True),
        sa.Column('public_key', sa.String(64), nullable=True),
        sa.Column('short_id', sa.String(16), nullable=True),
        sa.Column('dest_server', sa.String(255), nullable=False, default='www.microsoft.com'),
        sa.Column('dest_port', sa.Integer(), nullable=False, default=443),
        sa.Column('server_name', sa.String(255), nullable=False, default='www.microsoft.com'),
        sa.Column('is_enabled', sa.Boolean(), nullable=False, default=False),
        sa.Column('created_at', sa.DateTime(), nullable=False, server_default=sa.func.now()),
        sa.Column('updated_at', sa.DateTime(), nullable=True, onupdate=sa.func.now()),
        sa.PrimaryKeyConstraint('id')
    )

    # XRay client configs
    op.create_table(
        'xray_configs',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('client_id', sa.Integer(), nullable=False),
        sa.Column('uuid', sa.String(36), nullable=False),
        sa.Column('short_id', sa.String(16), nullable=False),
        sa.Column('traffic_up', sa.BigInteger(), nullable=False, default=0),
        sa.Column('traffic_down', sa.BigInteger(), nullable=False, default=0),
        sa.Column('expires_at', sa.DateTime(), nullable=True),
        sa.Column('is_active', sa.Boolean(), nullable=False, default=True),
        sa.Column('created_at', sa.DateTime(), nullable=False, server_default=sa.func.now()),
        sa.ForeignKeyConstraint(['client_id'], ['clients.id'], ondelete='CASCADE'),
        sa.PrimaryKeyConstraint('id')
    )
    op.create_index('ix_xray_configs_uuid', 'xray_configs', ['uuid'], unique=True)
    op.create_index('ix_xray_configs_client_id', 'xray_configs', ['client_id'], unique=True)

    # WireGuard server config
    op.create_table(
        'wireguard_server_config',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('private_key', sa.String(64), nullable=True),
        sa.Column('public_key', sa.String(64), nullable=True),
        sa.Column('listen_port', sa.Integer(), nullable=False, default=51820),
        sa.Column('server_ip', sa.String(18), nullable=False, default='10.10.0.1'),
        sa.Column('subnet', sa.String(18), nullable=False, default='10.10.0.0/24'),
        sa.Column('dns', sa.String(255), nullable=False, default='1.1.1.1, 8.8.8.8'),
        sa.Column('mtu', sa.Integer(), nullable=False, default=1420),
        sa.Column('wstunnel_enabled', sa.Boolean(), nullable=False, default=False),
        sa.Column('wstunnel_port', sa.Integer(), nullable=False, default=8080),
        sa.Column('is_enabled', sa.Boolean(), nullable=False, default=False),
        sa.Column('created_at', sa.DateTime(), nullable=False, server_default=sa.func.now()),
        sa.Column('updated_at', sa.DateTime(), nullable=True, onupdate=sa.func.now()),
        sa.PrimaryKeyConstraint('id')
    )

    # WireGuard client configs
    op.create_table(
        'wireguard_configs',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('client_id', sa.Integer(), nullable=False),
        sa.Column('private_key', sa.String(64), nullable=False),
        sa.Column('public_key', sa.String(64), nullable=False),
        sa.Column('preshared_key', sa.String(64), nullable=True),
        sa.Column('assigned_ip', sa.String(18), nullable=False),
        sa.Column('traffic_up', sa.BigInteger(), nullable=False, default=0),
        sa.Column('traffic_down', sa.BigInteger(), nullable=False, default=0),
        sa.Column('last_handshake', sa.DateTime(), nullable=True),
        sa.Column('expires_at', sa.DateTime(), nullable=True),
        sa.Column('is_active', sa.Boolean(), nullable=False, default=True),
        sa.Column('created_at', sa.DateTime(), nullable=False, server_default=sa.func.now()),
        sa.ForeignKeyConstraint(['client_id'], ['clients.id'], ondelete='CASCADE'),
        sa.PrimaryKeyConstraint('id')
    )
    op.create_index('ix_wireguard_configs_client_id', 'wireguard_configs', ['client_id'], unique=True)
    op.create_index('ix_wireguard_configs_public_key', 'wireguard_configs', ['public_key'], unique=True)


def downgrade():
    op.drop_index('ix_wireguard_configs_public_key', 'wireguard_configs')
    op.drop_index('ix_wireguard_configs_client_id', 'wireguard_configs')
    op.drop_table('wireguard_configs')
    op.drop_table('wireguard_server_config')
    op.drop_index('ix_xray_configs_client_id', 'xray_configs')
    op.drop_index('ix_xray_configs_uuid', 'xray_configs')
    op.drop_table('xray_configs')
    op.drop_table('xray_server_config')
