<div align="center">

# 🧾 Xianyu Codex Commerce Suite

**闲鱼消息、订单与本地库存履约的一体化工程**

把咨询、付款识别、库存出库、自动发货、买家确认与激活审计串成可回放的履约链路。

最后更新：2026-08-14。

## 更新记录

- 2026-06-26：已经结束的 Codex 邀请重置活动，也记念我当时在闲鱼完成的 300 多单重置。
- 2026-08-03：新出邀请好友送额度活动。与上一轮可以使用 Codex CLI 激活不同，本轮必须通过 ChatGPT 桌面端中的 Codex 发起会话，因此重新设计了桌面激活链路。
- 2026-08-04：最近进货侧以及openai风控提升，频繁掉凭证。但仍不影响反代链路，只是无法登录desktop，对于提供账号密码的凭证支持重拉Oauth刷新凭证。
- 2026-08-05：在闲鱼卖了 50 多单。高峰期出现发货延迟、桌面激活串行等问题，因此增加持久化发货队列、多实例激活和批量凭证更新。给闲鱼这群人售后太消耗精力，遂开源。
- 2026-08-14：在好心群友的技术支持下新增了协议激活方式——不再唤起桌面端发消息，而是把“你好”装包成 WebSocket 帧直接走 Codex 协议发送激活，大大提升并发、减少占用；原有 CLI 与桌面端模式保留，后台可选择三种激活提供方。新方式为实验性功能，暂未经过真实账号测试。

