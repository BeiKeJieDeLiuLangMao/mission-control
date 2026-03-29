# Boards 模块

> 看板工作区：Board、Board Group、Approval、Webhook。

## 概览

Board 是 Mission Control 中的核心工作区，归属于 Organization，关联 Gateway 和 Agent。Board 内包含 Task、Approval、Webhook 等资源，并支持多种治理选项控制 Agent 行为。

## 数据模型

```
Board (看板)
    ├── Task (任务) → 见 tasks.md
    ├── Approval (审批)
    │   └── ApprovalTaskLink (审批-任务关联)
    ├── BoardWebhook (Webhook 配置)
    │   └── BoardWebhookPayload (Webhook 载荷)
    ├── Agent (代理, 通过 gateway_id 关联)
    ├── BoardMemory (看板记忆)
    └── BoardOnboarding (看板引导会话)

BoardGroup (看板组)
    ├── Board (N)
    └── BoardGroupMemory (看板组记忆)
```

## 主要 Model (backend/app/models/)

| Model | 表名 | 关键字段 | 说明 |
|-------|------|---------|------|
| Board | boards | organization_id, name, slug, gateway_id, board_type, objective, max_agents | 看板/工作区 |
| BoardGroup | board_groups | organization_id, name, description | 看板分组 |
| Approval | approvals | board_id, task_id, agent_id, action_type, status, confidence | 审批请求 |
| ApprovalTaskLink | approval_task_links | approval_id, task_id | 审批-任务多对多 |
| BoardWebhook | board_webhooks | board_id, agent_id, description, secret, signature_header | Webhook 配置 |
| BoardWebhookPayload | board_webhook_payloads | webhook_id, payload, status | Webhook 载荷记录 |
| BoardMemory | board_memory | board_id, content | 看板级持久记忆 |
| BoardOnboarding | board_onboarding | board_id, session_state | 引导会话状态 |

## Board 治理选项

Board 支持多种治理配置控制 Agent 行为:

| 配置项 | 默认值 | 说明 |
|--------|--------|------|
| `require_approval_for_done` | `true` | Task 完成前需要审批 |
| `require_review_before_done` | `false` | Task 完成前需要审查 |
| `comment_required_for_review` | `false` | 审查时需要备注 |
| `block_status_changes_with_pending_approval` | `false` | 待审批时阻止状态变更 |
| `only_lead_can_change_status` | `false` | 仅 Lead Agent 可更改状态 |
| `max_agents` | `1` | 每个 Board 最大 Agent 数 |

## Approval 工作流

```
Agent 请求审批 (action_type + payload + confidence)
    → 创建 Approval (status: pending)
    → 关联 ApprovalTaskLink
    → 用户/Lead 审查
    → 解决 Approval (approve/reject)
    → resolved_at 记录时间
```

审批支持 `rubric_scores` (评分细则) 和 `confidence` (信心分数)。

## Webhooks

入站 Webhook 处理流程:

```
外部系统 → POST /boards/{id}/webhooks/{wh_id}/ingest
    → HMAC-SHA256 签名验证 (secret + signature_header)
    → 速率限制检查 (60 req/60s/IP)
    → 记录 BoardWebhookPayload
    → 入队 (enqueue_webhook_delivery)
    → Worker 处理 → 分发到目标 Agent
```

## API 路由映射

| 路由前缀 | 文件 | 用途 | 权限 |
|----------|------|------|------|
| /boards | api/boards.py | Board CRUD、快照 | org_member/org_admin |
| /board-groups | api/board_groups.py | BoardGroup CRUD、快照、心跳 | org_member |
| /boards/{id}/approvals | api/approvals.py | 审批列表、创建/解决、SSE | actor_read/actor_write |
| /boards/{id}/webhooks | api/board_webhooks.py | Webhook CRUD、入站接收 | user_write + HMAC |
| /boards/{id}/memory | api/board_memory.py | 看板记忆 CRUD、流式 | actor_read/user_write |
| /boards/{id}/onboarding | api/board_onboarding.py | 引导会话 | user_write |

## 关键文件

| 文件 | 作用 |
|------|------|
| models/boards.py | Board 模型 (含治理配置) |
| models/board_groups.py | BoardGroup 模型 |
| models/approvals.py | Approval 模型 |
| models/approval_task_links.py | 审批-任务关联 |
| models/board_webhooks.py | Webhook 配置 + 载荷 |
| models/board_memory.py | 看板记忆 |
| models/board_onboarding.py | 引导会话 |
| services/board_snapshot.py | 看板快照组装 |
| services/board_lifecycle.py | 看板生命周期操作 |
| services/webhooks/dispatch.py | Webhook 分发 |
| services/webhooks/queue.py | Webhook 入队/出队 |
| models/board_webhook_payloads.py | Webhook 载荷记录 |
| services/board_group_snapshot.py | 看板组快照组装 |
| services/lead_policy.py | Lead Agent 审批和规划策略 |
| api/board_groups.py | BoardGroup CRUD + 快照 + 心跳 |

## 相关文档

- [Tasks](./tasks.md) — 任务管理
- [Organizations](./organizations.md) — 多租户与权限
- [Gateway](./gateway.md) — Agent 生命周期
- [安全](../reference/security.md) — HMAC 验签、限流
- **E2E 测试**: `/mission-control-e2e-testing` Skill — 前端页面端到端测试
