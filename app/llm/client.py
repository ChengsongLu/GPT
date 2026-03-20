from __future__ import annotations

import re
from dataclasses import dataclass
from typing import Any

import anthropic
from openai import AsyncOpenAI

from app.core.config import AppConfig, settings


class LLMConfigError(ValueError):
    pass


class LLMRequestError(RuntimeError):
    pass


@dataclass(slots=True)
class ChatResult:
    text: str
    messages: list[dict[str, Any]]


@dataclass(slots=True)
class LLMProviderConfig:
    provider: str
    model: str
    api_key: str
    base_url: str
    temperature: float
    max_tokens: int
    timeout_seconds: float


class LLMClient:
    def __init__(self, config: LLMProviderConfig) -> None:
        self.config = config
        self.model = config.model
        if self.config.provider == "anthropic":
            self.async_client = anthropic.AsyncAnthropic(
                api_key=self.config.api_key,
                base_url=self.config.base_url,
                timeout=self.config.timeout_seconds,
            )
        elif self.config.provider == "openai":
            self.async_client = AsyncOpenAI(
                api_key=self.config.api_key,
                base_url=self.config.base_url,
                timeout=self.config.timeout_seconds,
            )
        else:
            raise LLMConfigError(f"不支持的 LLM_PROVIDER: {self.config.provider}")

    @classmethod
    def from_app_config(cls, app_config: AppConfig | None = None) -> "LLMClient":
        app_config = app_config or settings
        provider = (app_config.llm_provider or "").strip().lower()
        if not provider:
            raise LLMConfigError("缺少 LLM_PROVIDER，请在项目根目录 .env 中配置")

        if provider == "openai":
            api_key = (app_config.openai_api_key or "").strip()
            model = (app_config.openai_model or "").strip()
            base_url = (app_config.openai_base_url or "").strip()
            if not api_key:
                raise LLMConfigError("缺少 OPENAI_API_KEY，请在 .env 中配置")
            if not model:
                raise LLMConfigError("缺少 OPENAI_MODEL，请在 .env 中配置")
            if not base_url:
                raise LLMConfigError("缺少 OPENAI_BASE_URL，请在 .env 中配置")
        elif provider == "anthropic":
            api_key = (app_config.anthropic_api_key or "").strip()
            model = (app_config.anthropic_model or "").strip()
            base_url = (app_config.anthropic_base_url or "").strip()
            if not api_key:
                raise LLMConfigError("缺少 ANTHROPIC_API_KEY，请在 .env 中配置")
            if not model:
                raise LLMConfigError("缺少 ANTHROPIC_MODEL，请在 .env 中配置")
            if not base_url:
                raise LLMConfigError("缺少 ANTHROPIC_BASE_URL，请在 .env 中配置")
        else:
            raise LLMConfigError(f"不支持的 LLM_PROVIDER: {provider}")

        return cls(
            LLMProviderConfig(
                provider=provider,
                model=model,
                api_key=api_key,
                base_url=base_url,
                temperature=app_config.llm_temperature,
                max_tokens=app_config.llm_max_tokens,
                timeout_seconds=app_config.llm_timeout_seconds,
            )
        )

    async def __aenter__(self) -> "LLMClient":
        return self

    async def __aexit__(self, exc_type, exc, tb) -> None:
        await self.aclose()

    async def aclose(self) -> None:
        close = getattr(self.async_client, "close", None)
        if callable(close):
            await close()

    def _serialize_message_content(self, content: Any) -> str:
        if content is None:
            return ""
        if isinstance(content, str):
            return content
        if isinstance(content, (int, float, bool)):
            return str(content)
        if isinstance(content, list):
            parts: list[str] = []
            for item in content:
                if isinstance(item, dict):
                    item_type = item.get("type")
                    if item_type == "text" and item.get("text"):
                        parts.append(str(item["text"]))
                    elif item.get("content") is not None:
                        parts.append(self._serialize_message_content(item["content"]))
                else:
                    item_type = getattr(item, "type", None)
                    if item_type == "text" and getattr(item, "text", None):
                        parts.append(str(item.text))
                    elif getattr(item, "content", None) is not None:
                        parts.append(self._serialize_message_content(item.content))
            return "\n".join(part for part in parts if part)
        if isinstance(content, dict):
            if "text" in content and content["text"] is not None:
                return str(content["text"])
            if "content" in content and content["content"] is not None:
                return self._serialize_message_content(content["content"])
        inner_content = getattr(content, "content", None)
        if inner_content is not None:
            return self._serialize_message_content(inner_content)
        return str(content)

    def _normalize_openai_message_content(self, message: Any) -> str:
        return self._serialize_message_content(getattr(message, "content", ""))

    def _extract_anthropic_text(self, response: Any) -> str:
        parts: list[str] = []
        for block in getattr(response, "content", []):
            if getattr(block, "type", None) == "text" and getattr(block, "text", None):
                parts.append(str(block.text))
        return "\n".join(part for part in parts if part).strip()

    def _preview_for_error(self, value: Any, limit: int = 240) -> str:
        text = self._serialize_message_content(value)
        text = re.sub(r"\s+", " ", text).strip()
        if len(text) <= limit:
            return text
        return text[: limit - 3] + "..."

    async def chat(
        self,
        *,
        messages: list[dict[str, Any]],
        system: str | None = None,
        temperature: float | None = None,
        max_tokens: int | None = None,
    ) -> ChatResult:
        all_messages = list(messages)
        temperature = self.config.temperature if temperature is None else temperature
        max_tokens = self.config.max_tokens if max_tokens is None else max_tokens

        if self.config.provider == "anthropic":
            return await self._chat_anthropic(
                messages=all_messages,
                system=system,
                temperature=temperature,
                max_tokens=max_tokens,
            )
        if self.config.provider == "openai":
            return await self._chat_openai(
                messages=all_messages,
                system=system,
                temperature=temperature,
                max_tokens=max_tokens,
            )
        raise LLMConfigError(f"不支持的 provider: {self.config.provider}")

    async def generate_text(self, *, system_prompt: str, user_prompt: str) -> str:
        result = await self.chat(
            messages=[{"role": "user", "content": user_prompt}],
            system=system_prompt,
        )
        if result.text.strip():
            return result.text.strip()
        raise LLMRequestError("LLM 返回内容为空")

    async def _chat_anthropic(
        self,
        *,
        messages: list[dict[str, Any]],
        system: str | None,
        temperature: float,
        max_tokens: int,
    ) -> ChatResult:
        request_kwargs: dict[str, Any] = {
            "model": self.model,
            "messages": messages,
            "temperature": temperature,
            "max_tokens": max_tokens,
        }
        if system:
            request_kwargs["system"] = system

        try:
            response = await self.async_client.messages.create(**request_kwargs)
        except Exception as exc:
            raise LLMRequestError(f"Anthropic 请求失败: {self._preview_for_error(exc)}") from exc

        assistant_message = {
            "role": "assistant",
            "content": [block for block in response.content],
        }
        all_messages = [*messages, assistant_message]
        text = self._extract_anthropic_text(response)
        if text:
            return ChatResult(text=text, messages=all_messages)
        raise LLMRequestError("Anthropic 返回内容为空")

    async def _chat_openai(
        self,
        *,
        messages: list[dict[str, Any]],
        system: str | None,
        temperature: float,
        max_tokens: int,
    ) -> ChatResult:
        provider_messages = list(messages)
        if system:
            provider_messages.insert(0, {"role": "system", "content": system})

        try:
            response = await self.async_client.chat.completions.create(
                model=self.model,
                messages=provider_messages,
                temperature=temperature,
                max_tokens=max_tokens,
            )
        except Exception as exc:
            raise LLMRequestError(f"OpenAI 请求失败: {self._preview_for_error(exc)}") from exc

        message = response.choices[0].message
        assistant_message = {
            "role": "assistant",
            "content": message,
        }
        all_messages = [*provider_messages, assistant_message]
        text = self._normalize_openai_message_content(message)
        if text.strip():
            return ChatResult(text=text.strip(), messages=all_messages)
        raise LLMRequestError("OpenAI 返回内容为空")
