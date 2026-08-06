from __future__ import annotations

import asyncio
import json
from typing import Any

from fastapi import FastAPI, File, Header, HTTPException, UploadFile
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel, Field

from .activation.desktop_provider import DesktopProvider
from .activation.queue import (
    ActivationQueueConflict,
    cancel_activation_batch,
    get_activation_batch,
    list_activation_queue,
    start_activation_worker,
    stop_activation_worker,
    worker_status,
)
from .adapters import CockpitAdapter
from .audit import list_audit, write_audit
from .db import init_db
from .delivery_queue import (
    delivery_worker_status,
    get_delivery_job,
    list_delivery_jobs,
    reconcile_delivery_quantity,
    start_delivery_worker,
    stop_delivery_worker,
)
from .oauth_batch import (
    cancel_refresh_batch,
    create_refresh_batch,
    get_refresh_batch,
    list_refresh_batches,
    oauth_batch_status,
    retry_failed_refresh_jobs,
    start_oauth_batch_worker,
    stop_oauth_batch_worker,
)
from .fulfillment import (
    activate_inventory_item,
    activate_order,
    get_fulfillment,
    handle_buyer_message,
    handle_order_paid,
    list_fulfillments,
    preview_delivery_text,
    ship_order,
)
from .inventory import (
    InventoryDeleteBlocked,
    _items_from_cpa,
    delete_inventory_item,
    import_cpa,
    list_inventory,
    manual_update_status,
    normalize_account,
    summary,
)
from .oauth_reauth import (
    OAuthReauthError,
    automatic_reauthorize_inventory_oauth_retry,
    oauth_reauth_status,
    exchange_callback,
    import_oauth_payload,
)
from .settings_store import get_all_settings, update_settings


app = FastAPI(title="Xianyu Codex Fulfillment", version="1.1.0")
app.mount("/static", StaticFiles(directory="app/static"), name="static")


class ImportCpaRequest(BaseModel):
    payload: Any
    sync_cockpit: bool = False


class OrderPaidRequest(BaseModel):
    order_id: str = Field(min_length=1)
    buyer_id: str = Field(min_length=1)
    item_id: str = Field(min_length=1)
    chat_id: str = Field(min_length=1)
    account_id: str = Field(min_length=1)
    platform: str = "chatgpt"
    quantity: int = Field(default=1, ge=1)


class ManualShipRequest(BaseModel):
    order_id: str
    buyer_id: str = ""
    item_id: str = ""
    platform: str = "chatgpt"
    quantity: int = Field(default=1, ge=1)
    send_to_xianyu: bool = True


class BuyerMessageRequest(BaseModel):
    order_id: str
    buyer_id: str = ""
    text: str = Field(min_length=1)


class SettingsRequest(BaseModel):
    values: dict[str, Any]


class ActivateItemRequest(BaseModel):
    order_id: str = ""
    inventory_id: int


class InventoryStatusRequest(BaseModel):
    inventory_id: int
    status: str
    order_id: str = ""


class OAuthRefreshRequest(BaseModel):
    force_reauth: bool = False


class OAuthCallbackRequest(BaseModel):
    callback_url: str = Field(min_length=1)


class PreviewRequest(BaseModel):
    inventory_ids: list[int] = Field(default_factory=list)


class DeliveryQuantityRequest(BaseModel):
    quantity: int = Field(ge=1)


class OAuthRefreshBatchRequest(BaseModel):
    inventory_ids: list[int] = Field(default_factory=list)
    status: str = ""
    q: str = ""


def _cockpit_lines_from_payload(payload: Any) -> list[str]:
    lines: list[str] = []
    for raw in _items_from_cpa(payload):
        item = normalize_account(raw)
        if not item["email"]:
            continue
        extra = {
            "primary_token": item["primary_token"],
            "session_token": item["session_token"],
            "refresh_token": item["refresh_token"],
            "cookies": item["cookies"],
            "lifecycle_status": item["lifecycle_status"],
            "validity_status": item["validity_status"],
            "display_status": item["display_status"],
            "reset_count": item["reset_count"],
            "source": "xianyu-codex-fulfillment",
        }
        extra = {key: value for key, value in extra.items() if value not in (None, "", [], {})}
        lines.append(
            f"{json.dumps(item['email'], ensure_ascii=False)} "
            f"{json.dumps(item['password'], ensure_ascii=False)} "
            f"{json.dumps(extra, ensure_ascii=False)}"
        )
    return lines


