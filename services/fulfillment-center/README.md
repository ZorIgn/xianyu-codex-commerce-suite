# 闲鱼 Codex 履约中心

本服务负责库存导入、订单幂等出库、持久化发货队列、闲鱼内部消息发送、桌面激活队列和 OAuth 批量刷新。

## 启动

在仓库根目录运行：

~~~powershell
cd services/fulfillment-center
python -m pip install -r requirements.txt
python -m uvicorn app.main:app --host 127.0.0.1 --port 8765
~~~

需要桌面激活时，先按部署环境配置桌面实例池，再运行：

~~~powershell
./start-desktop-bridge.ps1
~~~

## 付款链路

闲鱼 websocket 调用 /webhooks/xianyu/order-paid，并传入 order_id、buyer_id、item_id、chat_id、account_id、quantity。付款接口只入队；worker 负责出库并通过闲鱼内部 /internal/accounts/{account_id}/send-message 发送。

## 关键接口

- POST /webhooks/xianyu/order-paid：付款入队
- GET /delivery/jobs/{order_id}：发货任务状态
- POST /delivery/jobs/{order_id}/reconcile：补齐订单数量
- GET /fulfillments/{order_id}：履约和库存状态
- POST /oauth/refresh-batches：创建批量凭证刷新
- DELETE /oauth/refresh-batches/{batch_id}：取消未执行任务
- POST /oauth/refresh-batches/{batch_id}/retry-failed：重试失败项

## 配置

请复制 .env.example 为 .env，并使用部署机器上的通用占位路径填写 OAuth 和桌面实例配置。不要提交 .env、数据库、日志或任何凭证。

闲鱼 websocket 的商品路由配置位于 services/xianyu-auto-reply/websocket/.env：

~~~env
FULFILLMENT_CENTER_ENABLED=true
FULFILLMENT_CENTER_URL=http://127.0.0.1:8765
FULFILLMENT_CENTER_ITEM_IDS=item-id-1,item-id-2
FULFILLMENT_CENTER_ALL_ITEMS=false
~~~

完整改造说明见 docs/2026-08-06-high-concurrency.md。
