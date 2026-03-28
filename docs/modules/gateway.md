# Gateway 模块

> 从 CLAUDE.md 提取的详细文档。概览见项目根目录 `CLAUDE.md` 的模块索引表。

## 概述

Gateway 模块管理 Mission Control 与 OpenClaw 网关之间的连接，负责 Agent 的模板渲染、生命周期编排和 WebSocket RPC 通信。

## 架构

```
Mission Control (FastAPI :8000)
    │
    ↓  WebSocket RPC (Protocol v3)
OpenClaw Gateway (wss://...)
    │
    ├── Agent 1 (Board Lead)
    ├── Agent 2 (Board Worker)
    └── Agent N
```

核心关系：
- Organization (1) → Gateway (N) → Agent (N)
- Gateway 持有 WebSocket URL + token
- Agent 生命周期状态：`provisioning` → `online` → `offline`

## 关键文件

| 文件 | 作用 |
|------|------|
| `services/openclaw/gateway_rpc.py` | WebSocket RPC 协议 (Protocol v3, 44+ methods) |
| `services/openclaw/provisioning.py` | Agent 模板渲染 (Jinja2) + 文件写入 |
| `services/openclaw/provisioning_db.py` | DB 持久层 (Agent/Gateway/Board CRUD) |
| `services/openclaw/coordination_service.py` | 多 Agent 协调 (Lead ↔ Worker 消息) |
| `services/openclaw/lifecycle_orchestrator.py` | 统一生命周期编排 (per-agent 锁) |
| `services/openclaw/lifecycle_queue.py` | RQ 延迟任务入队 (check-in deadline) |
| `services/openclaw/lifecycle_reconcile.py` | Check-in 超时重试 (最多 3 次) |
| `services/openclaw/session_service.py` | Gateway 会话查询 (只读) |
| `services/openclaw/admin_service.py` | 管理员操作 (模板同步, token 轮换) |
| `api/gateways.py` | 网关 CRUD + 模板同步 API |
| `api/gateway.py` | 网关会话检查 API |
| `api/agent.py` | Agent 端操作 (心跳/任务/审批/协调) |

## 数据模型

### Gateway

表名：`gateways`

| 字段 | 说明 |
|------|------|
| `id` (UUID) | 主键 |
| `organization_id` (FK→organizations) | 所属组织 |
| `name` | 网关名称 |
| `url` | WebSocket 端点地址 |
| `token` | 连接令牌 |
| `workspace_root` | 工作区根路径 |
| `disable_device_pairing` (bool) | 禁用设备配对 |
| `allow_insecure_tls` (bool) | 允许自签名 TLS |

### Agent

表名：`agents`

| 字段 | 说明 |
|------|------|
| `id` (UUID) | 主键 |
| `board_id` (FK→boards) | 所属 Board |
| `gateway_id` (FK→gateways) | 所属 Gateway |
| `name` | Agent 名称 |
| `status` | 状态 (默认 `"provisioning"`) |
| `openclaw_session_id` | OpenClaw 会话 ID |
| `agent_token_hash` | Agent token 哈希 |
| `heartbeat_config` (JSON) | 心跳配置 |
| `identity_profile` (JSON) | 身份配置 |
| `identity_template` | 身份模板 |
| `soul_template` | Soul 模板 |
| `provision_requested_at` | Provision 请求时间 |
| `provision_action` | Provision 动作 |
| `lifecycle_generation` | 生命周期代数 |
| `wake_attempts` | Wake 尝试次数 (最多 3 次) |
| `last_wake_sent_at` | 最后 wake 信号时间 |
| `checkin_deadline_at` | Check-in 截止时间 |
| `last_seen_at` | 最后心跳时间 |
| `last_provision_error` | 最后 provision 错误信息 |
| `is_board_lead` (bool) | 是否为 Board Lead |

## API 路由映射

| 路由前缀 | 文件 | 用途 |
|----------|------|------|
| `/gateways` | `api/gateways.py` | Gateway CRUD、模板同步 |
| `/gateways` | `api/gateway.py` | 会话状态查询 |
| `/agent` | `api/agent.py` | Agent 心跳、任务操作、Lead 协调 |

## Agent 生命周期

采用 **Fast Convergence** 策略，确保 Agent 在 provision 后快速上线或明确失败：

```
MC provisions/updates agent
    │
    ├── 1. 发送 wake 信号
    ├── 2. 延迟 reconcile 任务入队 (30 秒 deadline)
    │
    ↓  Agent 启动
    │
    ├── 3. Agent 调用 heartbeat
    ├── 4. Heartbeat 成功:
    │       last_seen_at 更新
    │       wake_attempts 重置
    │       deadline 清除
    │
    ↓  若 deadline 过期 (无 heartbeat)
    │
    ├── 5. Reconcile 重新 wake (最多 3 次)
    │
    ↓  3 次失败后
    │
    └── 6. status → offline
          last_provision_error 记录原因
```

关键常量：
- **Check-in deadline**：30 秒
- **最大 wake 尝试**：3 次

## WebSocket 协议

| 项目 | 说明 |
|------|------|
| 安全连接 | `wss://` (生产环境) |
| 非安全连接 | `ws://` (开发环境) |
| Protocol 版本 | v3 |
| 自签名 TLS | 通过 `allow_insecure_tls` 开关支持 (有安全风险) |
| RPC methods | `health`, `status`, `agents.*`, `exec.approvals.*`, `config.*`, `logs.tail` 等 (44+ methods) |

## Lead Agent 协调

Board Lead 负责编排 Worker Agent，通过以下消息类型实现多 Agent 协调：

| 消息类型 | 方向 | 用途 |
|----------|------|------|
| `GatewayLeadBroadcastRequest` | Lead → 多 Worker | 广播消息 |
| `GatewayMainAskUserRequest` | Agent → 操作者 | 确认请求 |
| `GatewayLeadMessageRequest` | Lead ↔ Worker | 直接消息 |

## 环境变量

| 变量 | 说明 |
|------|------|
| `RQ_REDIS_URL` | Redis 队列地址 (lifecycle 延迟任务) |
| `RQ_QUEUE_NAME` | 队列名称 |

## 故障排查

> 详细的 Agent provisioning 排查指南见 [Gateway Agent 故障排查](../troubleshooting/gateway-agent-provisioning.md)。

常见问题：
- **Agent wake 后无 check-in**：检查 Agent 是否启动、模板是否过期、heartbeat URL 是否正确
- **Agent 卡在 provisioning**：检查 RQ Worker 是否运行、Redis 配置是否匹配
- **Token 漂移**：使用 `POST /api/v1/gateways/{id}/templates/sync?rotate_tokens=true` 重新同步

## 相关文档

- [平台核心](./platform.md) — Organizations/Boards/Tasks (Gateway 的上下文)
- [Database](./database.md) — 底层存储
- [API 约定](../reference/api.md) — REST API 通用约定
- [安全](../reference/security.md) — Token 处理和安全策略
- [Gateway Agent 故障排查](../troubleshooting/gateway-agent-provisioning.md) — 详细排查指南
