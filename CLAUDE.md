# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

> **渐进式披露**: 本文件是项目地图 (Layer 1)。处理具体模块时，先读 `docs/modules/` 对应文档 (Layer 2)，再读代码 (Layer 3)。

## 项目概述

OpenClaw Mission Control 是一个用于运营和管理 OpenClaw/Claude Code 的统一平台。这是一个全栈应用:
- **Backend**: FastAPI 服务 (`backend/`),使用 SQLAlchemy + Alembic
- **Frontend**: Next.js 应用 (`frontend/`),使用 TypeScript + React
- **Adapters**: AI 工具集成适配器 (`adapters/`),将 Claude Code 和 OpenClaw 连接到 Memory 系统
  - `adapters/claude-code/` — Shell hooks (UserPromptSubmit 召回 + Stop 存储)
  - `adapters/openclaw/` — TypeScript 插件 (before_agent_start 召回 + agent_end 存储)
- 前后端通过 REST API 通信,前端 API 客户端由 orval 自动生成

## 核心架构

### Backend 结构
```
backend/
├── app/
│   ├── api/           # API 路由模块 (按功能领域组织)
│   │   └── memory/    # Memory API (adapter_* / frontend_* / internal_*)
│   ├── core/          # 核心功能 (认证、配置、错误处理、日志、限流)
│   ├── db/            # 数据库会话和连接管理
│   ├── models/        # SQLAlchemy ORM 模型
│   ├── schemas/       # Pydantic 请求/响应模式
│   ├── memory/        # Memory 模块 (core/providers/ailearn 三层)
│   └── services/      # 业务逻辑层
├── migrations/        # Alembic 数据库迁移
├── templates/         # 后端提供的模板 (用于 gateway 流程)
└── tests/            # pytest 测试套件
```

### Frontend 结构
```
frontend/
├── src/
│   ├── app/          # Next.js App Router 页面和布局
│   ├── components/   # React 组件 (按 atoms/molecules/organisms 组织)
│   ├── lib/          # 工具函数和共享逻辑
│   ├── api/
│   │   └── generated/ # 自动生成的 API 客户端 (不要手动编辑)
│   ├── auth/         # 认证集成 (Clerk/local)
│   └── hooks/        # 自定义 React hooks
```

### 认证架构
项目支持两种认证模式 (通过 `AUTH_MODE` 环境变量配置):
- **local**: 共享 bearer token 模式,用于自托管
- **clerk**: Clerk JWT 模式

### 限流系统
- **memory**: 内存限流 (默认)
- **redis**: Redis 限流 (需要 `RATE_LIMIT_REDIS_URL`)

## 常用开发命令

### 依赖安装
```bash
make setup              # 安装前后端依赖
make backend-sync       # 仅后端: uv sync --extra dev
make frontend-sync      # 仅前端: npm install
```

### 代码质量检查
```bash
make check              # 完整 CI 检查 (lint + typecheck + tests + build)
make lint               # 前后端 lint
make typecheck          # 前后端类型检查
```

### 测试
```bash
make backend-test       # 运行后端测试 (pytest)
make backend-coverage   # 后端测试覆盖率 (要求 100% 覆盖指定模块)
make frontend-test      # 运行前端测试 (vitest)
```

### 代码格式化
```bash
make format             # 格式化前后端代码
make format-check       # 检查格式 (不修改文件)
```

### 构建和运行

本项目通过 **launchd** 管理前后端服务 (Mac 登录后自动启动):

```bash
# 查看服务状态
launchctl list | grep ai.openclaw.mc

# 重启服务
launchctl kickstart -k gui/$(id -u)/ai.openclaw.mc.backend
launchctl kickstart -k gui/$(id -u)/ai.openclaw.mc.frontend

# 查看日志
tail -f ~/.openclaw/logs/mc-backend.log
tail -f ~/.openclaw/logs/mc-frontend.log
```

| 服务 | plist | 端口 |
|---|---|---|
| Backend (FastAPI) | `~/Library/LaunchAgents/ai.openclaw.mc.backend.plist` | 8000 |
| Frontend (Next.js) | `~/Library/LaunchAgents/ai.openclaw.mc.frontend.plist` | 3000 |

Docker 方式和手动启动见 `docs/deployment/README.md`。

### API 客户端生成
```bash
make api-gen           # 后端必须运行在 127.0.0.1:8000
```

### 数据库迁移
```bash
make backend-migrate           # 应用迁移
make backend-migration-check   # 验证迁移图和可逆性
```

## 代码风格规范

### Python
- **格式化**: Black (100 字符行宽) + isort
- **Lint**: flake8
- **类型检查**: mypy --strict
- **命名**: `snake_case` 用于变量和函数,`PascalCase` 用于类
- **导入顺序**: stdlib → 第三方 → 本地 (由 isort 管理)

### TypeScript/React
- **格式化**: Prettier
- **Lint**: ESLint
- **类型检查**: tsc --noEmit
- **命名**: `PascalCase` 用于组件,`camelCase` 用于变量/函数
- **未使用变量**: 使用下划线前缀 `_variable` 满足 lint 规则

## 开发注意事项

