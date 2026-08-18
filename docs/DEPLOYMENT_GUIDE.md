# 🚀 Xianyu Codex Commerce Suite 部署与自动化操作指南

**闲鱼消息、订单、本地库存履约与 Codex 激活的 Windows 本地部署手册**

本指南作为仓库的独立项目文档，按当前启动脚本、环境模板、管理端页面与履约中心实现整理；实际操作以当前代码和本指南中的当前版本边界为准。文档只使用占位符，不记录真实密码、Cookie、Token、库存邮箱、个人账号或本地数据库内容。

[系统组成](#-系统组成) · [环境准备](#-环境准备) · [下载项目](#-下载项目) · [首次启动](#-首次启动) · [首次配置](#-首次配置) · [闲鱼绑定](#-闲鱼绑定) · [商品卡券库存](#-商品卡券库存) · [WebSocket 激活](#-websocket-激活) · [重启维护](#-重启维护) · [踩坑与解决](#-踩坑与解决) · [版本差异](#-旧部署记录与当前版本差异)

---

> 💡 一句话概括：**闲鱼 WebSocket 负责在线接收付款与消息，本地履约中心负责库存锁定、发货队列与激活队列，Codex WebSocket 负责默认激活。**
>
> ⚠️ 这是本地自动化部署指南，不是绕过平台验证或风控的操作说明。只使用自己有权使用的账号与凭据，滑块、人脸或其他验证由账号本人完成，并遵守闲鱼、Codex 及相关服务条款。

## 📌 系统组成

当前 Windows 部署是“本机应用服务 + Docker 基础设施”的混合方式。MySQL 与 Redis 由 Docker Desktop 运行，其余服务由仓库根目录脚本在 Windows 本机启动。

| 模块 | 地址 / 端口 | 运行方式 | 主要职责 |
| --- | --- | --- | --- |
| 闲鱼管理后台 | `http://127.0.0.1:9000` | Node.js / Vite | 账号、商品、订单、自动回复、卡券与系统设置 |
| Backend Web | `http://127.0.0.1:8089` | Python | 管理后台 API；可打开 `/docs` 查看接口文档 |
| 闲鱼 WebSocket | `http://127.0.0.1:8090` | Python | 保持闲鱼账号在线，接收聊天和付款事件，发送内部消息 |
| Scheduler | `http://127.0.0.1:8091` | Python | 定时同步、补发与状态补偿 |
| 本地履约中心 | `http://127.0.0.1:8765` | Python / FastAPI | 多格式账号 JSON 导入导出、库存筛选、按份出库、发货队列、激活队列与审计 |
| MySQL / Redis | `3306` / `6379` | Docker Compose | 订单、账号、队列和共享状态基础设施 |

正常业务链路如下：

```text
买家付款
  -> 闲鱼 WebSocket 收到真实付款事件
  -> 履约中心按 quantity 锁定合格库存
  -> delivery worker 使用真实 chat_id / account_id 发出发货模板
  -> 买家邀请全部邮箱并回复完整确认短语
  -> 激活队列创建任务
  -> Codex WebSocket 预热并执行正式 turn
  -> 结果通知买家，库存与审计状态回写
```

## 🧰 环境准备

### 必装软件

| 项目 | 要求 |
| --- | --- |
| 操作系统 | Windows 10 / 11，建议 64 位 |
| Git | 用于克隆或更新仓库 |
| Python | 3.11 或更高版本，并加入 PATH |
| Node.js | 18 或更高版本，建议使用 LTS |
| Docker Desktop | Engine 必须能正常启动 |
| WSL 2 | Docker Desktop 在 Windows 上运行 Linux 容器时通常需要 |
| 网络代理 | 使用 `ws` 激活时必须有本机真实可用的代理监听地址 |
| 业务账号 | 一个可正常登录且有权使用的闲鱼账号 |

在 PowerShell 中检查基础命令：

```powershell
git --version
python --version
node --version
npm --version
docker version
```

### Docker Desktop 与 WSL 2

如果 Docker Desktop 提示 `Virtualization support not detected`，优先按下面顺序处理：

1. 在任务管理器的“性能 -> CPU”中确认“虚拟化”为“已启用”。
2. 如果未启用，进入 BIOS / UEFI 开启 Intel VT-x / VT-d 或 AMD SVM / AMD-V。
3. 在“启用或关闭 Windows 功能”中启用“适用于 Linux 的 Windows 子系统”和“虚拟机平台”。
4. 以管理员 PowerShell 执行 `wsl --update`；必要时执行 `wsl --set-default-version 2`。
5. 完整重启 Windows，再等待 Docker Desktop 显示 `Engine running`。

Docker Desktop 登录账号不是运行公开镜像的必要条件；本项目真正依赖的是 Docker Engine 已启动、MySQL 与 Redis 能通过健康检查。

### 🔐 安全准备

- `.env`、Cookie、Token、CPA JSON、数据库、日志和库存邮箱只保存在部署主机，不提交 GitHub。
- 文档、截图、工单和聊天记录中只使用脱敏后的订单号、商品 ID 和错误信息。
- 管理后台首次登录后立即设置个人密码，并使用密码管理器保存。
- 只导入自己有权使用的账号和凭据，遇到平台验证由本人完成。

## 📥 下载项目

### 推荐方式：Git 克隆

```powershell
git clone https://github.com/ZorIgn/xianyu-codex-commerce-suite.git
cd xianyu-codex-commerce-suite
```

### 备用方式：下载 ZIP

在 GitHub 页面选择 `Code -> Download ZIP`，完整解压到固定目录后再运行。不要直接在压缩包内双击脚本；路径尽量简短，也不要放在会自动同步的云盘目录中。

下载完成后，根目录至少应看到：

```text
xianyu-codex-commerce-suite/
├── start-all.bat
├── stop-all.bat
├── stop-infra.bat
├── scripts/
└── services/
    ├── xianyu-auto-reply/
    └── fulfillment-center/
```

> ℹ️ 当前仓库没有旧部署记录中提到的“启动闲鱼系统.bat”。当前实际入口是根目录的 `start-all.bat`，后文均以它为准。

## 🚀 首次启动

### 1. 运行 `start-all.bat`

从仓库根目录打开 PowerShell：

```powershell
cd E:\account\xianyu-codex-commerce-suite
.\start-all.bat
```

如果只想检查命令与脚本，不安装依赖或启动服务，可以使用：

```powershell
.\start-all.bat -CheckOnly
```

第一次启动不要关闭窗口。根脚本会调用 `scripts\start-suite.ps1`，实际执行以下步骤：

1. 检查 `python.exe`、`docker.exe` 和 `npm.cmd`。
2. 仅在目标配置不存在时，从 `.env.example` 创建本地 `.env`。
3. 创建或复用闲鱼服务虚拟环境 `.venv-xianyu`。
4. 创建或复用履约中心虚拟环境 `.venv`。
5. 按依赖文件指纹安装 Python 与前端依赖。
6. 将 Playwright Chromium 安装到仓库内的 `services\xianyu-auto-reply\.playwright` 缓存目录。
7. 启动 Docker Desktop，等待 Docker Engine 可用。
8. 使用 `docker-compose.yml` 与 `docker-compose.local-infra.yml` 启动并等待 MySQL、Redis 健康。
9. 按健康检查启动 `8765`、`8089`、`8090`、`8091` 和 `9000` 五个应用入口。
10. 将启动进程写入 `run-state\processes.json`，日志写入 `run-logs`。

当前脚本只负责打印入口地址，不保证自动打开浏览器；启动完成后请手动打开管理后台和库存中心。

### 2. 首次启动会创建哪些配置

当前脚本会在缺失时创建以下文件：

| 配置文件 | 用途 |
| --- | --- |
| `services/fulfillment-center/.env` | 本地 SQLite、履约、代理与激活配置 |
| `services/xianyu-auto-reply/backend-web/.env` | 管理后台 API 与 MySQL / Redis 配置 |
| `services/xianyu-auto-reply/websocket/.env` | 闲鱼实时服务与本地履约商品范围 |
| `services/xianyu-auto-reply/scheduler/.env` | 定时任务与共享基础设施配置 |

首次生成后只在本机编辑这些 `.env`。不要把其中的密码、Cookie、Token 或 OAuth 字段复制到文档、截图或提交记录。

`services/xianyu-auto-reply/websocket/.env` 还包含订单金额同步的有限重试设置。默认值适合本地小规模部署，不会无限重试：

| 变量 | 默认值 | 作用 |
| --- | ---: | --- |
| `AUTO_DELIVERY_PAYMENT_MAX_ATTEMPTS` | `4` | 金额或付款状态尚未同步时的最大检查次数 |
| `AUTO_DELIVERY_PAYMENT_RETRY_BASE_SECONDS` | `1` | 第一次延迟重试的秒数 |
| `AUTO_DELIVERY_PAYMENT_RETRY_MAX_SECONDS` | `8` | 指数退避的单次最大等待秒数 |

程序还会把误填的超大值限制为最多 16 次、单次等待最多 60 秒。重试详情写入订单 metadata，并包含 `attempt`、`max`、`next_retry` 和结构化原因。

### 3. 启动成功后的地址

| 用途 | 地址 |
| --- | --- |
| 闲鱼管理后台 | <http://127.0.0.1:9000> |
| 本地库存 / 履约中心 | <http://127.0.0.1:8765> |
| Backend Web 接口文档 | <http://127.0.0.1:8089/docs> |
| WebSocket 健康检查 | <http://127.0.0.1:8090/health> |
| Scheduler 健康检查 | <http://127.0.0.1:8091/health> |
| 履约中心健康检查 | <http://127.0.0.1:8765/health> |
| Backend Web 健康检查 | <http://127.0.0.1:8089/api/v1/health/ping> |

### 4. 如果网页拒绝连接

`ERR_CONNECTION_REFUSED` 表示对应端口没有服务监听，先按下面顺序排查：

1. 确认 Docker Desktop 显示 `Engine running`。
2. 确认命令是在仓库根目录执行的。
3. 查看 `run-logs` 中对应服务的 `.out.log` 与 `.err.log`。
4. 检查端口是否被占用：

   ```powershell
   Get-NetTCPConnection -State Listen |
     Where-Object LocalPort -in 9000,8765,8089,8090,8091
   ```

5. 确认不会重复发货后，先执行 `stop-all.bat`，再执行 `start-all.bat`。

如果 `8765` 显示没有样式的原始 HTML、库存突然变成 `0` 或数据像是另一套环境，通常是错误工作目录启动了另一份服务，或旧进程仍在占用端口。停止旧进程后，只从当前仓库根目录重新启动。

## 🔐 首次配置

### 管理后台登录

1. 打开 <http://127.0.0.1:9000>。
2. 新安装没有需要写进文档的默认密码；在部署机器本机的登录页面进入“首次设置管理员密码”。
3. 在本机页面完成首次设置后，使用新密码登录，并在个人设置中确认密码管理方式。
4. 管理后台密码只用于本地管理端，不等于 Docker 账号，也不等于闲鱼账号。

如果首次设置页面无法从远程浏览器调用，请登录部署主机，在仓库根目录运行 `setup-admin-password.bat`。该脚本同样使用交互式输入，不会把密码放进命令参数或日志。

已有锁定管理员不要继续猜测，也不要使用手写 HTTP 请求绕过页面流程。请在部署机器上从仓库根目录运行包装脚本；它会进入本地交互式 `reset` / `unlock` 流程，提示输入新密码并解除登录锁定：

```powershell
.\reset-admin-password.bat
```

包装脚本会调用 `services/xianyu-auto-reply/backend-web/app/admin_password.py` 的本地交互式实现。密码由交互式提示读取，不放入命令参数、脚本文件、日志或本指南。

密码问题只按以下规则处理：

| 场景 | 处理方式 |
| --- | --- |
| 首次设置 | 只在部署机器本机登录页完成首次设置，保存到密码管理器 |
| 连续失败锁定 | 不要继续猜测，等待或确认已触发本机锁定 |
| 本机解锁 / 重置 | 从仓库根目录运行 `reset-admin-password.bat`，交互式重置密码并解除锁定 |

本指南不记录任何初始化用户名、默认密码、真实密码或重置凭据，也不提供手写 HTTP 请求。

### 本地履约连接配置

履约中心打开 <http://127.0.0.1:8765> 后，当前页面的设置区域标题为“绑定与固定发货语句”。至少确认下面几项：

| 设置 | 当前部署填写内容 |
| --- | --- |
| 闲鱼项目地址 | `http://127.0.0.1:8090` |
| 发送消息接口 | `/internal/accounts/{account_id}/send-message` |
| 闲鱼账号 ID | 填写“账号管理”中显示的实际账号 ID |
| 闲鱼 API Token | 只有启用了接口鉴权时才填写，真实值只保留在本机 |
| 激活提供方 | 默认选择 `ws`，失败时可切换 `desktop` 或 `cli` |
| WS 代理地址 | 填写本机真实可用的 HTTP 代理监听地址，不要照抄不存在的端口 |

WebSocket 相关的模型、originator、客户端版本、service tier、reasoning effort、installation id、工具声明、重连次数和超时时间，可以先保留与当前 `.env.example` 兼容的配置；只有在实际环境需要时再调整。

## 👤 闲鱼绑定

### 推荐：扫码登录

在管理后台左侧进入“账号管理”：

1. 点击“添加新账号”。
2. 选择“扫码登录”。
3. 使用手机闲鱼扫码并确认。
4. 如果出现滑块、人脸或其他风控验证，由账号本人在当前设备和网络完成。
5. 返回账号列表并刷新。
6. 确认账号为“启用”，在线状态为绿色“在线”。

当前账号管理页面也保留密码登录、手动 Cookie 等兼容方式。Cookie 属于敏感凭据，不能外泄；扫码登录更容易保持账号、设备和验证链路一致。

### 绑定后的核对

| 检查项 | 期望结果 |
| --- | --- |
| 账号 ID | 已出现，并且与履约中心填写的 ID 一致 |
| 启用状态 | `启用` |
| 在线状态 | `在线` |
| WebSocket | `8090/health` 正常，服务日志无持续断线 |
| 消息链路 | 手机闲鱼收到的消息能出现在在线聊天或消息日志 |

如果账号显示在线，但 Scheduler 日志每分钟出现 `PERMISSION_EXCEPTION`，这通常表示当前闲鱼账号没有订单列表接口权限，不一定代表 Cookie 失效。实时 WebSocket 付款事件仍可能正常，但定时补拉漏单的能力会受影响，因此必须保持 WebSocket 在线并持续监控日志。

## 📦 商品、卡券与库存

### 1. 导入与管理账号 JSON 库存

在 <http://127.0.0.1:8765> 左侧进入“库存”，使用“账号 JSON 导入”。系统会自动识别 CPA、Sub2API、Cockpit Tools、`auth.json` 和常见账号 JSON，当前支持：

- 将单个或多个 JSON 对象粘贴到文本框。
- 选择多个 JSON 文件批量导入。
- 选择一个包含 JSON 文件的目录批量导入。
- 勾选库存后批量导出为 Cockpit Tools、Sub2API 或 CPA 格式。
- 勾选库存后批量删除；正在执行激活任务的库存会被跳过并明确列入阻止结果。

导入后检查顶部的“合格库存”数量，并抽查邮箱、状态、有效性和 OAuth 字段。基础合格条件包括：

| 条件 | 说明 |
| --- | --- |
| 未过期 | 账号仍在有效期内 |
| Token 未撤销 | 不能处于 `revoked` 状态 |
| 重置次数未超限 | 不超过当前履约设置的上限 |
| 未被其他订单锁定 | 不能已经被其他履约记录占用 |
| 有可用账号标识 | 后续 WebSocket 激活需要可靠的 `account_id` |

不同来源的账号 JSON 字段可能不同。显示 `unknown` 或 `not_available` 的记录，可以尝试从 `access_token` claims 补出 `account_id` 和 expiry，再重新导入或更新并复核。claims 只能用于兼容提取，不能替代凭据有效性判断；一旦明确为 `expired`、`revoked` 或 `invalid`，或者最终仍无法推导 `account_id`，都不能正式激活。手动出库只会改变库存状态，不会凭空补齐缺失字段；正式使用前先用一条库存做端到端测试。

不要直接删除已出库记录。它们关联订单、买家、激活和审计；确实需要测试数据清理时，先备份并确认不会造成同一账号重复发给不同买家。

### 2. 上架并同步闲鱼商品

推荐先用手机闲鱼发布商品，让官方 App 处理分类、风控验证和页面变化：

1. 在手机闲鱼发布新商品。
2. 填写真实的标题、描述、价格、分类、服务区域和交付周期。
3. 不要承诺无法保证的额度、成功率或退款条件，也不要公开库存邮箱、Token 或内部接口。
4. 回到管理后台进入“商品管理”。
5. 选择正确闲鱼账号，点击“获取所有账号商品”或“获取商品”。
6. 刷新列表，确认商品 ID 已保存，并记录该 ID 供履约范围配置使用。

管理后台也支持“商品发布 -> 单品发布”。该路径依赖 Playwright，若出现 `BrowserType.launch: Executable doesn't exist` 或找不到 `chromium_headless_shell`，优先从根目录重新运行 `start-all.bat`，让仓库统一准备 Chromium。不要混用系统 Python、不同虚拟环境和不同 Playwright 缓存目录。

后台发布成功后再由手机下架，只能证明发布自动化成功；下架不会自动删除后台已经抓取的商品记录，最终状态以闲鱼前台为准。

### 3. 创建履约卡券

在管理后台进入“卡券管理”：

1. 点击“新建卡券”。
2. 名称使用能区分业务的本地履约名称。
3. 卡券类型选择“固定文字”。当前表单的内部类型为 `text`，必须填写非空的固定文字内容。
4. 固定文字只写简短占位提示即可；真正按库存生成的账号内容来自 `8765` 的发货模板。
5. 保存，并确认卡券为“启用”。

当前卡券表单还支持批量数据、API 接口和图片类型。非图片类型如果填写备注，备注必须包含 `{DELIVERY_CONTENT}` 变量；不需要额外备注时可以留空，避免影响固定履约模板。

卡券的作用是把闲鱼商品纳入既有的商品发货配置和管理关系，不是把 CPA JSON 库存粘贴到卡券内容里。

### 4. 关联商品并配置履约商品范围

在卡券列表对应行点击“关联商品”：

1. 在“待选商品”中勾选需要自动发货的商品。
2. 确认商品出现在“已选商品”。
3. 点击保存，并确认关联保存成功。
4. 对每个新上架商品重复操作。

当前仓库还要求单独维护 WebSocket 的本地履约范围。编辑 `services/xianyu-auto-reply/websocket/.env` 时只使用自己的真实商品 ID：

```env
FULFILLMENT_CENTER_ENABLED=true
FULFILLMENT_CENTER_URL=http://127.0.0.1:8765
FULFILLMENT_CENTER_ITEM_IDS=<item-id-1>,<item-id-2>
FULFILLMENT_CENTER_ALL_ITEMS=false
```

如果明确要让所有商品进入本地履约范围，才将 `FULFILLMENT_CENTER_ALL_ITEMS` 设为 `true`；测试和正式环境都应先确认范围，避免误接管不应自动发货的商品。

> ⚠️ 当前代码把“卡券关联”与“履约商品白名单”分开处理。卡券关联保存不会自动改写 `FULFILLMENT_CENTER_ITEM_IDS`，WebSocket 进程也不会持续监视 `.env` 文件。编辑白名单后必须运行 `stop-all.bat` 再运行 `start-all.bat`，让进程重新加载配置。旧部署记录中“保存关联后自动追加名单、无需重启”的描述不适用于当前版本，详见 [旧部署记录与当前版本差异](#-旧部署记录与当前版本差异)。

### 5. 打开商品自动化开关

确认以下开关和配置：

- “账号管理”中目标账号为启用且在线。
- 目标商品属于正确闲鱼账号。
- 商品已同步到“商品管理”。
- 商品已关联启用卡券。
- `websocket/.env` 中商品 ID 已进入本地履约白名单，或明确启用了全商品模式。
- 目标账号的“自动确认发货”已按业务需要启用。
- 商品的默认回复或 AI 提示词按需配置。

“咨询自动回复”和“付款后的履约发货”是两套逻辑：普通咨询由默认回复、关键词或 AI 规则处理；付款后发邮箱和后续激活由履约中心模板与队列处理。只配置其中一套不能代替另一套。

## 🔌 WebSocket 激活

### 1. 选择激活提供方

在 <http://127.0.0.1:8765> 的“绑定与固定发货语句”中选择“激活提供方”：

| 提供方 | 行为 | 适用场景 |
| --- | --- | --- |
| `ws` | 默认模式，使用 Codex 两阶段 WebSocket 会话，不拉起桌面窗口 | 当前推荐；需要真实可用的 WS 代理和完整 OAuth 字段 |
| `desktop` | 使用绑定的 ChatGPT / Codex 桌面实例 | WS 链路异常或需要可视化兼容时回退 |
| `cli` | 使用 Codex CLI | 兼容旧流程或命令行环境 |

`ws` 模式会先发送预热帧，再携带 `previous_response_id` 建立正式 turn；它依赖库存中的可用 `access_token` 和可靠的 `account_id`。它不通过普通 HTTP 发送激活消息，不需要为每条任务拉起桌面窗口。

### 2. WebSocket 配置要点

至少确认：

| 配置项 | 要求 |
| --- | --- |
| Codex 后端地址 | 使用当前部署兼容的 Codex WebSocket 地址 |
| WS 代理地址 | 必须是本机真实可连接的代理监听地址 |
| 模型与客户端版本 | 与当前可用配置匹配，避免随意改动协议标识 |
| originator / service tier / reasoning effort | 与当前桌面协议兼容 |
| installation id | 可留空让系统生成并持久化，或使用本机已有配置 |
| Tools JSON / OpenAI-Beta | 没有明确需求时保持兼容默认值 |
| WS 重连次数 | 断线后允许有限重连，避免无限重试 |
| 连接与 Turn 超时 | 按代理、网络和账号响应情况设置 |

不要把代理认证信息、OAuth Token、Cookie 或账号密码写进本指南、共享配置或公开仓库。保存配置后在库存中心查看 Worker 状态，确认显示“激活 Worker 运行中”。

### 3. Worker 数量

Worker 表示同时处理后台任务的数量，不是库存数量。新安装的默认值已经按小规模部署设为 1；只有在队列稳定增长且接口、代理、库存和激活方都能承受时才逐步增加：

| Worker | 小规模建议 | 当前新安装默认值 |
| --- | --- | --- |
| 激活 Worker | `1` | `1` |
| 发货 Worker | `1` | `1`；稳定后可谨慎增加到 `2` 或更高 |

持续排队且接口、代理、库存和激活方都稳定时，再逐步增加并发。并发过高会放大资源占用、账号风控和重复操作风险。

### 4. 发货模板与触发词

在库存中心的发货模板中保留 `{accounts}` 占位符。推荐模板结构如下，具体业务文案可在本机调整：

```text
请将下面的邮箱逐个复制到 Codex 的邀请界面，并发送邀请：

{accounts}

全部邮箱邀请完成后，请确认邮箱和数量无误，然后复制下面整句话回复我：

全部邮箱无误 已邀请

请不要只回复“已邀请”，否则系统不会开始激活。

进入队列后请稍等，激活完成后系统会自动通知您。
```

`{accounts}` 必须保留，系统会按订单购买数量替换为实际库存邮箱。触发识别对空格有兼容，但买家说明仍应要求完整回复“全部邮箱无误 已邀请”，不要只要求“已邀请”。

### 5. 从付款到激活的完整链路

1. 买家完成付款，不能只是拍下待付款。
2. 闲鱼 WebSocket 以真实 `order_id`、`item_id`、`buyer_id`、`chat_id`、`account_id` 和 `quantity` 调用履约中心的 `/webhooks/xianyu/order-paid`。
3. 履约中心把事件写入持久化发货队列，delivery worker 按 `quantity` 原子锁定库存。
4. 发送消息使用真实会话上下文；发送失败应进入可追踪的 `send_pending` 或失败状态，不要只看“库存已出库”。
5. 买家邀请全部邮箱并完整回复触发词后，履约中心创建激活批次和任务。
6. 激活 Worker 使用所选提供方执行激活；`ws` 模式通过 WebSocket 会话完成预热与正式 turn。
7. 成功或失败均回写库存、履约和审计状态，并向买家发送结果通知。

多数量订单中，`quantity=N` 应锁定 N 条不同库存、一次展开 N 个邮箱，并创建 N 个激活任务。如果订单详情稍后同步出更大的数量，系统支持通过 `/delivery/jobs/{order_id}/reconcile` 补齐；正式使用前仍要实际测试购买 2 份。

## 🧪 第一次端到端验收

不要直接让陌生买家测试。先准备一个低价测试商品、至少两条合格库存和另一个可配合的闲鱼买家账号。

### 测试前检查

- Docker Engine、MySQL 与 Redis 健康。
- `9000`、`8765`、`8089`、`8090`、`8091` 可访问。
- 闲鱼账号为启用且在线。
- 商品已同步、已关联启用卡券，并已进入 `websocket/.env` 的履约范围。
- 合格库存数量大于测试购买数量。
- 发货模板包含 `{accounts}`。
- 履约中心中的账号 ID、发送接口和 WS 代理正确。
- 激活 Worker 运行中。

### 单份测试

1. 买家付款。
2. 在 `8765` 的出库发货或最近履约中确认出现真实订单号。
3. 确认库存从未出库变为已出库待激活。
4. 在买家端确认收到文字模板和一条邮箱。
5. 买家完成邀请后完整回复“全部邮箱无误 已邀请”。
6. 在激活队列确认出现批次和任务。
7. 等待状态变为已激活，或记录失败原因并按排障顺序处理。
8. 确认买家收到最终结果通知。

### 多份测试

购买 2 份时确认：

| 检查项 | 期望结果 |
| --- | --- |
| 订单 | 只有一张真实订单，数量为 `2` |
| 库存 | 锁定两条不同的合格库存 |
| 发货 | 买家一次收到两个邮箱 |
| 激活 | 激活队列出现两个任务 |
| 幂等 | 没有重复发送、少发或重复扣库存 |

以下场景不应触发本地履约发货：只有咨询、只拍下未付款、已退款、已关闭、真实金额为 0、商品未关联启用卡券或商品不在履约范围。退款订单不要直接人工补发，先确认订单和日志状态。

## 🔁 重启维护

### 每天开始营业

```text
1. 启动电脑并连接稳定网络
2. 打开 Docker Desktop，等待 Engine running
3. 在仓库根目录运行 .\start-all.bat
4. 打开 9000 与 8765，检查账号、库存和 Worker
5. 确认无异常 pending / processing / send_pending / 激活任务
6. 再上架或恢复正式商品
```

### 停止应用

```powershell
.\stop-all.bat
```

`stop-all.bat` 会停止应用服务并保留 MySQL、Redis 容器。需要同时停止基础设施时运行：

```powershell
.\stop-infra.bat
```

当前 `stop-infra.bat` 使用 Docker Compose 停止 MySQL 与 Redis，不是删除容器或数据卷；重新营业前仍需确认 Docker Engine 与容器健康。

### 修改配置后的完整重启

修改任意 `.env`、尤其是 WebSocket 商品白名单、代理或服务间地址后，使用完整重启让进程重新加载配置：

```powershell
.\stop-all.bat
.\start-all.bat
```

不要在业务订单仍处于 `processing`、`send_pending` 或激活中的时候随意重启。先暂停或下架商品，记录订单和任务状态，再决定是否等待、重试或人工接管。

### 日志、状态与备份

| 路径 / 对象 | 作用 |
| --- | --- |
| `run-logs/` | 各服务启动、标准输出和错误日志 |
| `run-state/processes.json` | 一键启动的进程信息，停止脚本会使用它 |
| `services/fulfillment-center/data/` | 履约中心 SQLite 与本地数据目录，实际路径以 `.env` 为准 |
| MySQL 数据卷或导出文件 | 账号、订单、商品、卡券与系统配置 |
| 本地 `.env` | 代理、服务地址和凭据配置，应加密保存 |

上线前至少备份：各服务 `.env`、履约中心数据库、MySQL 数据、库存 JSON、商品与卡券关联、发货模板、未完成订单和审计记录。备份不要上传到公开网盘或 GitHub。

### 更新 GitHub 代码

1. 暂停或下架正式商品，避免更新期间产生新订单。
2. 运行 `stop-all.bat`。
3. 备份 `.env`、SQLite、MySQL、库存 JSON 和业务配置。
4. 使用 `git status` 确认本地修改。
5. 使用 `git pull` 获取更新，并人工合并本地兼容调整；不要用破坏性 `reset` 覆盖本地数据或配置。
6. 重新运行 `start-all.bat`，允许脚本更新依赖和 Playwright 浏览器。
7. 检查五个应用端口、MySQL、Redis、账号在线状态和履约范围。
8. 用测试商品完成一笔单份和一笔多份订单。
9. 单份、多份、退款和断线恢复均验收通过后，再恢复正式商品。

Windows 主机营业期间不要自动睡眠。屏幕可以单独熄灭，但要保证电源、散热、网络、Docker 和五个应用服务持续在线。

## 🩺 踩坑与解决

下面整理部署过程中确认过的现象，并补充当前版本的处理方式。

| 现象 | 原因 | Solution / 当前处理 |
| --- | --- | --- |
| Docker 提示未检测到虚拟化 | BIOS 虚拟化或 WSL 2 未启用 | 开启 VT/SVM、WSL 和虚拟机平台，重启 Windows；单纯登录或升级 Docker 不是根因修复 |
| Docker 更新后仍无法启动 | 环境能力没有变化 | 先修虚拟化和 WSL，再确认 Docker Engine 状态 |
| 管理后台密码失效或被锁定 | 首次密码已改，连续失败触发本机锁定 | 按“首次设置、连续失败锁定、本机解锁/重置”处理，不记录真实密码 |
| 闲鱼登录滑块反复失败 | 平台风控或设备验证 | 由账号本人完成验证，尽量保持同一设备和网络，不尝试绕过验证 |
| `ERR_CONNECTION_REFUSED` | 服务未启动或端口被占用 | 查看 `run-logs`、检查端口，确认无重复履约后 `stop-all.bat` 再 `start-all.bat` |
| `8765` 页面无样式、库存变为 0 | 错误工作目录或启动了另一份服务 | 停止旧进程，只从当前仓库根目录启动 |
| Playwright 报浏览器不存在 | Chromium 未下载或缓存路径与运行时不一致 | 用根目录 `start-all.bat` 统一安装，不要混用系统 Python、项目虚拟环境和缓存目录 |
| 商品已在闲鱼发布，后台看不到 | 商品列表尚未同步 | 在“商品管理”选择账号，点击“获取商品”或“获取所有账号商品”并刷新 |
| 商品已关联卡券但付款不自动发货 | 商品不在 WebSocket 本地履约白名单，或卡券未启用 | 同时确认卡券关联、启用状态和 `FULFILLMENT_CENTER_ITEM_IDS`；修改 `.env` 后完整重启 |
| 重新保存旧关联仍不生效 | 旧部署记录预期的自动追加名单行为在当前版本中不存在 | 手动核对并追加商品 ID，确认 `FULFILLMENT_CENTER_ALL_ITEMS` 未误设，再重启 WebSocket |
| 金额同步重试期间重启了 WebSocket 服务 | 重试次数、下次时间和原因仍保存在订单 metadata 中，但短退避任务不会在启动时自动重新挂载 | 等待下一次付款事件或从订单发货入口再次触发检查；系统会沿用已记录的有限重试次数，不会重新从零开始或无限重试 |
| 库存显示 `unknown` / `not_available` | CPA 字段不完整或缺少可用 `account_id` | 使用完整 CPA 格式或补充 OAuth；不能可靠补齐的记录不要直接用于自动激活 |
| 手动出库后出现 `manual-shipped-*` | 使用了人工兼容入口 | 手动入口只用于确认后的补救；真实付款主链路应来自 WebSocket 付款事件 |
| 库存已出库但买家没收到 | 发送失败、会话上下文不完整或先写了出库状态 | 以买家端实际收到为准，检查 `chat_id`、`account_id`、发送日志和 `send_pending`，避免重复补发 |
| 买家只回复“已邀请”但没有激活 | 触发词过短或自动回复混入额外文字 | 要求完整回复“全部邮箱无误 已邀请”；系统兼容空格，但不建议依赖短表达 |
| 激活队列出现但任务失败 | 缺 `account_id`、OAuth 失效、代理不可用或激活方异常 | 查看失败原因，补完整字段、更新凭据、检查代理；必要时切换 `desktop` / `cli` 对比定位 |
| 默认回复只发图片不发文字 | 图片规则与文字规则分别匹配 | 分别配置图片和文字，检查关键词、优先级和会话去重 |
| 同一句咨询被反复回复 | 默认规则匹配所有消息且没有单次限制 | 使用会话级单次触发或去重，不要用全匹配关键词无限回复 |
| 多买几份却只发一份 | 付款事件和订单详情的数量到达时间不同 | 确认 `quantity`、数量重试与 `reconcile`，必须完成 2 份验收 |
| 订单金额暂时为 0 | 付款事件先到，订单详情或金额稍后同步，形成数据竞态 | 允许有限次数刷新订单详情；明确 0 元、退款和关闭订单一律不发货 |
| Scheduler 持续出现 `PERMISSION_EXCEPTION` | 当前账号没有订单列表接口权限 | 这是已知限制；保持实时 WebSocket 在线，并监控漏单风险 |
| 小规模却运行多个高并发 Worker | 额外并发会放大资源占用、风控和重复操作风险 | 新安装激活 / 发货默认均为 1；只有排队稳定增长后再逐步增加 |
| 电脑关机后无法自动发货 | 全部服务部署在本机 | 关机前暂停或下架商品，或迁移到可靠的常开主机 |

## ✅ 最终验收清单

### 环境

- [ ] Docker Engine 正常，MySQL 与 Redis 健康。
- [ ] `9000`、`8765`、`8089`、`8090`、`8091` 全部可访问。
- [ ] 根目录 `start-all.bat`、`stop-all.bat` 和 `stop-infra.bat` 可用。
- [ ] Windows 不会在营业时间自动睡眠。

### 账号与配置

- [ ] 管理员密码已经首次设置并安全保存。
- [ ] 闲鱼账号已绑定、启用并在线。
- [ ] 履约中心的闲鱼账号 ID 与在线账号一致。
- [ ] `ws` 代理地址真实可用，或已验证 `desktop` / `cli` 回退方式。
- [ ] 没有把 `.env`、Cookie、Token、库存邮箱或账号密码提交到 Git。

### 商品、卡券与库存

- [ ] 账号 JSON 已导入，合格库存数量足够；需要迁移时已验证目标导出格式。
- [ ] 正式库存没有无法解释的 `unknown`、`not_available` 或缺失账号标识。
- [ ] 每个正式商品已同步到商品管理。
- [ ] 每个正式商品已关联同一启用的本地履约卡券。
- [ ] `FULFILLMENT_CENTER_ITEM_IDS` 或 `FULFILLMENT_CENTER_ALL_ITEMS` 范围已人工核对。
- [ ] 发货模板保留 `{accounts}`。

### 发货与激活

- [ ] 单份付款可以自动发一条库存并进入激活队列。
- [ ] 两份付款可以锁定两条不同库存并创建两个激活任务。
- [ ] 未付款、退款、关闭和真实 0 元订单不会发货。
- [ ] 买家完整回复“全部邮箱无误 已邀请”后才会触发激活。
- [ ] 激活成功和失败均有可追踪状态与通知。
- [ ] 默认回复不会在同一会话无限重复。
- [ ] 已验证一次停应用、重启应用和停止基础设施后的恢复流程。

## 🔎 旧部署记录与当前版本差异

以下差异按当前仓库文件核对整理；后续更新代码后应重新确认：

| 旧部署记录中的描述 | 当前仓库实际情况 | 当前版本处理 |
| --- | --- | --- |
| 旧记录以“启动闲鱼系统.bat”为入口 | 当前根目录实际文件是 `start-all.bat`，没有该名称的脚本 | 统一使用 `start-all.bat` |
| 旧记录称首次启动会自动打开管理后台和库存中心 | `scripts/start-suite.ps1` 当前负责启动、健康检查和打印地址，不保证自动打开浏览器 | 启动完成后按输出地址手动打开 `9000` 与 `8765` |
| 旧记录称保存卡券关联后自动追加 `FULFILLMENT_CENTER_ITEM_IDS`，无需重启 | 当前 `fulfillment_center_client.py` 按进程环境中的白名单判断，卡券关联服务没有改写 WebSocket `.env` 的逻辑，文件也不会被持续重读 | 卡券关联与白名单都要配置；改 `.env` 后执行 `stop-all.bat` + `start-all.bat` |
| 旧记录称 WebSocket 会动态重读履约商品名单 | 当前实现只在进程内加载本地 `.env`，`is_item_enabled` 不等于持续监视文件 | 把重启作为配置生效步骤，不依赖热重载 |
| 旧记录建议小规模激活 Worker 为 1、发货 Worker 为 1 到 2 | 当前新安装的 `fulfillment-center/.env.example` 与配置回退值均为激活 1、发货 1 | 默认值与小规模起步边界一致；稳定后再逐步增加发货并发 |
| 旧记录将设置页称为“绑定与模板” | 当前库存中心导航仍显示“绑定与模板”，设置区域内容标题为“绑定与固定发货语句” | 按导航进入设置区，再按内容标题和字段操作 |
| 旧记录将停止基础设施视为“完全停止” | 当前 `stop-infra.bat` 执行 Docker Compose `stop`，停止 MySQL / Redis 但不删除数据卷 | 可用于关机前停止容器；恢复时重新启动并做健康检查 |

## 📚 当前仓库核对入口

| 文件 | 用途 |
| --- | --- |
| `start-all.bat` | 根目录一键启动入口 |
| `scripts/start-suite.ps1` | 环境检查、依赖安装、Docker 健康检查、应用启动与日志状态管理 |
| `stop-all.bat` / `scripts/stop-suite.ps1` | 停止应用服务和占用端口的进程 |
| `stop-infra.bat` / `scripts/stop-infra.ps1` | 停止 MySQL 与 Redis 容器 |
| `services/fulfillment-center/.env.example` | 履约、代理、激活提供方和 Worker 配置模板 |
| `services/xianyu-auto-reply/websocket/.env.example` | WebSocket 与本地履约商品范围模板 |
| `services/fulfillment-center/app/static/index.html` | 库存中心的设置、库存、出库、激活队列和审计页面 |
| `services/fulfillment-center/app/static/app.js` | 库存导入、设置保存和激活队列页面行为 |
| `reset-admin-password.bat` | 根目录管理员密码本机交互式 `reset` / `unlock` 包装入口 |
| `services/xianyu-auto-reply/backend-web/app/admin_password.py` | 包装脚本调用的本机交互式管理员密码 `setup` / `reset` 实现 |
| `services/xianyu-auto-reply/frontend/src/pages/accounts/Accounts.tsx` | 闲鱼账号、扫码登录、在线状态和自动确认发货开关 |
| `services/xianyu-auto-reply/frontend/src/pages/items/Items.tsx` | 商品同步、商品配置和回复配置 |
| `services/xianyu-auto-reply/frontend/src/pages/cards/` | 卡券创建、卡券类型和商品关联 |
