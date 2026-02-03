"""Add admin email field and seed domain templates

Revision ID: 003_admin_email
Revises: 002_security_tables
Create Date: 2024-01-20

"""
from typing import Sequence, Union
import json

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = '003_admin_email'
down_revision: Union[str, None] = '002_security_tables'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


# Pre-configured domain templates
TEMPLATES = [
    {
        "name": "AI Сервисы",
        "description": "ChatGPT, Claude, Gemini, Midjourney и другие AI-платформы",
        "icon": "🤖",
        "domains": [
            "openai.com",
            "chat.openai.com",
            "api.openai.com",
            "platform.openai.com",
            "chatgpt.com",
            "cdn.oaistatic.com",
            "anthropic.com",
            "claude.ai",
            "api.anthropic.com",
            "gemini.google.com",
            "bard.google.com",
            "ai.google.dev",
            "midjourney.com",
            "discord.com",
            "discord.gg",
            "discordapp.com",
            "perplexity.ai",
            "huggingface.co",
            "replicate.com",
            "stability.ai"
        ]
    },
    {
        "name": "Google Сервисы",
        "description": "Google Search, Maps, Drive, Gmail и др.",
        "icon": "🔍",
        "domains": [
            "google.com",
            "google.ru",
            "google.co.uk",
            "googleapis.com",
            "gstatic.com",
            "googleusercontent.com",
            "googlevideo.com",
            "google-analytics.com",
            "googletagmanager.com",
            "gmail.com",
            "mail.google.com",
            "drive.google.com",
            "docs.google.com",
            "sheets.google.com",
            "maps.google.com",
            "translate.google.com"
        ]
    },
    {
        "name": "Облачные хранилища",
        "description": "Dropbox, OneDrive, iCloud, Notion и др.",
        "icon": "☁️",
        "domains": [
            "dropbox.com",
            "dropboxstatic.com",
            "dropboxusercontent.com",
            "onedrive.com",
            "onedrive.live.com",
            "sharepoint.com",
            "live.com",
            "icloud.com",
            "apple.com",
            "mzstatic.com",
            "notion.so",
            "notion.com",
            "box.com"
        ]
    },
    {
        "name": "Разработка",
        "description": "GitHub, npm, Docker Hub, StackOverflow и др.",
        "icon": "💻",
        "domains": [
            "github.com",
            "github.io",
            "githubusercontent.com",
            "githubassets.com",
            "raw.githubusercontent.com",
            "npmjs.com",
            "npmjs.org",
            "registry.npmjs.org",
            "yarnpkg.com",
            "docker.com",
            "docker.io",
            "hub.docker.com",
            "registry.docker.io",
            "stackoverflow.com",
            "stackexchange.com",
            "gitlab.com",
            "bitbucket.org",
            "vercel.com"
        ]
    },
    {
        "name": "Соцсети",
        "description": "Instagram, Twitter/X, Facebook, LinkedIn и др.",
        "icon": "📱",
        "domains": [
            "instagram.com",
            "cdninstagram.com",
            "twitter.com",
            "x.com",
            "twimg.com",
            "t.co",
            "facebook.com",
            "fbcdn.net",
            "fb.com",
            "linkedin.com",
            "licdn.com",
            "pinterest.com",
            "reddit.com",
            "redd.it",
            "tiktok.com"
        ]
    },
    {
        "name": "Стриминг",
        "description": "Netflix, YouTube Premium, Spotify, Disney+ и др.",
        "icon": "🎬",
        "domains": [
            "netflix.com",
            "nflxvideo.net",
            "nflxext.com",
            "nflximg.net",
            "nflxso.net",
            "youtube.com",
            "youtu.be",
            "ytimg.com",
            "yt.be",
            "googlevideo.com",
            "spotify.com",
            "scdn.co",
            "spotifycdn.com",
            "disneyplus.com",
            "disney.com",
            "dssott.com",
            "hulu.com",
            "primevideo.com",
            "amazon.com"
        ]
    },
    {
        "name": "Мессенджеры",
        "description": "Telegram, WhatsApp, Signal и др.",
        "icon": "💬",
        "domains": [
            "telegram.org",
            "t.me",
            "telegram.me",
            "web.telegram.org",
            "core.telegram.org",
            "whatsapp.com",
            "whatsapp.net",
            "wa.me",
            "signal.org",
            "signal.art",
            "viber.com"
        ]
    },
    {
        "name": "Новости",
        "description": "BBC, CNN, Reuters и др.",
        "icon": "📰",
        "domains": [
            "bbc.com",
            "bbc.co.uk",
            "bbci.co.uk",
            "cnn.com",
            "reuters.com",
            "nytimes.com",
            "washingtonpost.com",
            "theguardian.com",
            "bloomberg.com",
            "ft.com",
            "economist.com"
        ]
    }
]


def upgrade() -> None:
    # Add email column to admin_users
    op.add_column('admin_users', sa.Column('email', sa.String(255), nullable=True))

    # Insert pre-configured templates
    templates_table = sa.table(
        'domain_templates',
        sa.column('name', sa.String),
        sa.column('description', sa.String),
        sa.column('icon', sa.String),
        sa.column('domains_json', sa.Text),
        sa.column('is_active', sa.Boolean),
    )

    # Delete existing templates first (in case of re-run)
    op.execute(templates_table.delete())

    # Insert new templates
    for template in TEMPLATES:
        op.execute(
            templates_table.insert().values(
                name=template['name'],
                description=template['description'],
                icon=template['icon'],
                domains_json=json.dumps(template['domains']),
                is_active=True
            )
        )


def downgrade() -> None:
    op.drop_column('admin_users', 'email')
    # Templates remain (optional cleanup)
