"""
System Updates API - Admin only
Handles checking and applying updates from GitHub
"""

import os
import json
import asyncio
import subprocess
from datetime import datetime
from typing import Optional, List
from pathlib import Path

from fastapi import APIRouter, HTTPException, status, BackgroundTasks
from pydantic import BaseModel, Field
import httpx

from app.api.deps import CurrentAdmin, DBSession
from app.config import settings


router = APIRouter()

# Path to store update settings
SETTINGS_FILE = Path("/opt/proxygate/.update_settings.json")
UPDATE_LOG_FILE = Path("/opt/proxygate/.update_log.json")

# Detect correct paths
def get_install_dirs():
    """Detect the correct installation directories.

    Returns: (git_dir, code_dir, deploy_dir)
    - git_dir: where .git is located (for git commands)
    - code_dir: where backend/frontend code is in the repo
    - deploy_dir: where we deploy to
    """
    nested = Path("/opt/proxygate/proxygate")
    base = Path("/opt/proxygate")

    # Case 1: .git at /opt/proxygate, code at /opt/proxygate/proxygate (cloned repo)
    if (base / ".git").exists() and (nested / "backend").exists():
        return base, nested, base  # git at base, code at nested, deploy at base

    # Case 2: .git at /opt/proxygate/proxygate (nested git repo)
    if (nested / ".git").exists():
        return nested, nested, base

    # Case 3: .git at /opt/proxygate, code also at /opt/proxygate
    if (base / ".git").exists():
        return base, base, base

    # Fallback: assume nested structure without git
    if (nested / "backend").exists():
        return nested, nested, base

    return base, base, base

GIT_DIR, CODE_DIR, DEPLOY_DIR = get_install_dirs()
REPO_DIR = CODE_DIR  # For backwards compatibility
INSTALL_DIR = DEPLOY_DIR


class GitHubSettings(BaseModel):
    token: str = Field(..., description="GitHub Personal Access Token")
    repo: str = Field(default="zuevav/full_network_access", description="GitHub repo (owner/repo)")
    branch: str = Field(default="main", description="Branch to pull from")


class UpdateStatus(BaseModel):
    is_updating: bool = False
    last_check: Optional[str] = None
    last_update: Optional[str] = None
    current_commit: Optional[str] = None
    latest_commit: Optional[str] = None
    has_updates: bool = False
    update_log: List[str] = []


class CommitInfo(BaseModel):
    sha: str
    message: str
    author: str
    date: str


class UpdateCheckResponse(BaseModel):
    has_updates: bool
    current_commit: Optional[str] = None
    latest_commit: Optional[str] = None
    commits_behind: int = 0
    recent_commits: List[CommitInfo] = []


def load_settings() -> Optional[dict]:
    """Load saved GitHub settings."""
    if SETTINGS_FILE.exists():
        try:
            with open(SETTINGS_FILE, 'r') as f:
                return json.load(f)
        except:
            pass
    return None


def save_settings(data: dict):
    """Save GitHub settings."""
    SETTINGS_FILE.parent.mkdir(parents=True, exist_ok=True)
    with open(SETTINGS_FILE, 'w') as f:
        json.dump(data, f)
    os.chmod(SETTINGS_FILE, 0o600)


def load_update_status() -> dict:
    """Load update status."""
    if UPDATE_LOG_FILE.exists():
        try:
            with open(UPDATE_LOG_FILE, 'r') as f:
                return json.load(f)
        except:
            pass
    return {
        "is_updating": False,
        "last_check": None,
        "last_update": None,
        "current_commit": None,
        "latest_commit": None,
        "has_updates": False,
        "update_log": []
    }


def save_update_status(data: dict):
    """Save update status."""
    UPDATE_LOG_FILE.parent.mkdir(parents=True, exist_ok=True)
    with open(UPDATE_LOG_FILE, 'w') as f:
        json.dump(data, f)


def get_current_commit() -> Optional[str]:
    """Get current git commit hash."""
    try:
        result = subprocess.run(
            ["/usr/bin/git", "rev-parse", "HEAD"],
            cwd=GIT_DIR,
            capture_output=True,
            text=True,
            timeout=10
        )
        if result.returncode == 0:
            return result.stdout.strip()[:7]
    except:
        pass
    return None


def get_current_branch() -> Optional[str]:
    """Get current git branch."""
    try:
        result = subprocess.run(
            ["/usr/bin/git", "branch", "--show-current"],
            cwd=GIT_DIR,
            capture_output=True,
            text=True,
            timeout=10
        )
        if result.returncode == 0:
            return result.stdout.strip()
    except:
        pass
    return None


