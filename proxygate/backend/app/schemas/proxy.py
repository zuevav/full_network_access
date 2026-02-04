from pydantic import BaseModel
from typing import Optional, List


class ProxyAccountResponse(BaseModel):
    id: int
    client_id: int
    username: str
    is_active: bool
    allowed_ips: Optional[str] = None

    model_config = {"from_attributes": True}


class ProxyCredentialsResponse(BaseModel):
    username: str
    password: str
    http_host: str
    http_port: int
    socks_host: str
    socks_port: int
    pac_url: str
    allowed_ips: Optional[List[str]] = None


class ProxyAllowedIpsUpdate(BaseModel):
    allowed_ips: List[str]
