# 闲鱼自动发货编排项目计划

## 目标

把 `zhinianboke/xianyu-auto-reply`、`aBaiAutoplus_syunnrai` 和 Cockpit 账号管理能力组合成一个本地履约编排层：

- 闲鱼负责监听订单、回复买家、自动发货。
- 本地库存负责筛选可用账号、锁定库存、避免重复消耗。
- Cockpit/aBai 继续作为账号状态来源和批量账号管理入口。
- 买家回复“已邀请”后触发 Codex CLI 激活验证。

## 核心流程

1. 批量导入 CPA JSON 到 `/inventory/import-cpa`。
2. 系统规范化账号字段，并可选同步到 Cockpit/aBai `/accounts/import`。
3. 闲鱼订单已付款 webhook 到 `/webhooks/xianyu/order-paid`。
4. 状态机抢占一个合格库存，生成发货文本，调用闲鱼 adapter 发送给买家。
5. 买家回复“已邀请”后，闲鱼消息 webhook 到 `/webhooks/xianyu/message`。
6. 状态机确认订单已发货，启动一次 `codex` CLI，发送 `hello`，拿到回复后关闭。
7. 系统调用闲鱼 adapter 回复“收到了吗”，并把库存标记为 consumed。
8. 所有动作写入 `audit_events`，所有 webhook/action 都经过幂等保护。

## 合格库存规则

账号必须同时满足：

- 本地库存状态是 `available`。
- `validity_status` 不是 `invalid`。
- `lifecycle_status` 不在 `invalid`、`expired`、`revoked`、`disabled`、`used`。
- `display_status` 不在 `invalid`、`expired`、`revoked`、`disabled`。
- `token_revoked` 为 false。
- `reset_count <= MAX_RESET_COUNT`，默认 `0`。
- 至少有 email/password 或 token/session/cookies 中的一种可交付凭据。

## 状态机

- `created`
- `paid`
- `account_reserved`
- `account_sent`
- `buyer_invited`
- `activating`
- `activated`
- `receipt_asked`
- `completed`
- `failed`

状态只能按允许路径推进，防止重复 webhook 造成跳步、重复发货或重复扣库存。

## 新项目边界

本项目是编排层，不直接侵入上游仓库：

- `XianyuAdapter` 通过 HTTP endpoint 对接上游闲鱼项目。
- `CockpitAdapter` 通过 HTTP endpoint 对接 aBai/Cockpit。
- 上游接口变更时只需要改 adapter。

