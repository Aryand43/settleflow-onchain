from __future__ import annotations

import json
import re
from datetime import date, timedelta

from app.schemas import ParsedCommand
from app.services.llm import LlmNotConfigured, LlmRequestError, chat_completions, llm_configured


DEMO_PATTERN = re.compile(
    r"collect\s+(\d+(?:\.\d+)?)\s+(\w+)\s+from\s+(.+?)\s+for\s+(.+?),\s*due\s+in\s+(\d+)\s+days?",
    re.IGNORECASE,
)

ALT_PATTERN = re.compile(
    r"collect\s+(\d+(?:\.\d+)?)\s+(\w+)\s+from\s+(.+?)\s+for\s+(.+?)(?:\.|$)",
    re.IGNORECASE,
)


def _parse_deterministic(command: str) -> ParsedCommand | None:
    text = command.strip()
    match = DEMO_PATTERN.search(text)
    if match:
        amount, currency, customer_name, description, days = match.groups()
        desc = description.strip()
        if desc.lower().startswith("the "):
            desc = desc[4:]
        return ParsedCommand(
            customer_name=customer_name.strip(),
            amount=float(amount),
            currency=currency.upper(),
            description=desc,
            due_date=date.today() + timedelta(days=int(days)),
            confidence=1.0,
            missing_fields=[],
        )

    match = ALT_PATTERN.search(text)
    if match:
        amount, currency, customer_name, description = match.groups()
        return ParsedCommand(
            customer_name=customer_name.strip(),
            amount=float(amount),
            currency=currency.upper(),
            description=description.strip(),
            due_date=date.today() + timedelta(days=7),
            confidence=0.85,
            missing_fields=["due_date"],
        )
    return None


async def _parse_with_llm(command: str) -> ParsedCommand | None:
    if not llm_configured():
        return None

    system_prompt = (
        "Extract invoice fields from the user command. Return JSON only with keys: "
        "customer_name, amount, currency, description, due_date (YYYY-MM-DD), confidence, missing_fields."
    )
    content = await chat_completions(
        [
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": command},
        ],
        response_format={"type": "json_object"},
    )
    data = json.loads(content)
    return ParsedCommand(**data)


async def parse_command(command: str) -> ParsedCommand:
    deterministic = _parse_deterministic(command)
    if deterministic:
        return deterministic

    try:
        llm_result = await _parse_with_llm(command)
        if llm_result:
            return llm_result
    except (LlmNotConfigured, LlmRequestError, Exception):
        pass

    return ParsedCommand(
        customer_name="",
        amount=0,
        currency="USDC",
        description="",
        due_date=date.today() + timedelta(days=7),
        confidence=0.0,
        missing_fields=["customer_name", "amount", "description"],
    )
