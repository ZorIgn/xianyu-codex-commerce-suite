# 闲鱼卡密履约中心

这是一个本地一体式卡密/账号库存管理中心，用来配合 `xianyu-auto-reply` 做咨询回复、订单出库、固定语句发货，以及人工一键 Codex 激活。

## 启动

```powershell
cd E:\account\xianyu-codex-fulfillment
python -m pip install -r requirements.txt
python -m uvicorn app.main:app --host 127.0.0.1 --port 8765
```

也可以双击：

```text
E:\account\xianyu-codex-fulfillment\start-backend.bat
```

前端管理后台和后端是同一个服务，打开：

```text
http://127.0.0.1:8765/
```

## 业务流程

1. 在“绑定与模板”里填写闲鱼项目地址、发送接口、Cockpit/aBai 地址、Codex 命令。
2. 在“绑定与模板”里编辑固定发货语句，使用 `{accounts}` 放账号内容，`{count}` 放份数。
3. 在“库存”里粘贴 CPA JSON 导入库存。需要同步到 aBai/Cockpit 时勾选“同步到 Cockpit/aBai”。
4. 买家咨询仍由 `xianyu-auto-reply` 前端处理。
5. 买家拍下付款后，闲鱼项目回调 `/webhooks/xianyu/order-paid`，或者人工在“出库发货”页输入订单号、买家 ID、份数并点击出库。
6. 系统按份数读取本地合格库存，状态改为“已出库待激活”，生成固定发货语句，并调用闲鱼发送接口。
7. 人工确认买家回复“已邀请”后，到“库存”里筛选“已出库待激活”，点击对应库存的“一键激活”。
8. 激活会读取该库存 CPA JSON 中的 `session_token/cookies`，复用 aBai 的 Codex 切号逻辑，然后运行 `codex exec 你好`。

## 合格库存规则

出库前必须满足：

- 状态是 `available`。
- `validity_status != invalid`。
- `lifecycle_status` 不在 `invalid/expired/revoked/disabled/used/consumed`。
- `display_status` 不在 `invalid/expired/revoked/disabled`。
- `token_revoked` 为 false。
- `reset_count <= MAX_RESET_COUNT`，默认 0。
- 至少有邮箱密码，或 token/session/cookies。

## 正式模式

`.env.example` 是模板。正式运行时复制为 `.env`：

```powershell
Copy-Item .env.example .env
```

然后设置：

```env
DRY_RUN=false
XIANYU_BASE_URL=http://127.0.0.1:你的闲鱼项目端口
CODEX_COMMAND=codex
```

`DRY_RUN=true` 时不会真实发送闲鱼消息，也不会真实切换 Codex 账号，适合检查界面和模板。

## 闲鱼项目需要回调的接口

已付款自动发货：

```http
POST http://127.0.0.1:8765/webhooks/xianyu/order-paid
Idempotency-Key: xianyu-order-paid-{order_id}
Content-Type: application/json

{
  "order_id": "闲鱼订单号",
  "buyer_id": "闲鱼会话或买家ID",
  "item_id": "商品ID",
  "quantity": 1,
  "platform": "chatgpt"
}
```

买家消息只做留痕，不自动激活：

```http
POST http://127.0.0.1:8765/webhooks/xianyu/message
Content-Type: application/json

{
  "order_id": "闲鱼订单号",
  "buyer_id": "闲鱼会话或买家ID",
  "text": "已邀请"
}
```

## 闲鱼发送接口适配

默认调用：

```text
{XIANYU_BASE_URL}/api/messages/send
```

请求体：

```json
{
  "buyer_id": "buyer id",
  "order_id": "order id",
  "text": "发货文本"
}
```

如果 `xianyu-auto-reply` 实际接口不同，打开后台“绑定与模板”修改发送消息接口；如果请求体字段不同，改 `app/adapters.py` 的 `XianyuAdapter.send_message`。

## API 速查

- `GET /`：管理前端。
- `POST /inventory/import-cpa`：CPA JSON 导入。
- `GET /inventory`：库存列表。
- `GET /inventory/summary`：库存统计。
- `POST /fulfillments/ship`：人工或上游出库发货。
- `POST /fulfillments/activate-item`：一键激活某个已出库库存。
- `GET /fulfillments/{order_id}`：订单履约详情。
- `GET /audit`：审计日志。
