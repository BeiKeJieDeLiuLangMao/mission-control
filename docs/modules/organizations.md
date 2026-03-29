# Organizations 模块

> 多租户基础：Organization、成员管理、权限控制。

## 概览

Organization 是 Mission Control 的顶级租户实体，所有 Gateway、Board、Task、Skill 等资源都归属于某个 Organization。

## 数据模型

```
Organization (组织)
    ├── OrganizationMember (成员, roles: owner/admin/member)
    │   └── OrganizationBoardAccess (看板级权限)
    ├── OrganizationInvite (邀请)
    │   └── OrganizationInviteBoardAccess (邀请附带的看板权限)
    ├── Gateway (网关) → 见 gateway.md
    ├── Board (看板) → 见 boards.md
    └── MarketplaceSkill (技能) → 见 skills.md
```

## 主要 Model (backend/app/models/)

| Model | 表名 | 关键字段 | 说明 |
|-------|------|---------|------|
| Organization | organizations | id, name | 顶级租户 |
| OrganizationMember | organization_members | organization_id, user_id, role, all_boards_read/write | 成员关系 + 权限 |
| OrganizationInvite | organization_invites | organization_id, email, role | 邮件邀请 |
| OrganizationBoardAccess | organization_board_access | member_id, board_id, can_read, can_write | 看板级权限 |
| User | users | id, clerk_id, email, name | 用户实体 |

## 多租户模型

- Organization 是租户边界，所有资源通过 `organization_id` 隔离
- OrganizationMember 支持三种角色: `owner`, `admin`, `member`
- `all_boards_read` / `all_boards_write` 标志控制全看板访问
- Board 级别通过 OrganizationBoardAccess 实现细粒度权限
- TenantScoped 基类为 Board, Task, Tag 等模型提供 `organization_id` 约束

## 邀请流程

```
管理员创建邀请 (email + role)
    → 邮件/链接发送
    → 用户接受邀请
    → 创建 OrganizationMember
    → 应用 OrganizationInviteBoardAccess → OrganizationBoardAccess
```

## API 路由映射

| 路由前缀 | 文件 | 用途 | 权限 |
|----------|------|------|------|
| /organizations | api/organizations.py | Organization CRUD、成员管理、邀请 | 用户认证 |

## 关键文件

| 文件 | 作用 |
|------|------|
| models/organizations.py | Organization 模型 |
| models/organization_members.py | 成员关系 + 权限 |
| models/organization_invites.py | 邀请模型 |
| models/organization_board_access.py | 看板级权限 |
| models/tenancy.py | TenantScoped 基类 |
| models/users.py | 用户模型 |
| api/organizations.py | Organization API 路由 |
| services/organizations.py | 成员管理 + 看板访问服务 |
| models/organization_invite_board_access.py | 邀请附带的看板权限 |
| api/auth.py | 认证引导端点 |
| services/admin_access.py | Actor 类型访问控制 |

## 相关文档

- [Boards](./boards.md) — 看板与审批
- [Gateway](./gateway.md) — 网关管理
- [认证](../reference/authentication.md) — local / Clerk 认证模式
- [API 约定](../reference/api.md) — REST API 通用约定
