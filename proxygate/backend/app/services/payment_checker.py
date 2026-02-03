from datetime import date, timedelta
from typing import List, Tuple
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from sqlalchemy.orm import selectinload

from app.models import Client, Payment
from app.services.telegram_bot import notifier


class PaymentChecker:
    """
    Checks payment status and handles expiration.

    Run as cron job every 15 minutes.
    """

    async def check_all(self, db: AsyncSession) -> dict:
        """
        Check all clients for payment status.

        Returns summary of actions taken.
        """
        today = date.today()

        result = await db.execute(
            select(Client)
            .options(selectinload(Client.payments))
            .where(Client.is_active == True)
        )
        clients = result.scalars().all()

        summary = {
            "deactivated": [],
            "warned": [],
            "checked": 0
        }

        for client in clients:
            summary["checked"] += 1

            if not client.payments:
                continue

            # Get latest payment
            latest_payment = max(client.payments, key=lambda p: p.valid_until)
            days_left = (latest_payment.valid_until - today).days

            # Expired - deactivate
            if days_left < 0:
                await self._deactivate_client(client, db)
                summary["deactivated"].append(client.name)

            # Expiring soon - warn (3 days, 1 day)
            elif days_left in [3, 1]:
                await self._send_warning(client, days_left)
                summary["warned"].append((client.name, days_left))

        await db.commit()
        return summary

    async def _deactivate_client(self, client: Client, db: AsyncSession):
        """Deactivate client due to expired payment."""
        client.is_active = False

        # Deactivate VPN config
        if client.vpn_config:
            client.vpn_config.is_active = False

        # Deactivate proxy account
        if client.proxy_account:
            client.proxy_account.is_active = False

        # Notify admin
        await notifier.notify_admin(
            f"<b>Клиент деактивирован</b>\n\n"
            f"Имя: {client.name}\n"
            f"Причина: истекла оплата"
        )

        # Notify client
        if client.telegram_id:
            await notifier.notify_client(
                client.telegram_id,
                f"<b>ProxyGate VPN</b>\n\n"
                f"{client.name}, ваша подписка истекла.\n"
                f"Доступ временно приостановлен.\n\n"
                f"Для продления обратитесь к администратору."
            )

    async def _send_warning(self, client: Client, days_left: int):
        """Send expiration warning to client."""
        if client.telegram_id:
            await notifier.send_payment_reminder(
                client.telegram_id,
                client.name,
                days_left
            )

    async def find_expired(self, db: AsyncSession) -> List[Client]:
        """Find all clients with expired payments."""
        today = date.today()

        result = await db.execute(
            select(Client)
            .options(selectinload(Client.payments))
            .where(Client.is_active == True)
        )
        clients = result.scalars().all()

        expired = []
        for client in clients:
            if client.payments:
                latest = max(client.payments, key=lambda p: p.valid_until)
                if latest.valid_until < today:
                    expired.append(client)

        return expired

    async def find_expiring_soon(
        self,
        db: AsyncSession,
        days: int = 7
    ) -> List[Tuple[Client, int]]:
        """Find clients expiring within N days."""
        today = date.today()
        threshold = today + timedelta(days=days)

        result = await db.execute(
            select(Client)
            .options(selectinload(Client.payments))
            .where(Client.is_active == True)
        )
        clients = result.scalars().all()

        expiring = []
        for client in clients:
            if client.payments:
                latest = max(client.payments, key=lambda p: p.valid_until)
                days_left = (latest.valid_until - today).days
                if 0 <= days_left <= days:
                    expiring.append((client, days_left))

        return sorted(expiring, key=lambda x: x[1])
