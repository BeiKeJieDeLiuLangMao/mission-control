# CLAUDE.md

IMPORTANT: 处理任何模块相关任务时，必须先读 `docs/modules/` 对应文档获取关键文件列表和架构概览，再进入代码。直接 Grep/Glob 盲搜代码是低效的。

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

## 开发工作流

> **执行任何开发任务前必读**: `docs/development/workflow.md`
>
> 五步法: Doc 先行 → 代码实现 → 交互验证 (MCP headless) → 修复问题 → 脚本固化
>
> 关键规则: 文档与代码保持一致 | 端口不换只修 | E2E 先交互后脚本 | headless 不弹窗

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

### 构建和运行 (launchd 管理, Backend :8000, Frontend :3000)

```bash
launchctl list | grep ai.openclaw.mc                          # 状态
launchctl kickstart -k gui/$(id -u)/ai.openclaw.mc.backend    # 重启后端
launchctl kickstart -k gui/$(id -u)/ai.openclaw.mc.frontend   # 重启前端
tail -f ~/.openclaw/logs/mc-backend.log                       # 日志
```

Docker 方式见 `docs/deployment/README.md`。

### API 客户端生成
```bash
make api-gen           # 后端必须运行在 127.0.0.1:8000
```

### 数据库迁移
```bash
make backend-migrate           # 应用迁移
make backend-migration-check   # 验证迁移图和可逆性
```

## 开发规范

- 代码风格: Python (Black 100 + isort + flake8 + mypy --strict) / TypeScript (Prettier + ESLint + tsc)
- 环境: `cp .env.example .env` → `AUTH_MODE=local` 时 `LOCAL_AUTH_TOKEN` ≥ 50 字符
- 数据库变更: `cd backend && uv run alembic revision --autogenerate -m "描述"` → `make backend-migrate`
- Git: `feat:` | `fix:` | `docs:` | `refactor:` | `test(scope):` (Conventional Commits)

> 详细的 API 开发流程、文档同步规范、测试规范见 `.claude/rules/` 目录。

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
| **Workflow** | **开发五步法 + E2E 规范** | **`docs/development/workflow.md`** | - |
| Testing | pytest + vitest + E2E | `docs/testing/README.md` | `/mission-control-e2e-testing` |
| Deployment | Docker + systemd + launchd | `docs/deployment/README.md` | - |
| Operations | 健康检查、备份、限流 | `docs/operations/README.md` | - |
| Security | Headers, HMAC, 限流 | `docs/reference/security.md` | - |

## 关键入口

- `backend/app/main.py` — FastAPI 入口 + 路由注册
- `backend/app/core/config.py` — 配置管理 (Pydantic Settings)
- `backend/app/core/error_handling.py` — 统一错误处理
- `.env.example` — 环境变量模板

## 故障排查

- 限流 / 迁移 / API 生成: `make backend-migration-check`, `curl http://localhost:8000/healthz`
- Memory / 数据库: 见 `docs/modules/memory.md` 和 `docs/modules/database.md`
- 完整排查指南: `docs/troubleshooting/README.md`
