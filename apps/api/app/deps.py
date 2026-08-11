from __future__ import annotations

from fastapi import Header, HTTPException
from typing import Optional

from app.config import get_settings


def verify_api_key(x_api_key: Optional[str] = Header(default=None)) -> None:
    settings = get_settings()
    if x_api_key != settings.api_key:
        raise HTTPException(status_code=401, detail="Invalid or missing API key")
