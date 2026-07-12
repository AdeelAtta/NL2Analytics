from __future__ import annotations

import re
from abc import ABC, abstractmethod
from typing import Any

import httpx

from app.core.config import get_settings


class ModelClient(ABC):
    @abstractmethod
    async def generate(self, prompt: str, **kwargs: Any) -> str:
        ...

    @property
    @abstractmethod
    def model_name(self) -> str:
        ...

    @property
    @abstractmethod
    def cost_per_query(self) -> float:
        ...


class HFInferenceClient(ModelClient):
    def __init__(self, model_id: str, cost: float = 0.0001) -> None:
        settings = get_settings()
        self._model_id = model_id
        self._cost = cost
        self._token = settings.hf_token
        self._api_url = "https://router.huggingface.co/v1/chat/completions"

    @property
    def model_name(self) -> str:
        return self._model_id

    @property
    def cost_per_query(self) -> float:
        return self._cost

    async def generate(self, prompt: str, **kwargs: Any) -> str:
        max_tokens = kwargs.get("max_tokens", 512)
        temperature = kwargs.get("temperature", 0.1)
        timeout = kwargs.get("timeout", 60.0)
        headers = {"Authorization": f"Bearer {self._token}", "Content-Type": "application/json"}

        payload = {
            "model": self._model_id,
            "messages": [{"role": "user", "content": prompt}],
            "max_tokens": max_tokens,
            "temperature": temperature,
        }

        async with httpx.AsyncClient(timeout=timeout) as client:
            for attempt in range(3):
                try:
                    resp = await client.post(self._api_url, json=payload, headers=headers)
                    if resp.status_code == 503:
                        import asyncio
                        await asyncio.sleep(2 ** attempt)
                        continue
                    resp.raise_for_status()
                    result = resp.json()
                    return self._parse_chat_response(result)
                except httpx.TimeoutException:
                    if attempt < 2:
                        import asyncio
                        await asyncio.sleep(2 ** attempt)
                        continue
                    raise
                except Exception:
                    if attempt < 2:
                        import asyncio
                        await asyncio.sleep(2 ** attempt)
                        continue
                    raise
        return ""

    @staticmethod
    def _parse_chat_response(result: Any) -> str:
        try:
            content = result["choices"][0]["message"]["content"]
            return _extract_sql(content)
        except (KeyError, IndexError, TypeError):
            return str(result)

    @staticmethod
    def _parse_response(result: Any, prompt: str) -> str:
        return HFInferenceClient._parse_chat_response(result)


class OpenAIClient(ModelClient):
    def __init__(self, model: str = "gpt-4o", cost: float = 0.01) -> None:
        self._model = model
        self._cost = cost

    @property
    def model_name(self) -> str:
        return self._model

    @property
    def cost_per_query(self) -> float:
        return self._cost

    async def generate(self, prompt: str, **kwargs: Any) -> str:
        try:
            from openai import AsyncOpenAI
        except ImportError:
            return "-- openai package not installed"
        settings = get_settings()
        api_key = kwargs.get("api_key") or settings.openai_api_key
        if not api_key:
            return "-- no openai api key configured"
        client = AsyncOpenAI(api_key=api_key, organization=settings.openai_org_id or None)
        resp = await client.chat.completions.create(
            model=self._model,
            messages=[{"role": "user", "content": prompt}],
            temperature=kwargs.get("temperature", 0.1),
            max_tokens=kwargs.get("max_tokens", 512),
        )
        return resp.choices[0].message.content.strip() if resp.choices else ""


class MockClient(ModelClient):
    def __init__(self, model_name: str = "mock", cost: float = 0.0) -> None:
        self._model_name = model_name
        self._cost = cost

    @property
    def model_name(self) -> str:
        return self._model_name

    @property
    def cost_per_query(self) -> float:
        return self._cost

    async def generate(self, prompt: str, **kwargs: Any) -> str:
        import asyncio

        m = await asyncio.to_thread(lambda: re.search(r"User Request: (.+)", prompt))
        query_text = m.group(1).strip() if m else ""
        if not query_text:
            m2 = await asyncio.to_thread(
                lambda: re.search(r"generate.*for:\s*(.+?)(?:\n|$)", prompt, re.I))
            if m2:
                query_text = m2.group(1).strip()
        return f"SELECT * FROM mock_table WHERE query LIKE '%{query_text}%'"


def _extract_sql(text: str) -> str:
    import re as _re
    cleaned = _re.sub(r"```(?:\w+)?\s*\n(.*?)```", r"\1", text, flags=_re.DOTALL)
    cleaned = cleaned.replace("```", "").strip()
    lines = cleaned.split("\n")
    sql_lines: list[str] = []
    in_sql = False
    for line in lines:
        stripped = line.strip()
        if _re.match(
            r"^(SELECT|WITH|INSERT|UPDATE|DELETE|CREATE|ALTER|DROP|EXPLAIN)\b",
            stripped, _re.I):
            sql_lines.append(stripped)
            in_sql = True
        elif in_sql and (stripped == "" or stripped.startswith(("--", "/*"))):
            sql_lines.append(stripped)
        elif in_sql and not _re.match(r"^[A-Z][a-z]", stripped):
            sql_lines.append(stripped)
        elif in_sql:
            break
    if sql_lines:
        return " ".join(sql_lines).strip()
    return cleaned.strip()


_sqlcoder_model_id: str | None = None


class InferenceFactory:
    _registry: dict[str, type[ModelClient]] = {
        "huggingface": HFInferenceClient,
        "openai": OpenAIClient,
        "mock": MockClient,
    }

    @classmethod
    def register(cls, provider: str, client_cls: type[ModelClient]) -> None:
        cls._registry[provider] = client_cls

    @classmethod
    def create(cls, provider: str, model_name: str | None, cost: float = 0.0) -> ModelClient:
        settings = get_settings()
        is_prod = settings.environment == "production"

        if provider == "huggingface" and not settings.hf_token:
            if is_prod:
                raise RuntimeError("HF_TOKEN not configured. Set HF_TOKEN environment variable for HuggingFace inference.")
            return MockClient(str(model_name or "mock"), cost)
        if provider == "openai" and not settings.openai_api_key:
            if is_prod:
                raise RuntimeError("OPENAI_API_KEY not configured. Set OPENAI_API_KEY environment variable for OpenAI inference.")
            return MockClient(str(model_name or "mock"), cost)
        client_cls = cls._registry.get(provider)
        if client_cls is not None:
            if client_cls is HFInferenceClient:
                if model_name:
                    return HFInferenceClient(model_name, cost)
                return MockClient(str(model_name or "mock"), cost)
            if client_cls is OpenAIClient:
                return OpenAIClient(model_name or "gpt-4o", cost)
            return client_cls(str(model_name or "mock"), cost)
        return MockClient(str(model_name or "mock"), cost)