@app.on_event("startup")
def startup() -> None:
    init_db()
    start_activation_worker()
    start_delivery_worker()
    start_oauth_batch_worker()


@app.on_event("shutdown")
async def shutdown() -> None:
    await stop_activation_worker()
    await stop_delivery_worker()
    await stop_oauth_batch_worker()


@app.get("/")
def index() -> FileResponse:
    return FileResponse("app/static/index.html")


@app.get("/health")
def health() -> dict[str, Any]:
    return {
        "ok": True,
        "service": "xianyu-codex-fulfillment",
        "activation_worker": worker_status(),
        "delivery_worker": delivery_worker_status(),
        "oauth_batch": oauth_batch_status(),
        "desktop_instance": DesktopProvider().status(),
    }


@app.post("/inventory/import-cpa")
async def import_inventory(body: ImportCpaRequest) -> dict[str, Any]:
    result = import_cpa(body.payload)
    if body.sync_cockpit:
        result["cockpit"] = await CockpitAdapter().import_accounts(_cockpit_lines_from_payload(body.payload))
    write_audit("api.inventory.import_cpa", payload={"result": result, "sync_cockpit": body.sync_cockpit})
    return result


@app.post("/inventory/import-cpa-files")
async def import_inventory_files(
    files: list[UploadFile] = File(...),
    sync_cockpit: bool = False,
) -> dict[str, Any]:
    payloads: list[Any] = []
    failed: list[dict[str, str]] = []
    for file in files:
        name = file.filename or "unnamed.json"
        if not name.lower().endswith(".json"):
            failed.append({"file": name, "error": "not a json file"})
            continue
        try:
            raw = await file.read()
            payloads.append(json.loads(raw.decode("utf-8-sig")))
        except Exception as exc:
            failed.append({"file": name, "error": str(exc)})
    result = (
        import_cpa(payloads)
        if payloads
        else {
            "created": 0,
            "updated": 0,
            "skipped": 0,
            "total": 0,
            "details": [],
            "details_truncated": False,
        }
    )
    result["files"] = len(files)
    result["parsed_files"] = len(payloads)
    result["failed_files"] = failed
    if sync_cockpit and payloads:
        lines: list[str] = []
        for payload in payloads:
            lines.extend(_cockpit_lines_from_payload(payload))
        result["cockpit"] = await CockpitAdapter().import_accounts(lines)
    write_audit("api.inventory.import_cpa_files", payload={"result": result, "sync_cockpit": sync_cockpit})
    return result


@app.get("/inventory")
def inventory(status: str = "", q: str = "", limit: int = 200) -> list[dict[str, Any]]:
    return list_inventory(status=status, q=q, limit=limit)


@app.get("/inventory/summary")
def inventory_summary() -> dict[str, Any]:
    return summary()


@app.post("/inventory/manual-status")
def inventory_manual_status(body: InventoryStatusRequest) -> dict[str, Any]:
    try:
        return manual_update_status(body.inventory_id, body.status, body.order_id)
    except Exception as exc:
        raise HTTPException(400, str(exc)) from exc


@app.delete("/inventory/{inventory_id}")
def inventory_delete(inventory_id: int) -> dict[str, Any]:
    try:
        return delete_inventory_item(inventory_id)
    except InventoryDeleteBlocked as exc:
        raise HTTPException(409, str(exc)) from exc
    except KeyError as exc:
        message = str(exc.args[0]) if exc.args else "库存不存在"
        raise HTTPException(404, message) from exc
    except Exception as exc:
        raise HTTPException(400, str(exc)) from exc

@app.post("/inventory/{inventory_id}/oauth/refresh")
async def inventory_oauth_refresh(
    inventory_id: int,
    body: OAuthRefreshRequest | None = None,
) -> dict[str, Any]:
    """Start a full local Cockpit OAuth reauthorization.

    The route name is kept for existing clients, but it deliberately skips
    the stored OpenAI refresh token. Reauthorization always uses the local
    aBai/Cockpit browser worker and its configured local mailbox provider.
    """
    try:
        result = await asyncio.to_thread(
            automatic_reauthorize_inventory_oauth_retry,
            inventory_id,
            priority=True,
        )
        return {"ok": True, "action": "reauthorized", **result}
    except KeyError as exc:
        raise HTTPException(404, str(exc)) from exc
    except OAuthReauthError as exc:
        raise HTTPException(409, f"自动 OAuth 失败: {exc}") from exc
    except Exception as exc:
        raise HTTPException(400, str(exc)) from exc
