from fastapi import APIRouter, HTTPException, status, Request
from sqlalchemy import select
from sqlalchemy.orm import selectinload

from app.api.deps import DBSession
from app.models import Client, VpnConfig
from app.schemas.auth import ClientLoginRequest, TokenResponse
from app.utils.security import verify_password, create_access_token
from app.services.security_service import SecurityService
from app.middleware.security import get_client_ip
from app.config import settings


router = APIRouter()


@router.post("/login", response_model=TokenResponse)
async def client_login(request: ClientLoginRequest, req: Request, db: DBSession):
    """Client login endpoint (using VPN username)."""
    client_ip = get_client_ip(req)
    user_agent = req.headers.get("User-Agent")
    security = SecurityService(db)

    # Check if IP is blocked
    is_blocked, _ = await security.is_ip_blocked(client_ip)
    if is_blocked:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail=f"IP заблокирован после множества неудачных попыток. Попробуйте позже.",
        )

    # Find VPN config by username
    result = await db.execute(
        select(VpnConfig)
        .options(selectinload(VpnConfig.client))
        .where(VpnConfig.username == request.username)
    )
    vpn_config = result.scalar_one_or_none()

    if vpn_config is None:
        await security.record_failed_attempt(
            ip_address=client_ip,
            username=request.username,
            endpoint="/api/portal/auth/login",
            user_agent=user_agent
        )
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Incorrect username or password",
        )

    client = vpn_config.client

    # Verify password against portal_password_hash
    auth_ok = False
    if client.portal_password_hash is None:
        # Fallback to VPN password for initial login
        auth_ok = (request.password == vpn_config.password)
    else:
        auth_ok = verify_password(request.password, client.portal_password_hash)

    if not auth_ok:
        block = await security.record_failed_attempt(
            ip_address=client_ip,
            username=request.username,
            endpoint="/api/portal/auth/login",
            user_agent=user_agent
        )
        if block:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail=f"IP заблокирован после множества неудачных попыток. Попробуйте позже.",
            )
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Incorrect username or password",
        )

    if not client.is_active:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Account is disabled",
        )

    await security.record_successful_login(client_ip, request.username)

    access_token = create_access_token(
        data={"sub": str(client.id)},
        token_type="client"
    )

    return TokenResponse(
        access_token=access_token,
        token_type="client",
        expires_in=settings.jwt_refresh_token_expire_days * 24 * 60 * 60
    )


@router.post("/refresh", response_model=TokenResponse)
async def refresh_client_token(db: DBSession):
    """Refresh client access token (requires existing valid token)."""
    raise HTTPException(
        status_code=status.HTTP_501_NOT_IMPLEMENTED,
        detail="Please login again"
    )


@router.post("/link/{access_token}", response_model=TokenResponse)
async def login_by_link(access_token: str, db: DBSession):
    """Login by unique client link (no password required)."""
    result = await db.execute(
        select(Client).where(Client.access_token == access_token)
    )
    client = result.scalar_one_or_none()

    if client is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Link not found",
        )

    if not client.is_active:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Account is disabled",
        )

    jwt_token = create_access_token(
        data={"sub": str(client.id)},
        token_type="client"
    )

    return TokenResponse(
        access_token=jwt_token,
        token_type="client",
        expires_in=settings.jwt_refresh_token_expire_days * 24 * 60 * 60
    )