@router.get("/settings")
async def get_github_settings(admin: CurrentAdmin):
    """Get current GitHub settings (token hidden)."""
    data = load_settings()
    if data:
        return {
            "configured": True,
            "repo": data.get("repo", ""),
            "branch": data.get("branch", "main"),
            "token_set": bool(data.get("token"))
        }
    return {
        "configured": False,
        "repo": "",
        "branch": "main",
        "token_set": False
    }


@router.post("/settings")
async def save_github_settings(settings: GitHubSettings, admin: CurrentAdmin):
    """Save GitHub settings."""
    save_settings({
        "token": settings.token,
        "repo": settings.repo,
        "branch": settings.branch
    })
    return {"success": True, "message": "Settings saved"}


@router.delete("/settings")
async def delete_github_settings(admin: CurrentAdmin):
    """Delete GitHub settings."""
    if SETTINGS_FILE.exists():
        SETTINGS_FILE.unlink()
    return {"success": True, "message": "Settings deleted"}


@router.get("/status", response_model=UpdateStatus)
async def get_update_status(admin: CurrentAdmin):
    """Get current update status."""
    status_data = load_update_status()
    status_data["current_commit"] = get_current_commit()
    return UpdateStatus(**status_data)


@router.post("/check", response_model=UpdateCheckResponse)
async def check_for_updates(admin: CurrentAdmin):
    """Check GitHub for available updates."""
    gh_settings = load_settings()
    if not gh_settings or not gh_settings.get("token"):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="GitHub settings not configured"
        )

    token = gh_settings["token"]
    repo = gh_settings.get("repo", "zuevav/full_network_access")
    branch = gh_settings.get("branch", "main")

    current_commit = get_current_commit()

    try:
        async with httpx.AsyncClient() as client:
            # Get latest commits from GitHub
            response = await client.get(
                f"https://api.github.com/repos/{repo}/commits",
                params={"sha": branch, "per_page": 10},
                headers={
                    "Authorization": f"token {token}",
                    "Accept": "application/vnd.github.v3+json"
                },
                timeout=30
            )

            if response.status_code == 401:
                raise HTTPException(
                    status_code=status.HTTP_401_UNAUTHORIZED,
                    detail="Invalid GitHub token"
                )

            if response.status_code == 404:
                raise HTTPException(
                    status_code=status.HTTP_404_NOT_FOUND,
                    detail=f"Repository {repo} or branch {branch} not found"
                )

            if response.status_code != 200:
                raise HTTPException(
                    status_code=status.HTTP_502_BAD_GATEWAY,
                    detail=f"GitHub API error: {response.status_code}"
                )

            commits_data = response.json()

            if not commits_data:
                return UpdateCheckResponse(
                    has_updates=False,
                    current_commit=current_commit,
                    latest_commit=current_commit,
                    commits_behind=0,
                    recent_commits=[]
                )

            latest_commit = commits_data[0]["sha"][:7]

            # Find how many commits we're behind
            commits_behind = 0
            recent_commits = []

            for commit in commits_data:
                commit_sha = commit["sha"][:7]
                if commit_sha == current_commit:
                    break
                commits_behind += 1
                recent_commits.append(CommitInfo(
                    sha=commit_sha,
                    message=commit["commit"]["message"].split("\n")[0][:100],
                    author=commit["commit"]["author"]["name"],
                    date=commit["commit"]["author"]["date"]
                ))

            has_updates = commits_behind > 0

            # Update status
            status_data = load_update_status()
            status_data["last_check"] = datetime.now().isoformat()
            status_data["current_commit"] = current_commit
            status_data["latest_commit"] = latest_commit
            status_data["has_updates"] = has_updates
            save_update_status(status_data)

            return UpdateCheckResponse(
                has_updates=has_updates,
                current_commit=current_commit,
                latest_commit=latest_commit,
                commits_behind=commits_behind,
                recent_commits=recent_commits[:5]  # Return last 5 commits
            )

    except httpx.TimeoutException:
        raise HTTPException(
            status_code=status.HTTP_504_GATEWAY_TIMEOUT,
            detail="GitHub API timeout"
        )
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Error checking updates: {str(e)}"
        )


