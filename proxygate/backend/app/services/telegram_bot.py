from typing import Optional
import asyncio

from app.config import settings


class TelegramNotifier:
    """
    Telegram notifications using aiogram 3.

    Sends notifications to admin and clients.
    """

    def __init__(self):
        self.bot = None
        self._initialized = False

    async def _ensure_initialized(self) -> bool:
        """Ensure bot is initialized."""
        if self._initialized:
            return True

        if not settings.telegram_bot_token:
            return False

        try:
            from aiogram import Bot
            self.bot = Bot(token=settings.telegram_bot_token)
            self._initialized = True
            return True
        except Exception as e:
            print(f"Failed to initialize Telegram bot: {e}")
            return False

    async def notify_admin(self, message: str) -> bool:
        """Send notification to admin."""
        if not await self._ensure_initialized():
            return False

        if not settings.admin_telegram_id:
            return False

        try:
            await self.bot.send_message(
                chat_id=settings.admin_telegram_id,
                text=message,
                parse_mode="HTML"
            )
            return True
        except Exception as e:
            print(f"Failed to send admin notification: {e}")
            return False

    async def notify_client(self, telegram_id: str, message: str) -> bool:
        """Send notification to a client."""
        if not await self._ensure_initialized():
            return False

        if not telegram_id:
            return False

        try:
            await self.bot.send_message(
                chat_id=telegram_id,
                text=message,
                parse_mode="HTML"
            )
            return True
        except Exception as e:
            print(f"Failed to send client notification: {e}")
            return False

    async def send_payment_reminder(
        self,
        telegram_id: str,
        client_name: str,
        days_left: int
    ) -> bool:
        """Send payment reminder to client."""
        message = f"""
<b>ProxyGate VPN</b>

{client_name}, ваша подписка истекает через {days_left} дней!

Для продления обратитесь к администратору.
"""
        return await self.notify_client(telegram_id, message)

    async def send_new_client_notification(
        self,
        client_name: str,
        username: str
    ) -> bool:
        """Notify admin about new client."""
        message = f"""
<b>Новый клиент</b>

Имя: {client_name}
Логин: {username}
"""
        return await self.notify_admin(message)

    async def send_domain_request_notification(
        self,
        client_name: str,
        domain: str,
        reason: Optional[str]
    ) -> bool:
        """Notify admin about domain request."""
        message = f"""
<b>Запрос на добавление домена</b>

Клиент: {client_name}
Домен: {domain}
Причина: {reason or 'Не указана'}
"""
        return await self.notify_admin(message)

    async def send_profile_file(
        self,
        telegram_id: str,
        file_data: bytes,
        filename: str
    ) -> bool:
        """Send profile file to client via Telegram."""
        if not await self._ensure_initialized():
            return False

        if not telegram_id:
            return False

        try:
            from aiogram.types import BufferedInputFile
            file = BufferedInputFile(file_data, filename=filename)

            await self.bot.send_document(
                chat_id=telegram_id,
                document=file,
                caption="Ваш VPN профиль ProxyGate"
            )
            return True
        except Exception as e:
            print(f"Failed to send profile file: {e}")
            return False

    async def close(self):
        """Close bot session."""
        if self.bot:
            await self.bot.session.close()


# Global instance
notifier = TelegramNotifier()
