#!/usr/bin/env python3
"""
Initialize database with admin user and seed data.

Usage: python scripts/init_db.py
"""

import asyncio
import sys
import os
import json

# Add parent directory to path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select

from app.database import async_session_maker, init_db
from app.models import AdminUser, DomainTemplate
from app.utils.security import get_password_hash
from app.config import settings


# Initial domain templates from spec
INITIAL_TEMPLATES = [
    {
        "name": "AI Сервисы",
        "icon": "🤖",
        "description": "ChatGPT, Claude, Gemini, Midjourney и другие AI-платформы",
        "domains": [
            "openai.com", "chat.openai.com", "api.openai.com", "platform.openai.com",
            "chatgpt.com", "oaiusercontent.com",
            "claude.ai", "anthropic.com",
            "gemini.google.com", "bard.google.com", "aistudio.google.com",
            "midjourney.com", "discord.com", "discord.gg",
            "perplexity.ai",
            "poe.com",
            "huggingface.co",
            "replicate.com",
            "stability.ai",
            "copilot.microsoft.com"
        ]
    },
    {
        "name": "Стриминг",
        "icon": "🎬",
        "description": "Netflix, YouTube Premium, Spotify, Disney+ и др.",
        "domains": [
            "netflix.com", "nflxvideo.net", "nflxext.com", "nflximg.net",
            "youtube.com", "googlevideo.com", "ytimg.com", "ggpht.com",
            "spotify.com", "spotifycdn.com", "scdn.co",
            "disneyplus.com", "disney-plus.net", "bamgrid.com", "dssott.com",
            "hbomax.com", "max.com",
            "primevideo.com", "amazonvideo.com"
        ]
    },
    {
        "name": "Соцсети",
        "icon": "📱",
        "description": "Instagram, Twitter/X, Facebook, LinkedIn и др.",
        "domains": [
            "instagram.com", "cdninstagram.com",
            "twitter.com", "x.com", "twimg.com", "t.co",
            "facebook.com", "fbcdn.net", "fb.com", "fb.me",
            "linkedin.com", "licdn.com",
            "threads.net",
            "tiktok.com", "tiktokcdn.com"
        ]
    },
    {
        "name": "Разработка",
        "icon": "💻",
        "description": "GitHub, npm, Docker Hub, StackOverflow и др.",
        "domains": [
            "github.com", "github.io", "githubusercontent.com", "githubassets.com",
            "npmjs.com", "npmjs.org",
            "docker.com", "docker.io",
            "stackoverflow.com", "stackexchange.com",
            "gitlab.com",
            "bitbucket.org",
            "pypi.org", "pythonhosted.org", "files.pythonhosted.org",
            "crates.io",
            "vercel.com", "netlify.com"
        ]
    },
    {
        "name": "Google Сервисы",
        "icon": "🔍",
        "description": "Google Search, Maps, Drive, Gmail и др.",
        "domains": [
            "google.com", "googleapis.com", "gstatic.com", "googleusercontent.com",
            "google.co.uk", "google.de", "google.fr",
            "gmail.com", "mail.google.com",
            "drive.google.com", "docs.google.com",
            "maps.google.com", "maps.googleapis.com",
            "translate.google.com",
            "play.google.com",
            "accounts.google.com"
        ]
    },
    {
        "name": "Облачные хранилища",
        "icon": "☁️",
        "description": "Dropbox, OneDrive, iCloud, Notion и др.",
        "domains": [
            "dropbox.com", "dropboxstatic.com",
            "onedrive.com", "onedrive.live.com", "sharepoint.com",
            "icloud.com", "apple.com",
            "box.com", "boxcdn.net",
            "notion.so", "notion.site",
            "mega.nz", "mega.io"
        ]
    }
]


async def create_admin_user(db: AsyncSession) -> None:
    """Create initial admin user."""
    # Check if admin exists
    result = await db.execute(
        select(AdminUser).where(AdminUser.username == settings.admin_username)
    )
    existing = result.scalar_one_or_none()

    if existing:
        print(f"Admin user '{settings.admin_username}' already exists")
        return

    admin = AdminUser(
        username=settings.admin_username,
        password_hash=get_password_hash(settings.admin_password),
        is_active=True
    )
    db.add(admin)
    await db.commit()
    print(f"Created admin user: {settings.admin_username}")


async def create_domain_templates(db: AsyncSession) -> None:
    """Create initial domain templates."""
    for template_data in INITIAL_TEMPLATES:
        # Check if template exists
        result = await db.execute(
            select(DomainTemplate).where(DomainTemplate.name == template_data["name"])
        )
        existing = result.scalar_one_or_none()

        if existing:
            print(f"Template '{template_data['name']}' already exists")
            continue

        template = DomainTemplate(
            name=template_data["name"],
            icon=template_data["icon"],
            description=template_data["description"],
            domains_json=json.dumps(template_data["domains"]),
            is_active=True
        )
        db.add(template)
        print(f"Created template: {template_data['name']}")

    await db.commit()


async def main():
    """Initialize database."""
    print("Initializing ProxyGate database...")

    # Create tables
    await init_db()
    print("Database tables created")

    # Create initial data
    async with async_session_maker() as db:
        await create_admin_user(db)
        await create_domain_templates(db)

    print("\nDatabase initialization complete!")
    print(f"\nAdmin credentials:")
    print(f"  Username: {settings.admin_username}")
    print(f"  Password: {settings.admin_password}")
    print("\nIMPORTANT: Change the admin password in production!")


if __name__ == "__main__":
    asyncio.run(main())
