from __future__ import annotations

from dataclasses import dataclass
import json
from typing import Any

import httpx

from app.models.settings import AppSettings


class FeishuConfigError(ValueError):
    pass


@dataclass(slots=True)
class FeishuConfig:
    app_id: str
    app_secret: str
    bitable_app_token: str
    bitable_table_id: str
    base_url: str = "https://open.feishu.cn"
    chat_id: str | None = None


class FeishuClient:
    def __init__(self, config: FeishuConfig) -> None:
        self.config = config
        self._client = httpx.AsyncClient(
            base_url=self.config.base_url.rstrip("/"),
            timeout=30.0,
        )
        self._tenant_access_token: str | None = None

    @classmethod
    def from_settings(cls, settings: AppSettings) -> "FeishuClient":
        return cls.from_values(
            app_id=settings.feishu_app_id,
            app_secret=settings.feishu_app_secret,
            base_url=settings.feishu_base_url,
            bitable_app_token=settings.feishu_bitable_app_token,
            bitable_table_id=settings.feishu_bitable_table_id,
            chat_id=settings.feishu_chat_id,
        )

    @classmethod
    def from_values(
        cls,
        *,
        app_id: str | None,
        app_secret: str | None,
        bitable_app_token: str | None,
        bitable_table_id: str | None,
        base_url: str | None = None,
        chat_id: str | None = None,
    ) -> "FeishuClient":
        app_id = (app_id or "").strip()
        app_secret = (app_secret or "").strip()
        bitable_app_token = (bitable_app_token or "").strip()
        bitable_table_id = (bitable_table_id or "").strip()
        base_url = (base_url or "https://open.feishu.cn").strip()
        chat_id = (chat_id or "").strip() or None

        if not app_id:
            raise FeishuConfigError("缺少 Feishu App ID")
        if not app_secret:
            raise FeishuConfigError("缺少 Feishu App Secret")
        if not bitable_app_token:
            raise FeishuConfigError("缺少多维表格 App Token")
        if not bitable_table_id:
            raise FeishuConfigError("缺少多维表格 Table ID")

        return cls(
            FeishuConfig(
                app_id=app_id,
                app_secret=app_secret,
                bitable_app_token=bitable_app_token,
                bitable_table_id=bitable_table_id,
                base_url=base_url,
                chat_id=chat_id,
            )
        )

    async def __aenter__(self) -> "FeishuClient":
        return self

    async def __aexit__(self, exc_type, exc, tb) -> None:
        await self.aclose()

    async def aclose(self) -> None:
        await self._client.aclose()

    async def get_tenant_access_token(self) -> str:
        if self._tenant_access_token is not None:
            return self._tenant_access_token

        response = await self._client.post(
            "/open-apis/auth/v3/tenant_access_token/internal",
            json={
                "app_id": self.config.app_id,
                "app_secret": self.config.app_secret,
            },
        )
        response.raise_for_status()
        payload = response.json()

        if payload.get("code") != 0:
            raise FeishuConfigError(payload.get("msg") or "获取飞书 tenant_access_token 失败")

        self._tenant_access_token = payload["tenant_access_token"]
        return self._tenant_access_token

    async def list_records(self, *, page_size: int = 100) -> list[dict[str, Any]]:
        token = await self.get_tenant_access_token()
        headers = {"Authorization": f"Bearer {token}"}

        items: list[dict[str, Any]] = []
        page_token: str | None = None

        while True:
            params: dict[str, Any] = {"page_size": page_size}
            if page_token:
                params["page_token"] = page_token

            response = await self._client.get(
                f"/open-apis/bitable/v1/apps/{self.config.bitable_app_token}/tables/{self.config.bitable_table_id}/records",
                headers=headers,
                params=params,
            )
            response.raise_for_status()
            payload = response.json()
            if payload.get("code") != 0:
                raise FeishuConfigError(payload.get("msg") or "读取飞书多维表格记录失败")

            data = payload.get("data", {})
            items.extend(data.get("items", []))
            if not data.get("has_more"):
                break
            page_token = data.get("page_token")
            if not page_token:
                break

        return items

    async def send_text_message(self, *, text: str, chat_id: str | None = None) -> dict[str, Any]:
        token = await self.get_tenant_access_token()
        target_chat_id = (chat_id or self.config.chat_id or "").strip()
        if not target_chat_id:
            raise FeishuConfigError("缺少飞书群 chat_id")

        response = await self._client.post(
            "/open-apis/im/v1/messages",
            headers={"Authorization": f"Bearer {token}"},
            params={"receive_id_type": "chat_id"},
            json={
                "receive_id": target_chat_id,
                "msg_type": "text",
                "content": json.dumps({"text": text}, ensure_ascii=False),
            },
        )
        response.raise_for_status()
        payload = response.json()
        if payload.get("code") != 0:
            raise FeishuConfigError(payload.get("msg") or "发送飞书消息失败")
        return payload.get("data", {})
