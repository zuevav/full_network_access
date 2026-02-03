from fastapi import APIRouter, HTTPException
from sqlalchemy import select, func
from sqlalchemy.orm import selectinload
from datetime import date

from app.api.deps import DBSession, CurrentClient
from app.models import Client, Payment, DomainRequest
from app.schemas.portal import (
    PortalMeResponse, PortalPaymentsResponse, SubscriptionInfo,
    PaymentHistoryItem, ChangePasswordRequest
)
from app.utils.security import verify_password, get_password_hash
from app.utils.helpers import get_subscription_status, format_date_range


router = APIRouter()


@router.get("/me", response_model=PortalMeResponse)
async def get_me(
    client: CurrentClient,
    db: DBSession
):
    """Get current client info."""
    result = await db.execute(
        select(Client)
        .options(
            selectinload(Client.vpn_config),
            selectinload(Client.domains),
            selectinload(Client.payments),
            selectinload(Client.domain_requests)
        )
        .where(Client.id == client.id)
    )
    client = result.scalar_one()

    # Get subscription info
    valid_until = None
    if client.payments:
        latest = max(client.payments, key=lambda p: p.valid_until)
        valid_until = latest.valid_until

    status, days_left = get_subscription_status(valid_until)

    # Count pending requests
    pending_requests = len([r for r in client.domain_requests if r.status == "pending"])

    username = ""
    if client.vpn_config:
        username = client.vpn_config.username

    return PortalMeResponse(
        name=client.name,
        username=username,
        is_active=client.is_active,
        service_type=client.service_type,
        subscription=SubscriptionInfo(
            status=status,
            valid_until=valid_until,
            days_left=days_left
        ),
        domains_count=len([d for d in client.domains if d.is_active]),
        pending_requests=pending_requests
    )


@router.get("/payments", response_model=PortalPaymentsResponse)
async def get_my_payments(
    client: CurrentClient,
    db: DBSession
):
    """Get client's payment history."""
    result = await db.execute(
        select(Client)
        .options(selectinload(Client.payments))
        .where(Client.id == client.id)
    )
    client = result.scalar_one()

    payments = sorted(client.payments, key=lambda p: p.paid_at, reverse=True)

    valid_until = None
    if payments:
        latest = max(payments, key=lambda p: p.valid_until)
        valid_until = latest.valid_until

    status, days_left = get_subscription_status(valid_until)

    history = [
        PaymentHistoryItem(
            paid_at=p.paid_at,
            amount=p.amount,
            currency=p.currency,
            period=format_date_range(p.valid_from, p.valid_until)
        )
        for p in payments
    ]

    return PortalPaymentsResponse(
        current_subscription=SubscriptionInfo(
            status=status,
            valid_until=valid_until,
            days_left=days_left
        ),
        history=history
    )


@router.post("/account/change-password")
async def change_password(
    request: ChangePasswordRequest,
    client: CurrentClient,
    db: DBSession
):
    """Change client portal password."""
    result = await db.execute(
        select(Client)
        .options(selectinload(Client.vpn_config))
        .where(Client.id == client.id)
    )
    client = result.scalar_one()

    # Verify old password
    if client.portal_password_hash:
        if not verify_password(request.old_password, client.portal_password_hash):
            raise HTTPException(status_code=400, detail="Incorrect current password")
    else:
        # First time change, verify against VPN password
        if client.vpn_config and request.old_password != client.vpn_config.password:
            raise HTTPException(status_code=400, detail="Incorrect current password")

    # Set new password
    client.portal_password_hash = get_password_hash(request.new_password)
    await db.commit()

    return {"message": "Password changed successfully"}


@router.get("/account/setup-guides")
async def get_setup_guides():
    """Get setup guides for all platforms."""
    return {
        "windows": {
            "steps": [
                "Скачайте файл настройки (.ps1)",
                "Нажмите правой кнопкой → 'Запустить от имени администратора'",
                "Дождитесь завершения скрипта",
                "Откройте Настройки → Сеть → VPN",
                "Нажмите 'ProxyGate VPN' → Подключить",
                "При первом подключении введите пароль"
            ]
        },
        "ios": {
            "steps": [
                "Скачайте профиль (откройте в Safari)",
                "Откройте 'Настройки'",
                "Вверху появится 'Профиль загружен'",
                "Нажмите 'Установить' и подтвердите",
                "VPN включится автоматически"
            ]
        },
        "macos": {
            "steps": [
                "Скачайте профиль .mobileconfig",
                "Дважды кликните на файл",
                "Откройте Системные настройки → Профили",
                "Установите профиль ProxyGate",
                "VPN появится в строке меню"
            ]
        },
        "android": {
            "steps": [
                "Установите приложение strongSwan из Play Store",
                "Скачайте профиль .sswan",
                "Откройте файл в strongSwan",
                "Нажмите 'Импорт'",
                "Подключитесь к VPN"
            ]
        }
    }