### API 更新流程
1. 在 `backend/app/api/` 中修改路由
2. 在 `backend/app/schemas/` 中更新 Pydantic 模式
3. 确保后端运行在 `127.0.0.1:8000`
4. 运行 `make api-gen` 重新生成前端 API 客户端
5. 在 `frontend/src/app/` 或组件中使用生成的客户端

### 数据库变更
1. 修改 `backend/app/models/` 中的模型
2. 运行 `cd backend && uv run alembic revision --autogenerate -m "描述"`
3. 检查生成的迁移文件在 `backend/migrations/versions/`
4. 运行 `make backend-migrate` 应用迁移
5. 使用 `make backend-migration-check` 验证迁移正确性

### 环境配置
- 复制 `.env.example` 到 `.env` 并填写真实值
- 关键配置:
  - `AUTH_MODE=local` 时,必须设置非占位符的 `LOCAL_AUTH_TOKEN` (最少 50 字符)
  - `BASE_URL` 必须匹配公共后端源 (如果不是 `http://localhost:8000`)
  - `NEXT_PUBLIC_API_URL=auto` 会自动解析为当前主机的 8000 端口
- Memory 模块环境变量 (QDRANT_*, LLM_*, NEO4J_*) 见 `docs/modules/memory.md`

### 覆盖率策略
- 当前只对特定模块强制 100% 覆盖率: `app.core.error_handling`, `app.services.mentions`
- 运行 `make backend-coverage` 查看覆盖率报告

## 文档同步规范

本项目采用三层渐进式文档 (CLAUDE.md → docs/ → code)，修改代码时必须同步对应文档：

1. **目录结构变更** → 更新 CLAUDE.md 的 Backend/Frontend 结构树
2. **新增/重构模块** → 更新 `docs/modules/` 对应文档的架构图和关键文件表
3. **新增 API 端点** → 更新 `docs/modules/` 中的 API 路由映射表
4. **环境变量变更** → 更新 `docs/modules/` 中的环境变量表 + `.env.example`
5. **新增测试方法** → 更新 `docs/testing/README.md` 或对应 Skill
6. **数据库 Model 变更** → 更新 `docs/modules/database.md` 的 Model 表

> 原则: 代码 PR 中如果涉及以上变更，docs 更新应包含在同一个 PR 中。

## Git 工作流

### Conventional Commits
- `feat: ...` 新功能 | `fix: ...` bug 修复 | `docs: ...` 文档 | `refactor: ...` 重构 | `test(scope): ...` 测试

## 功能模块 (按需深入)

处理特定模块时，先读对应文档获取上下文，再读代码。

| 模块 | 简述 | 详情 | 测试 Skill |
|------|------|------|-----------|
| Memory | AI 持久化记忆 (core/providers/ailearn) | `docs/modules/memory.md` | `/memory-e2e-testing` |
| Adapters | Claude Code hooks + OpenClaw 插件 | `docs/modules/adapters.md` | `/claude-code-plugin-testing` |
| Database | PostgreSQL + Qdrant + Neo4j | `docs/modules/database.md` | - |
| Gateway | 网关管理与 Agent 生命周期 | `docs/modules/gateway.md` | - |
| Organizations | 多租户、成员、权限 | `docs/modules/organizations.md` | - |
| Boards | 看板、审批、Webhooks | `docs/modules/boards.md` | - |
| Tasks | 任务、依赖、自定义字段、标签 | `docs/modules/tasks.md` | - |
| Skills | 技能市场、技能包、安装 | `docs/modules/skills.md` | - |
| Auth | local token / Clerk JWT | `docs/reference/authentication.md` | - |
| API | REST API 设计与约定 | `docs/reference/api.md` | - |
| Testing | pytest + vitest + E2E | `docs/testing/README.md` | `/mission-control-e2e-testing` |
| Deployment | Docker + systemd + launchd | `docs/deployment/README.md` | - |
| Operations | 健康检查、备份、限流 | `docs/operations/README.md` | - |
| Security | Headers, HMAC, 限流 | `docs/reference/security.md` | - |

## 重要路径

### 配置文件
- `backend/pyproject.toml` - Python 项目配置
- `frontend/package.json` - Node.js 依赖
- `compose.yml` - Docker Compose 配置
- `.env.example` - 环境变量模板

### 关键代码入口
- `backend/app/main.py` - FastAPI 应用入口和路由注册
- `backend/app/core/config.py` - 配置管理 (Pydantic Settings)
- `backend/app/core/auth.py` - 认证逻辑
- `backend/app/core/error_handling.py` - 统一错误处理
- `frontend/src/proxy.ts` - API 代理配置

## 故障排查

### 限流问题
- 如果使用 Redis 后端,检查 `RATE_LIMIT_REDIS_URL` 连接
- 应用启动时会验证 Redis 连接 (见 `app/core/rate_limit.py`)

### 迁移问题
- 运行 `make backend-migration-check` 验证迁移图
- 检查 `backend/migrations/versions/` 中的迁移文件顺序

### API 客户端生成失败
- 确保后端运行在 `127.0.0.1:8000` (不是 localhost)
- 检查后端健康状态: `curl http://localhost:8000/healthz`

### Docker 构建问题
- 完全重新构建: `docker compose -f compose.yml --env-file .env build --no-cache --pull`

### Memory / 数据库问题
- 详见 `docs/modules/memory.md` 的故障排查章节
- 数据库检查命令见 `docs/modules/database.md`
