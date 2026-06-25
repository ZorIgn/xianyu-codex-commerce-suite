# 对接说明

## 1. 启动顺序

1. 启动 aBai/Cockpit 账号管理服务。
2. 启动 `xianyu-auto-reply` 的 backend/websocket/scheduler。
3. 启动本项目：

```powershell
cd E:\account\xianyu-codex-fulfillment
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
  "platform": "chatgpt"
}
```

本项目会：

- 创建履约单。
- 抢占合格库存。
- 生成账号交付文本。
- 调用 `XIANYU_BASE_URL/api/messages/send` 回复买家。

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
XIANYU_BASE_URL=http://127.0.0.1:8080
CODEX_COMMAND=codex
```

如果 `xianyu-auto-reply` 实际发送消息接口不是 `/api/messages/send`，只需要改 `app/adapters.py` 的 `XianyuAdapter.send_message`。

