# 2026-08-06 高并发履约与桌面激活发布说明

## 发布边界

本次整合把闲鱼付款链路接入履约中心的 durable delivery queue，并同步三实例桌面激活、OAuth 批量刷新、数量补齐和消息发送状态回写。代码已经完成自动化验证，但三个真实桌面实例尚未在生产环境并发验证，真实高峰 P95 也尚未压测，不能把它们写成已验证指标。

## 付款与发货链路

闲鱼 websocket 只调用：

~~~http
POST /webhooks/xianyu/order-paid
~~~

请求必须包含 order_id、buyer_id、item_id、chat_id、account_id 和当前已知 quantity。履约中心立即写入 delivery_jobs 并返回，后台 worker 再完成库存原子分配和 delivery_outbox 发送。

outbox 发送调用闲鱼 websocket 的内部接口：

~~~http
POST /internal/accounts/{account_id}/send-message
~~~

请求携带真实 chat_id、buyer_id、order_id 和 account_id。XianyuAdapter 同时检查 HTTP 状态和 JSON 的 success/code；HTTP 200 但 success=false、错误 code 或内部 send_status=failed 都会抛出异常，进入 outbox 重试。

闲鱼 handler 收到“已入队”响应后不再发送 delivery_text。它只记录队列接收结果，真正的消息由履约 worker 发送，避免重复发送。

## fulfillment 状态

- 出库完成、等待内部消息发送：send_pending
- 内部消息成功：account_sent
- 内部消息失败：send_pending；已分配的库存保持不变，只重试发送
- 同订单重复付款事件：按 order_id 幂等，不重复扣库存

## 数量核对

订单详情同步得到更大 quantity 后，闲鱼 websocket 调用：

~~~http
POST /delivery/jobs/{order_id}/reconcile
~~~

履约中心使用 MAX(requested_quantity, quantity) 更新任务；即使订单已经 shipped/account_sent，只要 allocated_quantity 小于目标数量，任务仍会重新排队并只补齐缺少的库存。

## 本地履约中心配置

闲鱼 websocket 的 websocket/.env.example 提供通用占位配置：

~~~env
FULFILLMENT_CENTER_ENABLED=true
FULFILLMENT_CENTER_URL=http://127.0.0.1:8765
FULFILLMENT_CENTER_ITEM_IDS=replace-with-item-id
FULFILLMENT_CENTER_ALL_ITEMS=false
~~~

商品是否接入本地履约中心必须显式配置，不再根据绑定卡数量是否为 1 推断。

## 桌面激活

履约中心支持三个独立桌面实例，每个 worker 固定绑定一个实例。实例需要分别提供 instance_id、codex_home 和 app_user_data_dir；每个 bridge 使用独立目录和 Mutex。

推荐设置：

~~~env
ACTIVATION_WORKER_COUNT=3
DESKTOP_BACKGROUND_MODE=true
DESKTOP_ALLOW_FOREGROUND_FALLBACK=false
~~~

后台模式最小化启动桌面端，优先使用 UI Automation；关闭 fallback 时不使用剪贴板、SendKeys、鼠标移动等抢焦点手段。

## OAuth 批量刷新

oauth_refresh_batches 和 oauth_refresh_jobs 持久化批量授权任务。前端支持选择库存、全选筛选结果、查看进度和失败原因、取消任务、重试失败项。浏览器 OAuth 保持单并发，实时激活前授权优先于提前批量刷新。

## 验证结果

- 原有 24 个自动化测试通过。
- 发布整合后履约中心共 27 个测试通过。
- Python compileall、闲鱼 websocket 关键模块 py_compile、前端 node --check 和 PowerShell bridge/UI 解析均通过。
- 真实三个桌面实例并发尚未验证。
- 真实高峰 P95 尚未压测。
