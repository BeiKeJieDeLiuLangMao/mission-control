# Skills 模块

> 技能市场：MarketplaceSkill、SkillPack、网关安装。

## 概览

Skills Marketplace 是 Mission Control 的技能管理系统，允许组织管理员从 Git 仓库同步技能包、浏览技能目录、并将技能安装到指定 Gateway。

## 数据模型

```
MarketplaceSkill (市场技能)
    └── GatewayInstalledSkill (网关已安装技能) → Gateway

SkillPack (技能包)
    → Git clone → 解析 → MarketplaceSkill (N)
```

## 主要 Model (backend/app/models/skills.py)

| Model | 表名 | 关键字段 | 说明 |
|-------|------|---------|------|
| MarketplaceSkill | marketplace_skills | organization_id, name, source_url, category, risk, metadata_ | 可安装技能条目 |
| SkillPack | skill_packs | organization_id, name, source_url, branch, metadata_ | 技能包仓库 |
| GatewayInstalledSkill | gateway_installed_skills | gateway_id, skill_id | 网关已安装技能 |

### MarketplaceSkill

单个技能条目，包含:
- `name`: 技能名称
- `description`: 描述
- `category`: 分类
- `risk`: 风险等级
- `source`: 来源标识
- `source_url`: 来源 URL (唯一约束: organization_id + source_url)
- `metadata_`: JSON 扩展元数据

### SkillPack

技能包仓库，可批量同步技能:
- `source_url`: Git 仓库 URL
- `branch`: 分支名 (默认 `main`)
- 唯一约束: `(organization_id, source_url)`

### GatewayInstalledSkill

记录技能在哪些 Gateway 上安装:
- 唯一约束: `(gateway_id, skill_id)`

## 同步流程

```
管理员添加 SkillPack (Git URL + branch)
    → Git clone (超时: 600s)
    → 解析仓库内技能定义
    → 创建/更新 MarketplaceSkill 记录
    → 管理员选择技能
    → 安装到 Gateway (创建 GatewayInstalledSkill)
```

## API 路由映射

| 路由前缀 | 文件 | 用途 | 权限 |
|----------|------|------|------|
| /skills | api/skills_marketplace.py | 技能目录浏览 | org_member |
| /skills | api/skills_marketplace.py | 技能包管理、安装/卸载 | org_admin |

### 主要端点

- `GET /skills` — 技能目录列表
- `POST /skills/packs` — 添加技能包
- `POST /skills/packs/{id}/sync` — 同步技能包
- `POST /skills/{id}/install` — 安装技能到 Gateway
- `DELETE /skills/{id}/install` — 卸载技能

## 关键文件

| 文件 | 作用 |
|------|------|
| models/skills.py | MarketplaceSkill + SkillPack + GatewayInstalledSkill |
| api/skills_marketplace.py | Skills API 路由 |

## 相关文档

- [Gateway](./gateway.md) — 技能安装的目标网关
- [Organizations](./organizations.md) — 组织级权限控制
- [API 约定](../reference/api.md) — REST API 通用约定
