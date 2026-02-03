from pydantic import BaseModel
from typing import Optional, List
from datetime import datetime


class VpnConfigResponse(BaseModel):
    id: int
    client_id: int
    username: str
    assigned_ip: Optional[str]
    is_active: bool
    last_resolved: Optional[datetime]

    model_config = {"from_attributes": True}


class VpnCredentialsResponse(BaseModel):
    username: str
    password: str
    server: str
    server_id: str


class VpnRoutesResponse(BaseModel):
    routes: List[str]
    domains_count: int
    last_resolved: Optional[datetime]
