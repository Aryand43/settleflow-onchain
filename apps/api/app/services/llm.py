from __future__ import annotations

from typing import Any, Optional

import httpx

from app.config import get_settings


class LlmNotConfigured(Exception):
    """Raised when LLM_API_KEY is missing or blank."""


class LlmRequestError(Exception):
    """Raised when the upstream chat completions call fails."""


# Project keys often 403 on older aliases like gpt-4o-mini even when billing is fine.
FALLBACK_MODELS = (
    "gpt-4.1-mini",
    "gpt-5-mini",
    "gpt-5.4-mini",
    "gpt-4o-mini",
    "gpt-4.1",
    "gpt-4o",
)


def llm_configured() -> bool:
    key = get_settings().llm_api_key
    return bool(key and key.strip())


def _format_llm_http_error(response: httpx.Response) -> str:
    try:
        data = response.json()
        err = data.get("error", data)
        if isinstance(err, dict):
            msg = err.get("message") or err.get("code") or str(err)
        else:
            msg = str(err)
    except Exception:
        msg = (response.text or response.reason_phrase or "")[:800]
    return f"LLM request failed ({response.status_code}): {msg.strip()}"


def _is_retryable_model_error(status: int, message: str) -> bool:
    if status in (403, 404):
        return True
    lower = message.lower()
    return "does not have access" in lower or "model_not_found" in lower


async def chat_completions(
    messages: list[dict[str, str]],
    *,
    response_format: Optional[dict[str, Any]] = None,
    temperature: float = 0.2,
) -> str:
    settings = get_settings()
    if not llm_configured():
        raise LlmNotConfigured("LLM_API_KEY is not set")

    models: list[str] = []
    preferred = (settings.llm_model or "").strip()
    if preferred:
        models.append(preferred)
    for name in FALLBACK_MODELS:
        if name not in models:
            models.append(name)

    headers = {
        "Authorization": f"Bearer {settings.llm_api_key.strip()}",
        "Content-Type": "application/json",
    }
    url = f"{settings.llm_base_url.rstrip('/')}/chat/completions"

    last_error = "LLM request failed"
    async with httpx.AsyncClient(timeout=30) as client:
        for model in models:
            payload: dict[str, Any] = {
                "model": model,
                "messages": messages,
            }
            if not model.startswith(("gpt-5", "o1", "o3", "o4")):
                payload["temperature"] = temperature
            if response_format and not model.startswith(("gpt-5", "o1", "o3", "o4")):
                payload["response_format"] = response_format

            try:
                response = await client.post(url, headers=headers, json=payload)
            except httpx.HTTPStatusError as exc:
                response = exc.response
            except Exception as exc:
                last_error = f"LLM request failed: {type(exc).__name__}: {exc}"
                continue

            if response.status_code == 200:
                try:
                    content = response.json()["choices"][0]["message"]["content"]
                except Exception as exc:
                    raise LlmRequestError(f"LLM returned an unexpected payload: {exc}") from exc
                if not content or not str(content).strip():
                    raise LlmRequestError("LLM returned an empty reply")
                return str(content).strip()

            last_error = _format_llm_http_error(response)
            if response.status_code == 401:
                raise LlmRequestError(last_error)
            if _is_retryable_model_error(response.status_code, last_error):
                continue
            raise LlmRequestError(last_error)

    raise LlmRequestError(last_error)
