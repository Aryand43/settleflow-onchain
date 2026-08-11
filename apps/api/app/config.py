from __future__ import annotations

from functools import lru_cache
from typing import Optional

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    demo_mode: bool = True
    database_url: str = "sqlite:///./settleflow.db"
    api_key: str = "dev-key"
    web_base_url: str = "http://localhost:3000"
    merchant_name: str = "SettleFlow Demo Merchant"
    merchant_wallet: str = "0x0000000000000000000000000000000000000001"

    llm_api_key: Optional[str] = None
    llm_model: str = "gpt-4o-mini"
    llm_base_url: str = "https://api.openai.com/v1"

    chain_id: Optional[int] = None
    rpc_url: Optional[str] = None
    payment_contract_address: Optional[str] = None
    usdc_contract_address: Optional[str] = None
    merchant_private_key: Optional[str] = None


@lru_cache
def get_settings() -> Settings:
    return Settings()
