from __future__ import annotations

import json
from pathlib import Path

from fastapi import FastAPI, HTTPException

FIXTURES_ROOT = Path(__file__).resolve().parent / "fixtures"


def create_mock_feishu_app(
    *,
    scenario: str = "feishu_basic",
    fail_endpoint: str | None = None,
    fail_status: int = 500,
) -> FastAPI:
    scenario_dir = FIXTURES_ROOT / scenario
    if not scenario_dir.exists():
        raise FileNotFoundError(f"未知 mock Feishu 场景: {scenario}")

    token_payload = json.loads((scenario_dir / "token.json").read_text(encoding="utf-8"))
    records_payload = json.loads((scenario_dir / "records.json").read_text(encoding="utf-8"))

    app = FastAPI(title=f"Mock Feishu ({scenario})")
    sent_messages: list[dict] = []

    def maybe_fail(endpoint: str) -> None:
        if fail_endpoint == endpoint:
            raise HTTPException(status_code=fail_status, detail=f"Mock forced failure: {endpoint}")

    @app.get("/health")
    async def health() -> dict[str, str]:
        return {"status": "ok", "scenario": scenario}

    @app.post("/open-apis/auth/v3/tenant_access_token/internal")
    async def tenant_access_token_internal() -> dict:
        maybe_fail("token")
        return {
            "code": 0,
            "msg": "success",
            "tenant_access_token": token_payload["tenant_access_token"],
            "expire": 7200,
        }

    @app.get("/open-apis/bitable/v1/apps/{app_token}/tables/{table_id}/records")
    async def list_records(app_token: str, table_id: str) -> dict:
        maybe_fail("records")
        return {
            "code": 0,
            "msg": "success",
            "data": {
                "has_more": False,
                "page_token": "",
                "total": len(records_payload["items"]),
                "items": records_payload["items"],
                "app_token": app_token,
                "table_id": table_id,
            },
        }

    @app.post("/open-apis/im/v1/messages")
    async def create_message(receive_id_type: str) -> dict:
        maybe_fail("messages")
        if receive_id_type != "chat_id":
            raise HTTPException(status_code=400, detail="Mock only supports receive_id_type=chat_id")
        message_id = f"om_mock_{len(sent_messages) + 1:04d}"
        sent_messages.append({"message_id": message_id, "receive_id_type": receive_id_type})
        return {
            "code": 0,
            "msg": "success",
            "data": {
                "message_id": message_id,
            },
        }

    @app.get("/mock/sent-messages")
    async def get_sent_messages() -> dict:
        return {"items": sent_messages, "total": len(sent_messages)}

    return app