[![React](https://img.shields.io/badge/React-18-61DAFB?logo=react&logoColor=white)](https://react.dev/)
[![TypeScript](https://img.shields.io/badge/TypeScript-5-3178C6?logo=typescript&logoColor=white)](https://www.typescriptlang.org/)
[![FastAPI](https://img.shields.io/badge/FastAPI-fulfillment-009688?logo=fastapi&logoColor=white)](https://fastapi.tiangolo.com/)
[![Docker](https://img.shields.io/badge/Docker-infrastructure-2496ED?logo=docker&logoColor=white)](https://www.docker.com/)
[![SQLite](https://img.shields.io/badge/SQLite-inventory-003B57?logo=sqlite&logoColor=white)](https://www.sqlite.org/)

[核心能力](#-核心能力) · [业务架构](#️-业务架构) · [快速开始](#-快速开始) · [履约流程](#-履约流程) · [安全说明](#-安全说明)

</div>

---

## 📖 项目简介

**Xianyu Codex Commerce Suite** 面向闲鱼虚拟商品交付场景，将闲鱼自动回复/自动发货系统与本地库存履约中心整合为一个可部署仓库。

项目沉淀自真实订单流程：当实时注册无法稳定支撑订单峰值时，主链路改为“CPA JSON 批量导入 + 本地库存状态机 + 闲鱼自动发货”，并通过幂等 Key、审计日志和买家触发词降低重复出库、重复发货和错误激活风险。

> 💡 一句话概括：**前台负责接单和沟通，履约中心负责库存、状态与审计。**

## ✨ 核心能力

- 💬 **闲鱼账号与消息接入** —— 支持在线聊天、咨询分类、商品和订单管理。
- 🤖 **约束式客服回复** —— 使用场景化提示词，限制无关回答、议价承诺和库存幻觉。
- 📦 **自动出库** —— 付款后按真实订单份数从本地库存中心锁定合格账号。
- 🧾 **CPA 批量导入** —— 对账号有效性、token 状态和重置次数进行基础筛选。
- 🔄 **库存状态机** —— 管理未出库、已出库、已激活与激活失败状态。
- ✅ **买家确认触发** —— 完整触发词回传后执行后续激活和状态回写。
- 🛡️ **幂等与审计** —— 防止重复出库、重复发货和重复激活，并保留操作日志。
- 🚨 **低库存预警** —— 库存低于阈值时在管理端提示。
- 📬 **持久化发货队列** —— 付款事件快速入队，由 delivery worker 负责库存分配和闲鱼内部发送。
- 🖥️ **桌面实例池** —— 每个 worker 绑定独立桌面实例，支持后台唤起和跨实例并发；同一实例仍保持串行。
- 🔁 **OAuth 批量刷新** —— 批量任务持久化，支持取消未执行项和重试失败项。

## 🏗️ 业务架构

```mermaid
flowchart LR
    B[买家咨询 / 付款] --> X[闲鱼 WebSocket 服务]
    X --> C[受约束的客服回复]
    X --> O[订单识别]
    O --> F[本地履约中心]
    J[CPA JSON 库存] --> F
    F --> L[幂等锁定与按份出库]
    L --> D[delivery worker 调用闲鱼内部发送]
    D --> T[买家固定触发词]
    T --> A[ChatGPT 桌面端 Codex 激活]
    A --> S[(状态回写 + 审计日志)]
```

### 系统分工

| 子系统 | 职责 |
| --- | --- |
| `xianyu-auto-reply` | 闲鱼账号、聊天、商品、订单、卡券和自动发货 |
| `fulfillment-center` | CPA 导入、库存筛选、durable queue、桌面激活、OAuth 批处理与审计 |
| [`codex-oauth-auto-register`](https://github.com/ZorIgn/codex-oauth-auto-register) | 配套账号导入/注册、OAuth 验证、接码轮询与 CPA 导出 |

## 🛠️ 技术栈

| 领域 | 选型 |
| --- | --- |
| 管理端 | React 18、TypeScript、Vite 5、Zustand、Framer Motion、Recharts |
| 履约 API | Python 3.11+、FastAPI、Pydantic、HTTPX |
| 数据与状态 | SQLite、本地审计日志、幂等 Key |
| 基础设施 | Docker Compose、MySQL、Redis |
| 自动化 | Windows 批处理脚本、PowerShell UI Automation、ChatGPT 桌面端 Codex |

## 🚀 快速开始

### 环境要求

- Windows 10 / 11
- Python 3.11+
- Node.js 18+
- Docker Desktop
- Git
- 可用的 ChatGPT 桌面端 Codex（CLI 仅作为可选回退）

### 1. 配置

```bat
git clone https://github.com/ZorIgn/xianyu-codex-commerce-suite.git
cd xianyu-codex-commerce-suite
copy services\fulfillment-center\.env.example services\fulfillment-center\.env
copy services\xianyu-auto-reply\websocket\.env.example services\xianyu-auto-reply\websocket\.env
```

根据本地环境修改两个 `.env`，真实凭据不要提交到 Git。闲鱼 websocket 侧需要明确配置 `FULFILLMENT_CENTER_ITEM_IDS`，或在确认范围后启用 `FULFILLMENT_CENTER_ALL_ITEMS=true`。

### 2. 安装依赖

```bat
services\xianyu-auto-reply\install-all.bat

cd services\fulfillment-center
python -m venv .venv
.venv\Scripts\pip install -r requirements.txt
cd ..\..
```

### 3. 启动

先启动 Docker Desktop，再运行：

```bat
scripts\start-all.bat
```

| 服务 | 地址 |
| --- | --- |
| 闲鱼管理后台 | <http://127.0.0.1:9000> |
| 本地库存中心 | <http://127.0.0.1:8765> |
| Backend Web | <http://127.0.0.1:8089> |
| WebSocket | <http://127.0.0.1:8090> |
| Scheduler | <http://127.0.0.1:8091> |

## 🔄 履约流程

1. 在管理后台绑定闲鱼账号，并保持 WebSocket 服务在线。
2. 开启自动确认发货与自动发货。
3. 将目标商品唯一绑定到用于交付的卡券。
4. 在库存中心导入 CPA JSON。
5. 买家付款后，闲鱼 websocket 调用 `/webhooks/xianyu/order-paid` 快速入队，delivery worker 再按订单份数原子分配库存。
6. delivery worker 调用闲鱼内部发送接口；成功回写 `account_sent`，失败或等待重试回写 `send_pending`。
7. 订单详情同步发现数量增加时调用 `/delivery/jobs/{order_id}/reconcile`，即使订单已经 `shipped` 也继续补齐；买家完整回复约定触发词后，履约中心执行激活并回写状态。

### 库存筛选

库存中心会筛选基础合格账号：

- 未失效
- token 未 revoked
- 重置次数未超限
- 未被其他订单锁定

### 关键接口

| 方法 | 路径 | 用途 |
| --- | --- | --- |
| `POST` | `/webhooks/xianyu/order-paid` | 付款事件入 durable delivery queue；需携带 `order_id`、`item_id`、`buyer_id`、真实 `chat_id`、`account_id`、`quantity` |
| `POST` | `/delivery/jobs/{order_id}/reconcile` | 订单数量变大后的库存补齐，允许订单已 `shipped` |
| `POST` | `/webhooks/xianyu/message` | 接收买家确认消息并触发流程 |
| `POST` | `/fulfillments/{order_id}/activate` | 管理端手动补救激活 |
| `POST` | `/fulfillments/ship` | 仅保留给管理端人工兼容入口，不是闲鱼付款主链路 |

## 📂 项目结构

```text
services/
├── xianyu-auto-reply/
│   ├── frontend/              React 管理端
│   ├── backend-web/           管理后台 API
│   ├── websocket/             闲鱼 IM、订单与发货主服务
│   ├── scheduler/             定时任务
│   ├── common/                公共模型、数据库与工具
│   └── docker-compose*.yml    MySQL / Redis 等基础设施
└── fulfillment-center/
    ├── app/                   FastAPI、库存、履约与 Codex Runner
    └── tests/                 履约中心测试
scripts/
├── start-all.bat              Windows 一键启动
├── stop-all.bat               停止应用端口
└── stop-infra.bat             停止 Docker 基础设施
```

## 2026-08-06 发布边界

- 原有 24 个自动化测试通过，发布整合后共 27 个测试通过。
- 三个真实桌面实例并发尚未验证。
- 真实高峰 P95 尚未压测。
- 完整高并发说明见 [docs/2026-08-06-high-concurrency.md](docs/2026-08-06-high-concurrency.md)。

## 🛑 停止服务

```bat
scripts\stop-all.bat
scripts\stop-infra.bat
```

## 🛡️ 安全说明

本仓库默认不应提交：

- `.env`、API Key、Cookie、Token
- 数据库、库存文件和账号 JSON
- 日志、虚拟环境和运行缓存
- Docker、Node 和 Python 构建产物

对外部署前还应补充鉴权、权限分级、敏感字段加密、速率限制和审计日志留存策略。本项目包含第三方开源项目的集成与二次开发，使用、分发和商用前请逐项确认上游许可证与目标平台服务条款。

## 🙏 项目来源

- 闲鱼系统基于 [`zhinianboke/xianyu-auto-reply`](https://github.com/zhinianboke/xianyu-auto-reply) 整理改造。
- 本地库存履约中心为本仓库新增服务。
- 账号供给侧工具见 [`ZorIgn/codex-oauth-auto-register`](https://github.com/ZorIgn/codex-oauth-auto-register)。

## ⚠️ 免责声明

本项目用于学习、研究和本地自动化流程复盘。请遵守闲鱼、Codex 及相关第三方服务的条款和当地法律法规，不要用于虚假交易、垃圾消息、滥用账号或未经授权的访问。