@app.get("/oauth/reauth/status")
def oauth_reauth_status_endpoint() -> dict[str, Any]:
    return oauth_reauth_status()

@app.get("/oauth/refresh-batches")
def oauth_refresh_batches(limit: int = 50) -> list[dict[str, Any]]:
    return list_refresh_batches(limit)


@app.post("/oauth/refresh-batches")
async def oauth_refresh_batch_create(body: OAuthRefreshBatchRequest) -> dict[str, Any]:
    try:
        return create_refresh_batch(body.inventory_ids, status_filter=body.status, query=body.q)
    except Exception as exc:
        raise HTTPException(400, str(exc)) from exc


@app.get("/oauth/refresh-batches/{batch_id}")
def oauth_refresh_batch_get(batch_id: int) -> dict[str, Any]:
    result = get_refresh_batch(batch_id)
    if not result:
        raise HTTPException(404, "OAuth 批量任务不存在")
    return result


@app.delete("/oauth/refresh-batches/{batch_id}")
def oauth_refresh_batch_cancel(batch_id: int) -> dict[str, Any]:
    try:
        return cancel_refresh_batch(batch_id)
    except KeyError as exc:
        raise HTTPException(404, str(exc)) from exc


@app.post("/oauth/refresh-batches/{batch_id}/retry-failed")
def oauth_refresh_batch_retry(batch_id: int) -> dict[str, Any]:
    try:
        return retry_failed_refresh_jobs(batch_id)
    except KeyError as exc:
        raise HTTPException(404, str(exc)) from exc


@app.post("/inventory/{inventory_id}/oauth/import")
async def inventory_oauth_import(
    inventory_id: int,
    file: UploadFile = File(...),
) -> dict[str, Any]:
    try:
        raw = await file.read()
        payload = json.loads(raw.decode("utf-8-sig"))
        return {"ok": True, "action": "imported", **import_oauth_payload(inventory_id, payload)}
    except json.JSONDecodeError as exc:
        raise HTTPException(400, f"OAuth JSON 解析失败: {exc}") from exc
    except KeyError as exc:
        raise HTTPException(404, str(exc)) from exc
    except OAuthReauthError as exc:
        raise HTTPException(400, str(exc)) from exc
    except Exception as exc:
        raise HTTPException(400, str(exc)) from exc


@app.post("/oauth/reauth/{session_id}/callback")
async def oauth_reauth_callback(
    session_id: str,
    body: OAuthCallbackRequest,
) -> dict[str, Any]:
    try:
        return {"ok": True, "action": "authorized", **await exchange_callback(session_id, body.callback_url)}
    except OAuthReauthError as exc:
        raise HTTPException(400, str(exc)) from exc
    except Exception as exc:
        raise HTTPException(400, str(exc)) from exc


@app.post("/delivery/preview")
def delivery_preview(body: PreviewRequest) -> dict[str, Any]:
    return preview_delivery_text(body.inventory_ids)


@app.get("/delivery/jobs")
def delivery_jobs(limit: int = 100) -> list[dict[str, Any]]:
    return list_delivery_jobs(limit)


@app.get("/delivery/jobs/{order_id}")
def delivery_job(order_id: str) -> dict[str, Any]:
    result = get_delivery_job(order_id)
    if not result:
        raise HTTPException(404, "delivery job not found")
    return result


@app.post("/delivery/jobs/{order_id}/reconcile")
async def delivery_job_reconcile(order_id: str, body: DeliveryQuantityRequest) -> dict[str, Any]:
    try:
        return await reconcile_delivery_quantity(order_id, body.quantity)
    except KeyError as exc:
        raise HTTPException(404, str(exc)) from exc
    except Exception as exc:
        raise HTTPException(400, str(exc)) from exc


@app.get("/settings")
def settings() -> dict[str, Any]:
    return get_all_settings()


@app.put("/settings")
def save_settings(body: SettingsRequest) -> dict[str, Any]:
    return update_settings(body.values)


@app.get("/desktop-instance/status")
def desktop_instance_status() -> dict[str, Any]:
    return DesktopProvider().status()


