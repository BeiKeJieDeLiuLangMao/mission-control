# 平台核心模块

> Organizations、Boards、Tasks、Agents、Approvals、Webhooks、Skills Marketplace。

## 概览

平台核心覆盖 Mission Control 的业务实体和工作流。Organization 是顶级租户，下辖 Gateway、Board、Task 等资源。

## 数据模型关系

```
Organization (组织)
    ├── OrganizationMember (成员, roles: owner/admin/member)
    ├── Gateway (网关)
    │   └── Agent (代理)
    ├── Board (看板)
    │   ├── Task (任务)
    │   ├── Approval (审批)
    │   ├── BoardWebhook (Webhook)
    │   └── Agent (通过 gateway_id 关联)
    ├── Tag (标签)
    ├── MarketplaceSkill (市场技能)
    │   └── GatewayInstalledSkill (网关安装)
    └── SkillPack (技能包)
```

## 主要 Model (backend/app/models/)

| Model | 表名 | 关键字段 | 说明 |
|-------|------|---------|------|
| Organization | organizations | id, name | 顶级租户 |
| OrganizationMember | organization_members | organization_id, user_id, role, all_boards_read/write | 成员关系 + 权限 |
| Board | boards | organization_id, name, slug, gateway_id, board_type, objective, max_agents | 看板/工作区 |
| Task | tasks | board_id, title, status, priority, assigned_agent_id, due_at | 任务实体 |
| Approval | approvals | board_id, task_id, agent_id, action_type, status, confidence | 审批请求 |
| BoardWebhook | board_webhooks | board_id, agent_id, description, secret, signature_header | Webhook 配置 |
| Tag | tags | organization_id, name, slug, color | 任务标签 |
| MarketplaceSkill | marketplace_skills | organization_id, name, source_url, category, risk | 可安装技能 |
| SkillPack | skill_packs | organization_id, source_url, branch | 技能包仓库 |
| GatewayInstalledSkill | gateway_installed_skills | gateway_id, skill_id | 网关已安装技能 |

## API 路由映射

| 路由前缀 | 文件 | 用途 | 权限 |
|----------|------|------|------|
| /organizations | api/organizations.py | Organization CRUD、成员邀请 | 用户认证 |
| /boards | api/boards.py | Board CRUD、快照 | org_member/org_admin |
| /boards/{id}/tasks | api/tasks.py | Task CRUD、状态变更、评论、SSE | actor_read/user_write |
| /boards/{id}/approvals | api/approvals.py | 审批列表、创建/解决、SSE | actor_read/actor_write |
| /boards/{id}/webhooks | api/board_webhooks.py | Webhook CRUD、入站接收 | user_write + HMAC 验签 |
| /tags | api/tags.py | 标签 CRUD + 任务关联 | org_member |
| /skills | api/skills_marketplace.py | 技能目录、技能包、安装/卸载 | org_admin |

## 多租户模型

- Organization 是租户边界
- OrganizationMember 控制用户访问，支持三种角色: owner, admin, member
- all_boards_read / all_boards_write 标志控制全看板访问
- Board 级别通过 OrganizationBoardAccess 实现细粒度权限
- TenantScoped 基类为 Board, Task, Tag 等模型提供 organization_id 约束

## Webhooks

入站 Webhook 处理流程:
```
外部系统 → POST /boards/{id}/webhooks/{wh_id}/ingest
    → HMAC-SHA256 签名验证 (secret + signature_header)
    → 速率限制检查
    → 入队 (enqueue_webhook_delivery)
    → Worker 处理 → 分发到目标 Agent
```

关键文件:
- services/webhooks/dispatch.py — 分发队列处理
- services/webhooks/queue.py — 入队/出队

## Skills Marketplace

- MarketplaceSkill: 单个技能条目 (名称、分类、风险等级、来源 URL)
- SkillPack: 技能包仓库 (Git URL + branch)，可批量同步技能
- GatewayInstalledSkill: 记录技能在哪些网关上安装
- 同步流程: SkillPack → Git clone → 解析技能 → 更新 MarketplaceSkill

## Board 工作流

Board 支持多种治理选项:
- require_approval_for_done: 完成前需要审批
- require_review_before_done: 完成前需要审查
- block_status_changes_with_pending_approval: 待审批时阻止状态变更
- only_lead_can_change_status: 仅 Lead Agent 可更改状态
- max_agents: 每个 Board 最大 Agent 数

## 关键文件

| 文件 | 作用 |
|------|------|
| models/organizations.py | Organization 模型 |
| models/organization_members.py | 成员关系 + 权限 |
| models/boards.py | Board 模型 (含治理配置) |
| models/tasks.py | Task 模型 (含状态/优先级) |
| models/approvals.py | Approval 模型 |
| models/board_webhooks.py | Webhook 配置 + 载荷 |
| models/skills.py | MarketplaceSkill + SkillPack + GatewayInstalledSkill |
| models/tags.py | Tag 模型 |
| models/tenancy.py | TenantScoped 基类 |
| services/organizations.py | 成员管理 + 看板访问 |
| services/board_snapshot.py | 看板快照组装 |
| services/webhooks/dispatch.py | Webhook 分发 |

## 相关文档

- [Gateway](./gateway.md) — 网关管理与 Agent 生命周期
- [Database](./database.md) — 底层存储
- [Memory](./memory.md) — AI 持久化记忆
- [认证](../reference/authentication.md) — 认证模式
- [安全](../reference/security.md) — HMAC 验签、限流
- [API 约定](../reference/api.md) — REST API 通用约定
