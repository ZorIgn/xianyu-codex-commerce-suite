# 闲鱼消息与订单子系统

本目录包含 Xianyu Codex Commerce Suite 的闲鱼管理端和订单消息服务。

## 组成

- `frontend`：React 管理端
- `backend-web`：账号、商品、订单、卡券和系统设置 API
- `websocket`：闲鱼实时消息、付款识别和履约中心回传
- `scheduler`：补发、状态同步和定时任务
- `common`：共享配置、数据模型和服务
- `docker-compose.yml`：MySQL、Redis 及容器化服务定义
- `docker-compose.local-infra.yml`：Windows 本地运行使用的 MySQL/Redis 镜像覆盖

## 与履约中心的连接

`websocket/.env` 控制哪些商品接入本地履约中心：

```env
FULFILLMENT_CENTER_ENABLED=true
FULFILLMENT_CENTER_URL=http://127.0.0.1:8765
FULFILLMENT_CENTER_ITEM_IDS=你的商品ID
FULFILLMENT_CENTER_ALL_ITEMS=false
```

付款事件会进入履约中心的持久化发货队列，买家确认消息会进入激活队列。库存内容、状态机、OAuth 和 Codex 激活逻辑位于相邻的 `../fulfillment-center`。

整个项目从仓库根目录运行 `start-all.bat` 启动，不需要在本目录分别启动各服务。