async def run_update_process():
    """Background task to run the update process."""
    status_data = load_update_status()
    # is_updating is already set by /apply endpoint
    log = status_data.get("update_log", [])

    def add_log(message: str):
        log.append(f"[{datetime.now().strftime('%H:%M:%S')}] {message}")
        status_data["update_log"] = log
        save_update_status(status_data)

    try:
        gh_settings = load_settings()
        if not gh_settings:
            add_log("ERROR: GitHub settings not configured")
            return

        branch = gh_settings.get("branch", "main")

        add_log("Starting update process...")

        # Check required commands exist
        required_commands = [
            "/usr/bin/git",
            "/usr/bin/rsync",
            "/usr/bin/npm",
            "/usr/bin/cp",
            "/usr/bin/rm",
            "/usr/bin/chown",
            "/usr/bin/systemctl",
        ]
        missing = [cmd for cmd in required_commands if not Path(cmd).exists()]
        if missing:
            add_log(f"ERROR: Missing required commands: {', '.join(missing)}")
            add_log("Please install missing packages and try again.")
            return

        add_log(f"Git directory: {GIT_DIR}")
        add_log(f"Code directory: {CODE_DIR}")
        add_log(f"Deploy directory: {DEPLOY_DIR}")

        # Step 1: Git fetch
        add_log("Fetching latest changes from GitHub...")
        result = subprocess.run(
            ["/usr/bin/git", "fetch", "origin", branch],
            cwd=GIT_DIR,
            capture_output=True,
            text=True,
            timeout=120
        )
        if result.returncode != 0:
            add_log(f"ERROR: Git fetch failed: {result.stderr}")
            return

        # Step 2: Git reset to origin/branch
        add_log(f"Resetting to origin/{branch}...")
        result = subprocess.run(
            ["/usr/bin/git", "reset", "--hard", f"origin/{branch}"],
            cwd=GIT_DIR,
            capture_output=True,
            text=True,
            timeout=60
        )
        if result.returncode != 0:
            add_log(f"ERROR: Git reset failed: {result.stderr}")
            return

        add_log("Code updated successfully")

        # Step 3: Copy updated files to deploy directory (if code dir != deploy dir)
        if CODE_DIR != DEPLOY_DIR:
            add_log("Copying updated files to deploy directory...")
            # Copy backend (preserving venv)
            subprocess.run(
                ["/usr/bin/rsync", "-av", "--exclude", "venv", "--exclude", "__pycache__",
                 str(CODE_DIR / "backend") + "/", str(DEPLOY_DIR / "backend") + "/"],
                capture_output=True,
                timeout=60
            )
            # Copy frontend source
            subprocess.run(
                ["/usr/bin/rsync", "-av", "--exclude", "node_modules", "--exclude", "dist",
                 str(CODE_DIR / "frontend") + "/", str(DEPLOY_DIR / "frontend") + "/"],
                capture_output=True,
                timeout=60
            )
            add_log("Files copied to deploy directory")

            # Copy VERSION file to deploy directory root
            version_src = CODE_DIR / "VERSION"
            version_dst = DEPLOY_DIR / "VERSION"
            if version_src.exists():
                subprocess.run(
                    ["/usr/bin/cp", str(version_src), str(version_dst)],
                    capture_output=True,
                    timeout=10
                )
                add_log("VERSION file copied")

        # Step 4: Install Python dependencies
        add_log("Installing Python dependencies...")
        backend_dir = DEPLOY_DIR / "backend"
        venv_dir = backend_dir / "venv"
        venv_pip = venv_dir / "bin" / "pip"

        # Create venv if it doesn't exist
        if not venv_pip.exists():
            add_log("Virtual environment not found, creating...")
            result = subprocess.run(
                ["/usr/bin/python3", "-m", "venv", str(venv_dir)],
                cwd=backend_dir,
                capture_output=True,
                text=True,
                timeout=120
            )
            if result.returncode != 0:
                add_log(f"WARNING: venv creation failed: {result.stderr[:200]}")
                add_log("Trying to use global pip...")
                # Fallback to global pip
                result = subprocess.run(
                    ["/usr/bin/pip3", "install", "-r", "requirements.txt"],
                    cwd=backend_dir,
                    capture_output=True,
                    text=True,
                    timeout=300
                )
                if result.returncode != 0:
                    add_log(f"WARNING: global pip install had issues: {result.stderr[:200]}")
                else:
                    add_log("Python dependencies installed globally")
            else:
                add_log("Virtual environment created")
                # Install dependencies in new venv
                result = subprocess.run(
                    [str(venv_pip), "install", "-r", "requirements.txt"],
                    cwd=backend_dir,
                    capture_output=True,
                    text=True,
                    timeout=300
                )
                if result.returncode != 0:
                    add_log(f"WARNING: pip install had issues: {result.stderr[:200]}")
                else:
                    add_log("Python dependencies updated")
        else:
            result = subprocess.run(
                [str(venv_pip), "install", "-r", "requirements.txt"],
                cwd=backend_dir,
                capture_output=True,
                text=True,
                timeout=300
            )
            if result.returncode != 0:
                add_log(f"WARNING: pip install had issues: {result.stderr[:200]}")
            else:
                add_log("Python dependencies updated")

        # Step 5: Run migrations
        add_log("Running database migrations...")
        venv_alembic = venv_dir / "bin" / "alembic"

        if venv_alembic.exists():
            result = subprocess.run(
                [str(venv_alembic), "upgrade", "head"],
                cwd=backend_dir,
                capture_output=True,
                text=True,
                timeout=120
            )
        else:
            # Try global alembic
            result = subprocess.run(
                ["/usr/local/bin/alembic", "upgrade", "head"],
                cwd=backend_dir,
                capture_output=True,
                text=True,
                timeout=120
            )

        if result.returncode != 0:
            add_log(f"WARNING: Migrations had issues: {result.stderr[:200]}")
        else:
            add_log("Database migrations complete")

        # Step 6: Build frontend
        add_log("Building frontend...")
        frontend_dir = DEPLOY_DIR / "frontend"

        # Remove old dist folder to avoid permission issues
        old_dist = frontend_dir / "dist"
        if old_dist.exists():
            subprocess.run(
                ["/usr/bin/rm", "-rf", str(old_dist)],
                capture_output=True,
                timeout=30
            )
            add_log("Removed old dist folder")

        result = subprocess.run(
            ["/usr/bin/npm", "install"],
            cwd=frontend_dir,
            capture_output=True,
            text=True,
            timeout=300
        )
        if result.returncode != 0:
            add_log(f"WARNING: npm install had issues: {result.stderr[:200]}")

        result = subprocess.run(
            ["/usr/bin/npm", "run", "build"],
            cwd=frontend_dir,
            capture_output=True,
            text=True,
            timeout=300
        )
        if result.returncode != 0:
            add_log(f"ERROR: Frontend build failed: {result.stderr[:200]}")
            return
        add_log("Frontend built successfully")

        # Step 7: Copy frontend to web directory
        add_log("Deploying frontend...")
        subprocess.run(["/usr/bin/rm", "-rf", "/var/www/proxygate"], capture_output=True, timeout=30)
        subprocess.run(
            ["/usr/bin/cp", "-r", str(frontend_dir / "dist"), "/var/www/proxygate"],
            capture_output=True,
            timeout=30
        )
        subprocess.run(
            ["/usr/bin/chown", "-R", "www-data:www-data", "/var/www/proxygate"],
            capture_output=True,
            timeout=30
        )
        add_log("Frontend deployed")

        # Step 8: Restart backend service
        add_log("Restarting backend service...")
        result = subprocess.run(
            ["/usr/bin/systemctl", "restart", "proxygate"],
            capture_output=True,
            text=True,
            timeout=60
        )
        if result.returncode != 0:
            add_log(f"WARNING: Service restart had issues: {result.stderr}")
        else:
            add_log("Backend service restarted")

        add_log("UPDATE COMPLETE!")

        status_data["last_update"] = datetime.now().isoformat()
        status_data["current_commit"] = get_current_commit()
        status_data["has_updates"] = False

    except subprocess.TimeoutExpired:
        add_log("ERROR: Command timed out")
    except Exception as e:
        add_log(f"ERROR: {str(e)}")
    finally:
        status_data["is_updating"] = False
        save_update_status(status_data)


@router.post("/apply")
async def apply_updates(background_tasks: BackgroundTasks, admin: CurrentAdmin):
    """Apply available updates (runs in background)."""
    status_data = load_update_status()

    if status_data.get("is_updating"):
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Update already in progress"
        )

    gh_settings = load_settings()
    if not gh_settings or not gh_settings.get("token"):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="GitHub settings not configured"
        )

    # Set is_updating BEFORE starting background task
    # so frontend sees the state immediately on next poll
    status_data["is_updating"] = True
    status_data["update_log"] = ["Starting update..."]
    save_update_status(status_data)

    background_tasks.add_task(run_update_process)

    return {"success": True, "message": "Update started in background"}


@router.get("/log")
async def get_update_log(admin: CurrentAdmin):
    """Get the current update log."""
    status_data = load_update_status()
    return {
        "is_updating": status_data.get("is_updating", False),
        "log": status_data.get("update_log", [])
    }
