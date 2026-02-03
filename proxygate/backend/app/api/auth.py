from fastapi import APIRouter, HTTPException, status
from sqlalchemy import select

from app.api.deps import DBSession, CurrentAdmin
from app.models import AdminUser
from app.schemas.auth import AdminLoginRequest, TokenResponse, AdminUserResponse
from app.utils.security import verify_password, create_access_token, verify_totp
from app.config import settings


router = APIRouter()


@router.post("/login", response_model=TokenResponse)
async def admin_login(request: AdminLoginRequest, db: DBSession):
    """Admin login endpoint."""
    result = await db.execute(
        select(AdminUser).where(AdminUser.username == request.username)
    )
    user = result.scalar_one_or_none()

    if user is None or not verify_password(request.password, user.password_hash):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Incorrect username or password",
        )

    if not user.is_active:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="User account is disabled",
        )

    # Check TOTP if enabled
    if user.totp_secret:
        if not request.totp_code:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="TOTP code required",
            )
        if not verify_totp(user.totp_secret, request.totp_code):
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Invalid TOTP code",
            )

    access_token = create_access_token(
        data={"sub": str(user.id)},
        token_type="admin"
    )

    return TokenResponse(
        access_token=access_token,
        token_type="admin",
        expires_in=settings.jwt_access_token_expire_minutes * 60
    )


@router.post("/refresh", response_model=TokenResponse)
async def refresh_token(admin: CurrentAdmin):
    """Refresh admin access token."""
    access_token = create_access_token(
        data={"sub": str(admin.id)},
        token_type="admin"
    )

    return TokenResponse(
        access_token=access_token,
        token_type="admin",
        expires_in=settings.jwt_access_token_expire_minutes * 60
    )


@router.get("/me", response_model=AdminUserResponse)
async def get_current_admin_info(admin: CurrentAdmin):
    """Get current admin user info."""
    return AdminUserResponse(
        id=admin.id,
        username=admin.username,
        has_totp=admin.totp_secret is not None,
        is_active=admin.is_active
    )
