# 闲鱼项目接入履约中心说明

## 你的闲鱼项目在哪里

本地源码目录：

```text
<repo>/services/xianyu-auto-reply
```

主前端目录：

```text
<repo>/services/xianyu-auto-reply\frontend
```

主要服务：

| 服务 | 目录 | 默认端口 | 作用 |
|---|---|---:|---|
| frontend | `frontend` | 9000 | 闲鱼后台前端 |
| backend-web | `backend-web` | 8089 | 管理 API |
| websocket | `websocket` | 8090 | 闲鱼实时连接、聊天、发货 |
| scheduler | `scheduler` | 8091 | 定时拉单、补发货 |

## 我已经补好的接入代码

新增文件：

```text
<repo>/services/xianyu-auto-reply\websocket\app\services\fulfillment_center_client.py
```

已修改：

```text
<repo>/services/xianyu-auto-reply\websocket\app\api\routes\internal.py
<repo>/services/xianyu-auto-reply\websocket\.env.example
```

付款事件通过闲鱼 websocket 的订单处理逻辑进入本地履约中心：

```http
POST /webhooks/xianyu/order-paid
```

请求必须包含 `order_id`、`item_id`、`buyer_id`、真实 `chat_id`、闲鱼 `account_id` 和当前已知 `quantity`。履约中心只负责把事件写入 durable delivery queue；本地 delivery worker 负责库存分配和调用闲鱼内部发送接口，闲鱼 handler 不再重复发送 `delivery_text`。

订单详情同步发现数量增加时，调用：

```http
POST /delivery/jobs/{order_id}/reconcile
```

补齐逻辑不受订单已标记 `shipped` 的限制。

## 闲鱼项目怎么绑定履约中心

编辑：

```text
<repo>/services/xianyu-auto-reply\websocket\.env
```

如果没有 `.env`，从 `.env.example` 复制一份。

加入或修改：

```env
FULFILLMENT_CENTER_ENABLED=true
FULFILLMENT_CENTER_URL=http://127.0.0.1:8765
FULFILLMENT_CENTER_ITEM_IDS=replace-with-item-id
FULFILLMENT_CENTER_ALL_ITEMS=false
FULFILLMENT_CENTER_TIMEOUT=5
```

开启后，闲鱼项目的发货流程会变成：

```text
买家付款
-> websocket POST /webhooks/xianyu/order-paid
-> 履约中心 durable delivery queue
-> delivery worker 按 quantity 分配库存
-> worker 调用闲鱼内部发送接口
-> fulfillment 回写 account_sent / send_pending
-> 订单详情同步后按需 POST /delivery/jobs/{order_id}/reconcile
-> 本地库存变成“已出库待激活”
```

## 履约中心怎么绑定闲鱼发送接口

打开履约中心：

```text
http://127.0.0.1:8765/
```

进入“绑定与模板”，推荐填写：

```text
闲鱼项目地址：http://127.0.0.1:8090
发送消息接口：/internal/accounts/{account_id}/send-message
闲鱼账号 ID：你的闲鱼账号 account_id
```

这里用于你在履约中心后台手动出库时直接调用闲鱼 websocket 发消息。若你只让闲鱼项目自动回传出库，可以不使用这一项。

## 启动顺序

1. 启动履约中心：

```powershell
cd <repo>/services/fulfillment-center
python -m uvicorn app.main:app --host 127.0.0.1 --port 8765
```

2. 启动闲鱼项目后端服务。

在源码目录下分别启动：

```powershell
cd <repo>/services/xianyu-auto-reply\backend-web
python main.py
```

```powershell
cd <repo>/services/xianyu-auto-reply\websocket
python main.py
```

```powershell
cd <repo>/services/xianyu-auto-reply\scheduler
python main.py
```

3. 启动闲鱼前端：

```powershell
cd <repo>/services/xianyu-auto-reply\frontend
npm install
npm run dev -- --host 127.0.0.1 --port 9000
```

打开：

```text
http://127.0.0.1:9000/
```

## 使用步骤

1. 先在履约中心导入真实 CPA JSON。
2. 在闲鱼项目前端登录闲鱼账号并启动 websocket 连接。
3. 在闲鱼项目里保持原来的咨询回复、商品、订单管理流程。
4. 买家拍下并付款后，闲鱼项目调用 `/internal/orders/deliver`。
5. 这个接口会自动回传履约中心扣库存并拿发货语句。
6. 闲鱼项目把发货语句发给买家。
7. 你人工确认买家发来“已邀请”后，去履约中心库存列表筛选“已出库待激活”，点“一键激活”。

## 验证

已执行：

```powershell
python -m py_compile websocket\app\services\fulfillment_center_client.py websocket\app\api\routes\internal.py
python -m py_compile app\db.py app\settings_store.py app\adapters.py app\main.py
```

均通过。
