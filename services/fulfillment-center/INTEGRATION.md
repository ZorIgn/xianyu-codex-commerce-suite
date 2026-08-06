# 对接说明

## 1. 启动顺序

1. 启动 aBai/Cockpit 账号管理服务。
2. 启动 `xianyu-auto-reply` 的 backend/websocket/scheduler。
3. 启动本项目：

```powershell
cd <repo>/services/fulfillment-center
python -m uvicorn app.main:app --host 127.0.0.1 --port 8765
```

## 2. CPA 库存导入

```http
POST http://127.0.0.1:8765/inventory/import-cpa
Content-Type: application/json

{
  "sync_cockpit": true,
  "payload": [
    {
      "email": "demo@example.com",
      "password": "password",
      "access_token": "token",
      "session_token": "session",
      "lifecycle_status": "registered",
      "validity_status": "valid",
      "reset_count": 0
    }
  ]
}
```

`sync_cockpit=true` 会额外调用 `COCKPIT_BASE_URL/accounts/import`，使用 aBai 当前支持的 `email password {extra}` 行格式。

## 3. 闲鱼已付款事件

上游闲鱼项目在确认买家拍下/付款后回调：

```http
POST http://127.0.0.1:8765/webhooks/xianyu/order-paid
Idempotency-Key: xianyu-order-paid-{order_id}
Content-Type: application/json

{
  "order_id": "xy_order_10001",
  "buyer_id": "buyer_abc",
  "item_id": "item_123",
  "chat_id": "chat_abc",
  "account_id": "xianyu-account-1",
  "platform": "chatgpt",
  "quantity": 1
}
```

本项目会：

- 把付款事件写入 durable delivery queue。
- 由 delivery worker 原子抢占合格库存。
- 生成账号交付文本并调用闲鱼内部发送接口。
- 将发送状态回写为 `account_sent` 或 `send_pending`。

订单详情同步发现数量增加时，调用 `POST /delivery/jobs/{order_id}/reconcile`；即使订单已标记 `shipped`，也会继续补齐未分配库存。

## 4. 买家“已邀请”消息事件

上游闲鱼项目收到买家聊天消息后回调：

```http
POST http://127.0.0.1:8765/webhooks/xianyu/message
Idempotency-Key: xianyu-message-{message_id}
Content-Type: application/json

{
  "order_id": "xy_order_10001",
  "buyer_id": "buyer_abc",
  "text": "已邀请"
}
```

只有履约状态已经是 `account_sent` 时才会触发 Codex 激活。激活成功后，本项目会把库存标记为 `consumed`，再回复买家“收到了吗”。

## 5. 正式模式

`.env` 中设置：

```env
DRY_RUN=false
COCKPIT_BASE_URL=http://127.0.0.1:8000
XIANYU_BASE_URL=http://127.0.0.1:8090
CODEX_COMMAND=codex
```

闲鱼发送接口由 `XIANYU_SEND_ENDPOINT` 设置控制；HTTP 200 但响应 `success=false` 或错误 `code` 会进入 durable outbox 重试。

