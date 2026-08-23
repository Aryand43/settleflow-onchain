from __future__ import annotations

from functools import lru_cache
from typing import Any, Optional

from pydantic import model_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    @model_validator(mode="before")
    @classmethod
    def _blank_means_unset(cls, values: Any) -> Any:
        """Treats an empty environment variable as absent.

        Docker Compose writes `CHAIN_ID: ""` for any `${CHAIN_ID:-}` the host
        hasn't set, and `Optional[int]` refuses to parse `""` — so a container
        with no chain configured used to crash on startup instead of running
        without one. Kubernetes ConfigMaps and most CI systems template the same
        way.

        Dropping the key entirely (rather than coercing to None) lets each field
        fall back to its own default, which is what "unset" should mean.
        """
        if not isinstance(values, dict):
            return values
        return {k: v for k, v in values.items() if not (isinstance(v, str) and v.strip() == "")}

    demo_mode: bool = True
    database_url: str = "sqlite:///./settleflow.db"
    api_key: str = "dev-key"
    web_base_url: str = "http://localhost:3000"
    merchant_name: str = "SettleFlow Demo Merchant"
    merchant_wallet: str = "0x0000000000000000000000000000000000000001"

    # Signing key for dashboard sessions. The default is fine for local demos;
    # anything reachable from the internet must set this, or every JWT this app
    # issues is forgeable by anyone who has read the source.
    jwt_secret: str = "dev-secret-change-me"
    jwt_expire_minutes: int = 60 * 24 * 7

    llm_api_key: Optional[str] = None
    llm_model: str = "gpt-4.1-mini"
    llm_base_url: str = "https://api.openai.com/v1"

    # --- Email delivery ---
    # Unset SMTP_HOST keeps PreviewEmailService (writes HTML files to
    # email_previews/). Set it and reminders are really sent.
    smtp_host: Optional[str] = None
    smtp_port: int = 587
    smtp_username: Optional[str] = None
    smtp_password: Optional[str] = None
    smtp_starttls: bool = True
    email_from: Optional[str] = None
    email_from_name: str = "SettleFlow"

    chain_id: Optional[int] = None
    rpc_url: Optional[str] = None

    # What the *browser* should use to reach the chain, when that differs from
    # what the API uses. Under Docker Compose the API talks to `http://anvil:8545`
    # over the compose network, a hostname no browser can resolve — the customer's
    # wallet needs `http://localhost:8545` instead. Hosted deployments reach the
    # same public URL from both sides, so this stays unset and falls back.
    public_rpc_url: Optional[str] = None
    payment_contract_address: Optional[str] = None
    usdc_contract_address: Optional[str] = None
    merchant_private_key: Optional[str] = None
    demo_payer_private_key: Optional[str] = None


@lru_cache
def get_settings() -> Settings:
    return Settings()
