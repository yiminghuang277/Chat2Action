from __future__ import annotations

import json
from typing import Any

import httpx

from backend.app.config import get_settings


class DashScopeClient:
    def __init__(self) -> None:
        self.settings = get_settings()

    @property
    def enabled(self) -> bool:
        return bool(self.settings.dashscope_api_key)

    async def chat(self, messages: list[dict[str, str]], response_format: dict[str, Any] | None = None) -> str:
        payload: dict[str, Any] = {
            "model": self.settings.model_name,
            "temperature": 0,
            "messages": messages,
        }
        if response_format:
            payload["response_format"] = response_format

        headers = {
            "Authorization": f"Bearer {self.settings.dashscope_api_key}",
            "Content-Type": "application/json",
        }
        async with httpx.AsyncClient(timeout=self.settings.request_timeout_seconds) as client:
            response = await client.post(
                f"{self.settings.dashscope_base_url}/chat/completions",
                headers=headers,
                json=payload,
            )
            response.raise_for_status()
            data = response.json()
        return data["choices"][0]["message"]["content"]

    async def json_chat(self, messages: list[dict[str, str]]) -> dict[str, Any]:
        content = await self.chat(messages, response_format={"type": "json_object"})
        return json.loads(content)

