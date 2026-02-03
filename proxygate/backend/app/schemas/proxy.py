from pydantic import BaseModel


class ProxyAccountResponse(BaseModel):
    id: int
    client_id: int
    username: str
    is_active: bool

    model_config = {"from_attributes": True}


class ProxyCredentialsResponse(BaseModel):
    username: str
    password: str
    http_host: str
    http_port: int
    socks_host: str
    socks_port: int
    pac_url: str
