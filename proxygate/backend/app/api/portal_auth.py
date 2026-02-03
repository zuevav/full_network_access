from fastapi import APIRouter, HTTPException, status
from sqlalchemy import select
from sqlalchemy.orm import selectinload

from app.api.deps import DBSession
from app.models import Client, VpnConfig
from app.schemas.auth import ClientLoginRequest, TokenResponse
from app.utils.security import verify_password, create_access_token
from app.config import settings


router = APIRouter()


@router.post("/login", response_model=TokenResponse)
async def client_login(request: ClientLoginRequest, db: DBSession):
    """Client login endpoint (using VPN username)."""
    # Find VPN config by username
    result = await db.execute(
        select(VpnConfig)
        .options(selectinload(VpnConfig.client))
        .where(VpnConfig.username == request.username)
    )
    vpn_config = result.scalar_one_or_none()

    if vpn_config is None:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Incorrect username or password",
        )

    client = vpn_config.client

    # Verify password against portal_password_hash
    if client.portal_password_hash is None:
        # Fallback to VPN password for initial login
        if request.password != vpn_config.password:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Incorrect username or password",
            )
    else:
        if not verify_password(request.password, client.portal_password_hash):
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Incorrect username or password",
            )

    if not client.is_active:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Account is disabled",
        )

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
    # This would need the current_client dependency
    # For now, clients need to re-login
    raise HTTPException(
        status_code=status.HTTP_501_NOT_IMPLEMENTED,
        detail="Please login again"
    )
