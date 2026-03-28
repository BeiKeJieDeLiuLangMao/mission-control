# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## 项目概述

OpenClaw Mission Control 是一个用于运营和管理 OpenClaw 的统一平台。这是一个全栈应用:
- **Backend**: FastAPI 服务 (`backend/`),使用 SQLAlchemy + Alembic
- **Frontend**: Next.js 应用 (`frontend/`),使用 TypeScript + React
- 前后端通过 REST API 通信,前端 API 客户端由 orval 自动生成

## 核心架构

### Backend 结构
```
backend/
├── app/
│   ├── api/           # API 路由模块 (按功能领域组织)
│   ├── core/          # 核心功能 (认证、配置、错误处理、日志、限流)
│   ├── db/            # 数据库会话和连接管理
│   ├── models/        # SQLAlchemy ORM 模型
│   ├── schemas/       # Pydantic 请求/响应模式
│   ├── memory/        # Memory 模块 (从 mem0 迁移, 详见下方)
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

认证逻辑在 `backend/app/core/auth.py` 和 `frontend/src/auth/` 中实现。

### 限流系统
支持两种限流后端 (`RATE_LIMIT_BACKEND`):
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
```bash
# Docker 方式 (推荐用于生产)
docker compose -f compose.yml --env-file .env up -d --build

# 本地开发模式 (快速迭代)
docker compose -f compose.yml --env-file .env up -d db
cd backend && uv run uvicorn app.main:app --reload --port 8000
cd frontend && npm run dev

# 前端构建
make frontend-build    # 或: cd frontend && npm run build
```

### MC 自用 Mac 开机自启 (launchd)

> 以下为本地 MC 开发环境的 launchd 配置，适用于非 Docker 模式。
> 配置文件在 `~/Library/LaunchAgents/`，登录后自动启动前后端服务。

| 服务 | plist 文件 | 端口 |
|---|---|---|
| Backend (FastAPI) | `ai.openclaw.mc.backend.plist` | 8000 |
| Frontend (Next.js) | `ai.openclaw.mc.frontend.plist` | 3000 |

```bash
# 查看服务状态
launchctl list | grep ai.openclaw.mc

# 重新加载服务 (修改 plist 后需执行)
launchctl unload ~/Library/LaunchAgents/ai.openclaw.mc.backend.plist
launchctl unload ~/Library/LaunchAgents/ai.openclaw.mc.frontend.plist
launchctl load ~/Library/LaunchAgents/ai.openclaw.mc.backend.plist
launchctl load ~/Library/LaunchAgents/ai.openclaw.mc.frontend.plist

# 查看日志
cat ~/.openclaw/logs/mc-backend.log
cat ~/.openclaw/logs/mc-backend-error.log
cat ~/.openclaw/logs/mc-frontend.log
cat ~/.openclaw/logs/mc-frontend-error.log
```

> 注意：LaunchAgents 在**用户登录后**启动，非机器开机。如需开机即启动需用 LaunchDaemons。

### API 客户端生成
```bash
# 修改后端 API 后,重新生成前端 API 客户端
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

### Memory 模块环境变量

配置定义在 `backend/app/memory/utils/__init__.py` 的 `get_default_memory_config()` 中。

| 变量 | 默认值 | 说明 |
|------|--------|------|
| `QDRANT_HOST` | `127.0.0.1` | Qdrant 向量数据库地址 |
| `QDRANT_PORT` | `6333` | Qdrant 端口 |
| `QDRANT_COLLECTION` | `memories` | Qdrant 集合名 |
| `LLM_PROVIDER` | `openai` | LLM 提供商 (openai/ollama/anthropic 等) |
| `LLM_MODEL` | `gpt-4o-mini` | LLM 模型名 |
| `LLM_API_KEY` | `env:OPENAI_API_KEY` | LLM API Key (支持 `env:` 前缀引用) |
| `LLM_BASE_URL` | (空) | LLM API Base URL |
| `EMBEDDER_PROVIDER` | `openai` | 嵌入模型提供商 |
| `EMBEDDER_MODEL` | `text-embedding-3-small` | 嵌入模型名 |
| `EMBEDDER_API_KEY` | `env:OPENAI_API_KEY` | 嵌入 API Key |
| `EMBEDDER_BASE_URL` | (空) | 嵌入 API Base URL |
| `NEO4J_URI` | (空) | Neo4j URI (设置后启用图谱, 如 `bolt://localhost:7687`) |
| `NEO4J_USERNAME` | `neo4j` | Neo4j 用户名 |
| `NEO4J_PASSWORD` | (空) | Neo4j 密码 |
| `OLLAMA_BASE_URL` | (空) | Ollama API 地址 |