@app.post("/desktop-instance/test")
def desktop_instance_test() -> dict[str, Any]:
    provider = DesktopProvider()
    status = provider.status()
    status["test"] = "snapshot"
    if status.get("online") and status.get("pid"):
        try:
            snapshot = provider._ui("snapshot", int(status["pid"]))
            status["ui_snapshot"] = {
                "window": snapshot.get("window"),
                "text_count": len(snapshot.get("texts") or []),
                "button_count": len(snapshot.get("buttons") or []),
            }
        except Exception as exc:
            status["ui_error"] = str(exc)
    return status

@app.get("/activation/queue")
def activation_queue(limit: int = 100) -> list[dict[str, Any]]:
    return list_activation_queue(limit)


@app.delete("/activation/queue/{batch_id}")
def activation_queue_cancel(batch_id: int) -> dict[str, Any]:
    try:
        return cancel_activation_batch(batch_id)
    except ActivationQueueConflict as exc:
        raise HTTPException(409, str(exc)) from exc
    except KeyError as exc:
        message = str(exc.args[0]) if exc.args else "激活批次不存在"
        raise HTTPException(404, message) from exc
    except Exception as exc:
        raise HTTPException(400, str(exc)) from exc


@app.get("/activation/worker/status")
def activation_worker_status() -> dict[str, Any]:
    return worker_status()


@app.get("/activation/batches/{batch_id}")
def activation_batch(batch_id: int) -> dict[str, Any]:
    result = get_activation_batch(batch_id)
    if not result:
        raise HTTPException(404, "激活批次不存在")
    return result


@app.post("/fulfillments/ship")
async def manual_ship(
    body: ManualShipRequest,
    idempotency_key: str = Header(default="", alias="Idempotency-Key"),
) -> dict[str, Any]:
    try:
        return await ship_order(
            order_id=body.order_id,
            buyer_id=body.buyer_id,
            item_id=body.item_id,
            quantity=body.quantity,
            platform=body.platform,
            send_to_xianyu=body.send_to_xianyu,
            idempotency_key=idempotency_key or f"manual-ship:{body.order_id}",
        )
    except Exception as exc:
        raise HTTPException(400, str(exc)) from exc


@app.post("/fulfillments/activate-item")
async def activate_item(body: ActivateItemRequest) -> dict[str, Any]:
    try:
        return await activate_inventory_item(body.order_id, body.inventory_id)
    except Exception as exc:
        raise HTTPException(400, str(exc)) from exc


@app.post("/fulfillments/{order_id}/activate")
async def activate_all(order_id: str) -> dict[str, Any]:
    try:
        return await activate_order(order_id)
    except Exception as exc:
        raise HTTPException(400, str(exc)) from exc


@app.post("/webhooks/xianyu/order-paid")
async def xianyu_order_paid(
    body: OrderPaidRequest,
    idempotency_key: str = Header(default="", alias="Idempotency-Key"),
) -> dict[str, Any]:
    try:
        return await handle_order_paid(
            order_id=body.order_id,
            buyer_id=body.buyer_id,
            item_id=body.item_id,
            chat_id=body.chat_id,
            account_id=body.account_id,
            platform=body.platform,
            quantity=body.quantity,
            idempotency_key=idempotency_key or f"order-paid:{body.order_id}",
        )
    except Exception as exc:
        raise HTTPException(400, str(exc)) from exc


@app.post("/webhooks/xianyu/message")
async def xianyu_message(
    body: BuyerMessageRequest,
    idempotency_key: str = Header(default="", alias="Idempotency-Key"),
) -> dict[str, Any]:
    try:
        return await handle_buyer_message(
            order_id=body.order_id,
            buyer_id=body.buyer_id,
            text=body.text,
            idempotency_key=idempotency_key or f"message:{body.order_id}:{body.text}",
        )
    except Exception as exc:
        raise HTTPException(400, str(exc)) from exc


@app.get("/fulfillments")
def fulfillments(limit: int = 100) -> list[dict[str, Any]]:
    return list_fulfillments(limit=limit)


@app.get("/fulfillments/{order_id}")
def fulfillment(order_id: str) -> dict[str, Any]:
    row = get_fulfillment(order_id)
    if not row:
        raise HTTPException(404, "订单不存在")
    return row


@app.get("/audit")
def audit(limit: int = 100) -> list[dict[str, Any]]:
    return list_audit(limit=limit)
