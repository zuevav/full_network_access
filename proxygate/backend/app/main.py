from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.config import settings
from app.database import init_db, close_db
from app.api import api_router
from app.api.system import get_app_version
from app.middleware.security import SecurityMiddleware


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Application lifespan handler."""
    # Startup
    await init_db()
    yield
    # Shutdown
    await close_db()


app = FastAPI(
    title="ProxyGate",
    description="VPN/Proxy Access Management System",
    version=get_app_version(),
    lifespan=lifespan
)

# Security middleware (brute force protection)
app.add_middleware(SecurityMiddleware)

# CORS middleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # Configure properly in production
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Include API router
app.include_router(api_router, prefix="/api")


@app.get("/health")
async def health_check():
    """Health check endpoint."""
    return {"status": "ok", "version": get_app_version()}


@app.get("/")
async def root():
    """Root endpoint."""
    return {
        "name": "ProxyGate API",
        "version": get_app_version(),
        "docs": "/docs"
    }