### Memory 开发工作流

#### 手动测试 Memory 功能
```bash
# 创建 turn
curl -X POST http://localhost:8000/api/v2/turns/ \
  -H "Content-Type: application/json" \
  -d '{"user_id":"test","session_id":"s1","agent_id":"a1","messages":[{"role":"user","content":"我喜欢Python"}],"source":"test"}'

# 等待 Worker 处理 (~10秒)
sleep 10

# 验证记忆
curl "http://localhost:8000/api/v2/memories/search?user_id=test&query=Python"
```

#### 添加新 Provider
1. 在 `backend/app/memory/llms/` (或 `embeddings/`, `vector_stores/`) 创建新文件 (继承 `base.py`)
2. 在对应 `configs/` 子目录添加配置类
3. 在 `utils/__init__.py` 的 config 构建逻辑中添加 provider 分支

### 覆盖率策略
- 当前只对特定模块强制 100% 覆盖率:
  - `app.core.error_handling`
  - `app.services.mentions`
- 运行 `make backend-coverage` 查看覆盖率报告
- 覆盖率报告生成在 `backend/coverage.xml` 和 `backend/coverage.json`

## Git 工作流

### Conventional Commits
遵循项目的 commit 历史模式:
- `feat: ...` - 新功能
- `fix: ...` - bug 修复
- `docs: ...` - 文档更新
- `test(core): ...` - 测试相关 (可指定作用域)
- `refactor: ...` - 代码重构

### Pull Request 指南
- 保持 PR 专注且基于最新的 `master` 分支
- 包含以下信息:
  - 变更内容和原因
  - 测试证据 (`make check` 或相关命令输出)
  - 关联的 issue
  - UI 或工作流变更时的截图/日志

## 重要路径和文件

### 配置文件
- `backend/pyproject.toml` - Python 项目配置和工具设置
- `frontend/package.json` - Node.js 依赖和脚本
- `compose.yml` - Docker Compose 配置
- `.env.example` - 环境变量模板

### 关键代码文件
- `backend/app/main.py` - FastAPI 应用入口和路由注册
- `backend/app/core/config.py` - 配置管理 (Pydantic Settings)
- `backend/app/core/auth.py` - 认证逻辑
- `backend/app/core/error_handling.py` - 统一错误处理
- `frontend/src/proxy.ts` - API 代理配置

### Memory 模块关键文件
- `backend/app/memory/core/engine.py` - Memory 引擎核心 (add/search/get/update/delete)
- `backend/app/memory/core/graph_memory.py` - Neo4j 图记忆 (纯 Cypher 余弦相似度)
- `backend/app/memory/providers/factory.py` - Provider 工厂 (LLM/Embedder/VectorStore)
- `backend/app/memory/services/memory_worker.py` - 后台 Worker (fact extraction + graph build)
- `backend/app/memory/services/client_factory.py` - Memory 客户端工厂 (get_memory_client)
- `backend/app/memory/ailearn/orchestrator.py` - AI Learn 编排器

### Memory API 端点 (按消费者组织)
- `backend/app/api/memory/adapter_compat.py` - 适配器兼容路由 (v1/v2 映射)
- `backend/app/api/memory/adapter_turns.py` - 适配器 Turn 存储
- `backend/app/api/memory/frontend_views.py` - MC 前端记忆页面
- `backend/app/api/memory/frontend_ailearn.py` - MC 前端 AI Learn 页面
- `backend/app/api/memory/internal_crud.py` - 内部 Memory CRUD

### 适配器 (Adapters)
- `adapters/claude-code/` - Claude Code hooks (UserPromptSubmit 召回 + Stop 存储)
- `adapters/openclaw/` - OpenClaw TypeScript 插件 (before_agent_start 召回 + agent_end 存储)

