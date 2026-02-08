from pydantic_settings import BaseSettings
from pydantic import Field
from functools import lru_cache
from typing import Optional


class Settings(BaseSettings):
    # Server
    vps_public_ip: str = Field(default="127.0.0.1")
    vps_domain: str = Field(default="vpn.localhost")

    # Admin
    admin_username: str = Field(default="admin")
    admin_password: str = Field(...)  # Required — no insecure default
    secret_key: str = Field(...)  # Required — no insecure default

    # JWT
    jwt_algorithm: str = Field(default="HS256")
    jwt_access_token_expire_minutes: int = Field(default=60 * 24)  # 24 hours
    jwt_refresh_token_expire_days: int = Field(default=7)

    # IKEv2
    ikev2_server_id: str = Field(default="vpn.localhost")
    ikev2_pool_subnet: str = Field(default="10.0.0.0/24")
    ikev2_dns: str = Field(default="1.1.1.1,8.8.8.8")

    # 3proxy
    proxy_http_port: int = Field(default=3128)
    proxy_socks_port: int = Field(default=1080)

    # Telegram
    telegram_bot_token: Optional[str] = Field(default=None)
    admin_telegram_id: Optional[str] = Field(default=None)

    # Database
    database_url: str = Field(default="sqlite+aiosqlite:///./data/proxygate.db")

    # Paths
    swanctl_dir: str = Field(default="/etc/swanctl")
    swanctl_conf_dir: str = Field(default="/etc/swanctl/conf.d")
    proxy_config_path: str = Field(default="/etc/3proxy/3proxy.cfg")
    proxy_passwd_path: str = Field(default="/etc/3proxy/passwd")

    model_config = {
        "env_file": ".env",
        "env_file_encoding": "utf-8",
        "extra": "ignore"
    }


@lru_cache
def get_settings() -> Settings:
    return Settings()


settings = get_settings()
