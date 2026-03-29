# Tasks 模块

> 任务管理：Task、依赖、自定义字段、标签。

## 概览

Task 是 Mission Control 中的核心工作单元，归属于 Board。支持状态流转、优先级、Agent 分配、依赖关系、自定义字段和标签分类。

## 数据模型

```
Task (任务)
    ├── TaskDependency (任务依赖, 有向边)
    ├── TaskCustomFieldBinding (自定义字段值)
    ├── TaskFingerprint (指纹, 用于去重/关联)
    └── TagAssignment (标签关联)

TaskCustomField (自定义字段定义, Board 级)

Tag (标签, Organization 级)
    └── TagAssignment (标签-任务关联)

ActivityEvent (活动事件/审计日志)
```

## 主要 Model (backend/app/models/)

| Model | 表名 | 关键字段 | 说明 |
|-------|------|---------|------|
| Task | tasks | board_id, title, status, priority, assigned_agent_id, due_at | 任务实体 |
| TaskDependency | task_dependencies | from_task_id, to_task_id, dependency_type | 任务依赖边 |
| TaskCustomField | task_custom_fields | board_id, name, field_type | 自定义字段定义 |
| TaskCustomFieldBinding | task_custom_field_bindings | task_id, field_id, value | 字段值绑定 |
| TaskFingerprint | task_fingerprints | task_id, fingerprint, source | 去重/关联指纹 |
| Tag | tags | organization_id, name, slug, color | 组织级标签 |
| TagAssignment | tag_assignments | tag_id, task_id | 标签-任务关联 |
| ActivityEvent | activity_events | board_id, task_id, actor_type, event_type | 审计日志 |

## Task 状态流转

Task 默认状态为 `inbox`，支持以下流转:

```
inbox → todo → in_progress → review → done
  ↓                                    ↑
  └──────────── blocked ───────────────┘
```

关键字段:
- `status`: 当前状态 (indexed)
- `priority`: 优先级 (`low`, `medium`, `high`, `critical`)
- `in_progress_at`: 开始进行时间 (自动记录)
- `assigned_agent_id`: 分配的 Agent
- `auto_created` / `auto_reason`: Agent 自动创建的标记和原因

## 任务依赖

TaskDependency 表示任务间的有向依赖关系:
- `from_task_id` → `to_task_id`: "from 依赖 to"
- `dependency_type`: 依赖类型

服务层 (`services/task_dependencies.py`) 提供依赖验证和查询。

## 自定义字段

Board 级别定义自定义字段，Task 级别绑定值:
- TaskCustomField: 定义字段名和类型 (归属 Board)
- TaskCustomFieldBinding: 绑定字段值到具体 Task

## 标签

Tag 是 Organization 级别的分类标签:
- 唯一约束: `(organization_id, slug)`
- 每个 Tag 可关联到多个 Task (通过 TagAssignment)
- 支持颜色 (`color`) 用于前端展示

## API 路由映射

| 路由前缀 | 文件 | 用途 | 权限 |
|----------|------|------|------|
| /boards/{id}/tasks | api/tasks.py | Task CRUD、状态变更、评论、SSE | actor_read/user_write |
| /boards/{id}/tasks/{id}/custom-fields | api/task_custom_fields.py | 自定义字段 CRUD、绑定 | user_write |
| /tags | api/tags.py | 标签 CRUD + 任务关联 | org_member |
| /activity | api/activity.py | 活动事件/审计日志 | user_read |

## 关键文件

| 文件 | 作用 |
|------|------|
| models/tasks.py | Task 模型 (状态/优先级/分配) |
| models/task_dependencies.py | 任务依赖边 |
| models/task_custom_fields.py | 自定义字段定义 + 绑定 |
| models/task_fingerprints.py | 去重/关联指纹 |
| models/tags.py | 标签模型 |
| models/tag_assignments.py | 标签-任务关联 |
| models/activity_events.py | 审计日志 |
| api/tasks.py | Task API (CRUD + 状态 + 评论 + SSE) |
| api/task_custom_fields.py | 自定义字段 API |
| api/tags.py | 标签 API |
| services/activity_log.py | 活动日志记录 |
| services/task_dependencies.py | 依赖验证和查询 |
| api/activity.py | 活动事件/审计日志 API |
| services/mentions.py | @mention 提取和匹配 |

## 相关文档

- [Boards](./boards.md) — 看板与审批
- [Organizations](./organizations.md) — 多租户与权限
- [Database](./database.md) — 底层存储
- [API 约定](../reference/api.md) — REST API 通用约定
- **E2E 测试**: `/mission-control-e2e-testing` Skill — 前端页面端到端测试