### 文档
- `docs/README.md` - 文档导航
- `docs/getting-started/` - 入门指南
- `docs/development/` - 开发指南
- `docs/deployment/` - 部署文档

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
- 查看前端 `orval.config.ts` 配置

### Memory Worker 问题

Worker 在 FastAPI startup 时通过后台线程启动 (`app/main.py`)，每 5 秒轮询 pending turns。

```bash
# 查看 Worker 日志
grep -i "memory_worker\|Fact extraction\|Turn.*process" ~/.openclaw/logs/mc-backend.log | tail -20

# 检查 pending turns
curl -s "http://localhost:8000/api/v2/turns/?user_id=yishu&limit=5" | jq '.items[] | {id: .id[:8], processing_status, source}'

# 检查 memory client
curl -s "http://localhost:8000/api/v1/memories?user_id=yishu" | jq '.total'
```

常见问题：
- `LLM_API_KEY` 未设置 → Worker 运行但 fact extraction 全部失败
- Qdrant 未启动 → Memory client 初始化失败
- Neo4j 未启动 → 图谱功能自动跳过 (graceful degradation)

### Docker 构建问题
- 完全重新构建: `docker compose -f compose.yml --env-file .env build --no-cache --pull`
- 查看日志: `docker compose -f compose.yml --env-file .env logs -f`

---

## Memory 模块架构

### 概览

Memory 模块位于 `backend/app/memory/`，提供 AI Agent 持久化记忆能力。从原 mem0 项目完整迁移而来。

```
backend/app/memory/                   # 9 个顶层包，三大分区
├── __init__.py                       # 公共 API (导出 Memory)
├── exceptions.py                     # 结构化异常
│
├── core/                             # ① 核心引擎 (做什么)
│   ├── engine.py                     #   Memory 类 (add/search/get/update/delete)
│   ├── base.py                       #   MemoryBase ABC
│   ├── graph_memory.py               #   Neo4j 图记忆
│   ├── storage.py                    #   SQLite 存储层
│   ├── setup.py                      #   初始化
│   └── utils.py                      #   工具函数
│
├── providers/                        # ② 可插拔 Providers (用什么)
│   ├── factory.py                    #   Provider 工厂 (LLM/Embedder/VectorStore/Graph)
│   ├── llms/                         #   21 LLM providers (Anthropic, OpenAI, DeepSeek 等)
│   ├── embeddings/                   #   13 嵌入 providers (OpenAI, HF, Gemini, Ollama 等)
│   ├── vector_stores/                #   27 向量存储 backends (Qdrant 为主)
│   └── graphs/                       #   图数据库 providers (Neo4j, Neptune)
│
├── configs/                          #   配置定义 (被 core + providers 共用)
│   ├── base.py, prompts.py, enums.py
│   ├── llms/, embeddings/, vector_stores/, rerankers/
│
├── ailearn/                          # ③ AI Learn 管道 (怎么学)
│   ├── orchestrator.py               #   编排器 (EnhancedAILearn)
│   ├── observation/                  #   阶段 1: 观察 (collectors, filters, hooks, storage)
│   ├── learning/                     #   阶段 2: 学习 (pattern_detector, skill_extractor)
│   ├── instincts/                    #   阶段 3: 直觉 (auto_applier, decay)
│   ├── amendment/                    #   阶段 4: 修订 (proposer)
│   ├── evolution/                    #   阶段 5: 进化 (health_monitor, metrics)
│   └── quality/                      #   阶段 6: 质量 (auditor, dashboard)
│
├── models/                           #   SQLModel (Turn, VectorMemory)
├── schemas/                          #   Pydantic v2 API schemas
├── client/                           #   REST 客户端 SDK
└── services/                         #   后台服务
    ├── memory_worker.py              #   Worker (fact extraction + graph build)
    └── client_factory.py             #   客户端工厂 (get_memory_client)
```

### 数据流

```
┌─────────────────────────────────────────────────────────────────┐
│  插件层 (Claude Code hooks / OpenClaw TypeScript 插件)           │
│  HTTP → POST http://localhost:8000/api/v2/turns/               │
└────────────────────────────┬────────────────────────────────────┘
                             │
                             ↓
┌─────────────────────────────────────────────────────────────────┐
│  MC Backend (FastAPI :8000)                                      │
│  兼容路由 → /memory/turns/ → Worker 队列                         │
└────────────────────────────┬────────────────────────────────────┘
                             │
         ┌───────────────────┼───────────────────┐
         ↓                   ↓                   ↓
┌──────────────┐    ┌──────────────┐    ┌──────────────┐
│  PostgreSQL  │    │   Qdrant     │    │    Neo4j     │
│  (SQLModel)  │    │  向量数据库   │    │   图数据库    │
│  turns       │    │  :6333       │    │  :7687       │
│  memories    │    │  memories    │    │  实体 + 关系  │
│  metadata    │    │  1536 维向量  │    │              │
└──────────────┘    └──────────────┘    └──────────────┘
```

### API 路由映射

| 客户端 | 路由 | 用途 |
|--------|------|------|
| Claude Code hooks | `POST /api/v2/turns/` | 存储对话轮次 |
| Claude Code hooks | `GET /api/v2/memories/search` | 召回相关记忆 |
| OpenClaw 插件 | `POST /api/v2/turns/` | 存储对话轮次 |
| OpenClaw 插件 | `GET /api/v2/memories/search` | 召回相关记忆 |
| 前端 Memories 页 | `GET /api/v1/memories` | 记忆列表 |
| 前端 Graph 页 | `GET /api/v1/graph` | 图数据 |
| 前端 AILearn 页 | `GET /api/v1/ailearn/status` | 学习状态 |
| 内部路由 | `/memory/turns/`, `/memory/memories/` | 原始 CRUD |

### 外部依赖

| 服务 | 端口 | 容器 | 用途 |
|------|------|------|------|
| Qdrant | 6333 | qdrant | 向量存储 |
| Neo4j | 7687 | neo4j-mem0 | 图数据库 |

> **注意**: Qdrant 和 Neo4j 不在 `compose.yml` 中，需单独运行：
> ```bash
> # Qdrant
> docker run -d --name qdrant -p 6333:6333 -v qdrant_data:/qdrant/storage qdrant/qdrant
> # Neo4j
> docker run -d --name neo4j-mem0 -p 7687:7687 -p 7474:7474 \
>   -e NEO4J_AUTH=neo4j/mem0password neo4j:5
> ```

### AI Learn 管道

AI Learn 是自主学习引擎，位于 `backend/app/memory/ailearn/enhanced.py`，通过六层管道处理观察数据：

1. **Observation** (观察) → 捕获对话 turn，过滤隐私 (`observation/filters/privacy_filter.py`)
2. **Learning** (学习) → 检测模式 (`learning/pattern_detector.py`)，提取技能 (`learning/skill_extractor.py`)
3. **Instincts** (直觉) → 自动应用规则 (`instincts/auto_applier.py`)，衰减过期知识 (`instincts/decay.py`)
4. **Amendment** (修订) → 提出记忆修正建议 (`amendment/proposer.py`)
5. **Evolution** (进化) → 追踪变化 (`evolution/evolution_tracker.py`)，监控健康 (`evolution/health_monitor.py`)
6. **Quality** (质量) → 审计质量 (`quality/auditor.py`)，展示仪表板 (`quality/dashboard.py`)

API: `POST /api/v1/ailearn/start`、`GET /api/v1/ailearn/status`

### 查看数据库状态

```bash
# Qdrant
curl -s http://127.0.0.1:6333/collections | jq

# Neo4j
docker exec neo4j-mem0 cypher-shell -u neo4j -p mem0password \
  "MATCH (n) RETURN labels(n) as label, count(*) as count ORDER BY count DESC;"

# MC 后端健康检查
curl http://localhost:8000/healthz
```

### 适配器开发说明

**Claude Code 适配器** (`adapters/claude-code/`):
- `config.sh` - 配置 (API URL, user_id, source)
- `mem0-retrieve.sh` - UserPromptSubmit hook，搜索相关记忆注入上下文
- `mem0-store.sh` - Stop hook，异步存储对话到 turns
- `install.sh` / `install-project.sh` - 安装脚本，写入 `~/.claude/settings.json`

**OpenClaw 适配器** (`adapters/openclaw/`):
- `index.ts` - 插件入口 (before_agent_start 召回 + agent_end 存储)
- `config.ts` - 配置管理
- `providers.ts` - Provider 注册
- `provider.ts` - 核心 Provider 实现
- 默认 API: `http://localhost:8000`
