# Memory Module

> 从 CLAUDE.md 提取的详细文档。概览见项目根目录 `CLAUDE.md` 的模块索引表。

## 概述

Memory 模块位于 `backend/app/memory/`，提供 AI Agent 持久化记忆能力。从原 mem0 项目完整迁移而来。

## 架构 (三大分区)

```
backend/app/memory/                   # 9 个顶层包
├── __init__.py                       # 公共 API (导出 Memory)
├── exceptions.py                     # 结构化异常
│
├── core/                             # 1. 核心引擎 (做什么)
│   ├── engine.py                     #   Memory 类 (add/search/get/update/delete)
│   ├── base.py                       #   MemoryBase ABC
│   ├── graph_memory.py               #   Neo4j 图记忆
│   ├── storage.py                    #   SQLite 存储层
│   ├── setup.py                      #   初始化
│   └── utils.py                      #   工具函数
│
├── providers/                        # 2. 可插拔 Providers (用什么)
│   ├── factory.py                    #   Provider 工厂 (LLM/Embedder/VectorStore/Graph)
│   ├── llms/                         #   21 LLM providers (Anthropic, OpenAI, DeepSeek 等)
│   ├── embeddings/                   #   13 嵌入 providers (OpenAI, HF, Gemini, Ollama 等)
│   ├── vector_stores/                #   27 向量存储 backends (Qdrant 为主)
│   └── graphs/                       #   图数据库 providers (Neo4j, Neptune)
│
├── configs/                          #   配置定义 (被 core + providers 共用)
│   ├── base.py, prompts.py, enums.py
│   └── llms/, embeddings/, vector_stores/, rerankers/
│
├── ailearn/                          # 3. AI Learn 管道 (怎么学)
│   ├── orchestrator.py               #   编排器 (EnhancedAILearn)
│   ├── observation/                  #   阶段 1: 观察 (collectors, filters, hooks, storage)
│   ├── learning/                     #   阶段 2: 学习 (pattern_detector, skill_extractor)
│   ├── instincts/                    #   阶段 3: 直觉 (auto_applier, decay)
│   ├── amendment/                    #   阶段 4: 修订 (proposer)
│   ├── evolution/                    #   阶段 5: 进化 (health_monitor, metrics)
│   └── quality/                      #   阶段 6: 质量 (auditor, dashboard)
│
├── models/                           #   SQLModel (Turn, VectorMemory, TaskSegment)
├── schemas/                          #   Pydantic v2 API schemas
├── client/                           #   REST 客户端 SDK
└── services/                         #   后台服务
    ├── memory_worker.py              #   Worker (batch + concurrent sessions + task segmentation)
    ├── task_segmenter.py             #   任务分段 (启发式 + LLM 可选)
    └── client_factory.py             #   客户端工厂 (get_memory_client)
```

## 数据流

```
┌─────────────────────────────────────────────────────────────────┐
│  插件层 (Claude Code hooks / OpenClaw TypeScript 插件)           │
│  HTTP → POST http://localhost:8000/api/v2/turns/               │
│  messages: [{role, content: string | ContentBlock[]}]           │
└────────────────────────────┬────────────────────────────────────┘
                             │
                             ↓
┌─────────────────────────────────────────────────────────────────┐
│  MC Backend (FastAPI :8000)                                      │
│  兼容路由 → /memory/turns/ → Worker 队列                         │
│  Worker: batch N turns → group by session → concurrent process  │
│    per-turn: extract_text → Memory Engine (fact/summary/graph)  │
│    per-session: TaskSegmenter → task_segments 表                 │
└────────────────────────────┬────────────────────────────────────┘
                             │
         ┌───────────────────┼───────────────────┐
         ↓                   ↓                   ↓
┌──────────────┐    ┌──────────────┐    ┌──────────────┐
│  PostgreSQL  │    │   Qdrant     │    │    Neo4j     │
│  turns       │    │  :6333       │    │  :7687       │
│  task_segments│    │  1536 维向量  │    │  实体 + 关系  │
│  vector_mem  │    │              │    │              │
└──────────────┘    └──────────────┘    └──────────────┘
```

### 消息格式

Turn.messages 支持两种 content 格式 (向下兼容):

```typescript
// 纯文本 (旧格式)
{ role: "user", content: "查看配置文件" }

// 结构化 (新格式，含 tool_use/tool_result)
{ role: "assistant", content: [
  { type: "text", text: "让我读取配置。" },
  { type: "tool_use", id: "call_1", name: "Read", input: { file_path: "/app/config.py" } }
]}
{ role: "user", content: [
  { type: "tool_result", tool_use_id: "call_1", content: "DEBUG=true" }
]}
```

适配器截断策略: tool_result.content max 4000 chars, tool_use.input max 2000 chars, text max 4000 chars。
Worker 通过 `extract_text_from_messages()` (`memory_worker.py`) 将结构化消息转为纯文本后再喂给 Memory Engine。

## API 路由映射

| 消费者 | 路由 | 用途 | 代码 |
|--------|------|------|------|
| Claude Code hooks | `POST /api/v2/turns/` | 存储对话轮次 | `api/memory/adapter_turns.py` |
| Claude Code hooks | `GET /api/v2/memories/search` | 召回记忆 | `api/memory/adapter_compat.py` |
| OpenClaw 插件 | `POST /api/v1/turns/` | 存储对话轮次 | `api/memory/adapter_compat.py` |
| OpenClaw 插件 | `GET /api/v2/memories/search` | 召回记忆 | `api/memory/adapter_compat.py` |
| 前端 Memories 页 | `GET /api/v1/memories` | 记忆列表 | `api/memory/frontend_views.py` |
| 前端 Memory 详情 | `GET /api/v2/turns/{turn_id}` | Turn 详情 | `api/memory/adapter_compat.py` |
| 前端 Memory 详情 | `GET /api/v2/memories/?turn_id=X` | 同 Turn 记忆 | `api/memory/adapter_compat.py` |
| 前端 Graph 页 | `GET /api/v1/graph` | 图数据 | 同上 |
| 前端 AILearn 页 | `GET /api/v1/ailearn/status` | 学习状态 | `api/memory/frontend_ailearn.py` |
| 内部路由 | `/memory/turns/`, `/memory/memories/` | 原始 CRUD | `api/memory/internal_crud.py` |

## 前端页面 (`frontend/src/app/memories/page.tsx`)

三个视图 Tab: 列表 / 图谱 / AI 学习

### 列表视图
- 记忆卡片: 内容 + source 徽章 + memory_type 徽章 (事实/摘要) + agent + 时间
- 筛选: 按来源 (OpenClaw/Claude Code) + 按 Agent
- 搜索: 关键词搜索 (`api/memory/internal_crud.py:search_memories`)
- 详情 Dialog: 点击卡片 → 完整内容 + Turn 关联 (session/status/messages/同 Turn 记忆)
  - 消息渲染: `MessageContent` 组件兼容 string 和 ContentBlock[] 两种 content 格式
  - 工具调用: `ToolCallBlock` 组件 — tool_use (amber, 🔧 工具名 + 可折叠参数) / tool_result (green, 📋 可折叠结果)
  - tool call 计数 badge 显示在 assistant 消息头部

### 图谱视图 (`frontend/src/components/molecules/MemoryGraph.tsx`)
- Force-directed graph (react-force-graph-2d)
- Agent 筛选: 选中后重新请求 API，关系统计和 chips 动态更新 (`adapter_compat.py` Cypher 按 `agent_id` 过滤)
- 来源筛选: 按 source (OpenClaw/Claude Code) 过滤，选中后将匹配的 agent_ids 传入 API
- 关系类型筛选: 点击 chip 高亮/过滤特定关系类型
- 搜索: 节点名称搜索

### AI 学习视图 (`frontend/src/components/molecules/AILearnView.tsx`)
- 状态: observations / patterns / skills / health

## 关键文件

| 文件 | 作用 |
|------|------|
| `memory/core/engine.py` | Memory 引擎核心 (add/search/get/update/delete) |
| `memory/core/graph_memory.py` | Neo4j 图记忆 (纯 Cypher 余弦相似度) |
| `memory/providers/factory.py` | Provider 工厂 (LLM/Embedder/VectorStore) |
| `memory/services/memory_worker.py` | 后台 Worker (batch + concurrent sessions + task segmentation) |
| `memory/services/task_segmenter.py` | 任务分段服务 (启发式 + LLM 可选) |
| `memory/services/client_factory.py` | Memory 客户端工厂 (get_memory_client) |
| `memory/models/__init__.py` | SQLModel: Turn, VectorMemory, TaskSegment |
| `memory/ailearn/orchestrator.py` | AI Learn 编排器 (EnhancedAILearn) |
| `memory/core/base.py` | MemoryBase 抽象基类 |
| `memory/core/storage.py` | 存储层 |
| `memory/core/setup.py` | 初始化逻辑 |
| `api/memory/adapter_compat.py` | 插件兼容路由 (v1/v2) |
| `api/memory/adapter_turns.py` | Turn 存储 API (v2) |
| `api/memory/frontend_views.py` | 前端记忆可视化 API |

## 环境变量

配置定义在 `backend/app/memory/services/client_factory.py` 的 `get_default_memory_config()` 中。

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
| `NEO4J_URI` | (空) | Neo4j URI (设置后启用图谱) |
| `NEO4J_USERNAME` | `neo4j` | Neo4j 用户名 |
| `NEO4J_PASSWORD` | (空) | Neo4j 密码 |
| `OLLAMA_BASE_URL` | (空) | Ollama API 地址 |
| `WORKER_BATCH_SIZE` | `10` | Worker 每次轮询取出的 pending turns 数 |
| `WORKER_MAX_CONCURRENT_SESSIONS` | `5` | Worker 并发处理的 session 数上限 |
| `TASK_SEGMENTER_USE_LLM` | `false` | 是否启用 LLM 增强任务分段 |

## 外部依赖

| 服务 | 端口 | 容器 | 用途 |
|------|------|------|------|
| Qdrant | 6333 | qdrant | 向量存储 |
| Neo4j | 7687 | neo4j-mem0 | 图数据库 |

> Qdrant 和 Neo4j 不在 `compose.yml` 中，需单独运行。启动命令见 [database.md](./database.md#docker-commands)。

## AI Learn 管道

AI Learn 是自主学习引擎，位于 `backend/app/memory/ailearn/orchestrator.py`，通过六层管道处理观察数据：

1. **Observation** (观察) → 捕获对话 turn，过滤隐私 (`observation/filters/privacy_filter.py`)
2. **Learning** (学习) → 检测模式 (`learning/pattern_detector.py`)，提取技能 (`learning/skill_extractor.py`)
3. **Instincts** (直觉) → 自动应用规则 (`instincts/auto_applier.py`)，衰减过期知识 (`instincts/decay.py`)
4. **Amendment** (修订) → 提出记忆修正建议 (`amendment/proposer.py`)
5. **Evolution** (进化) → 追踪变化 (`evolution/evolution_tracker.py`)，监控健康 (`evolution/health_monitor.py`)
6. **Quality** (质量) → 审计质量 (`quality/auditor.py`)，展示仪表板 (`quality/dashboard.py`)

API: `POST /api/v1/ailearn/start`、`GET /api/v1/ailearn/status`

## 开发工作流

### 手动测试 Memory 功能
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

### 添加新 Provider
1. 在 `backend/app/memory/providers/llms/` (或 `embeddings/`, `vector_stores/`) 创建新文件 (继承 `base.py`)
2. 在对应 `configs/` 子目录添加配置类
3. 在 `services/client_factory.py` 的 config 构建逻辑中添加 provider 分支

## 故障排查

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

## 数据库检查

```bash
# Qdrant
curl -s http://127.0.0.1:6333/collections | jq

# Neo4j
docker exec neo4j-mem0 cypher-shell -u neo4j -p mem0password \
  "MATCH (n) RETURN labels(n) as label, count(*) as count ORDER BY count DESC;"

# MC 后端健康检查
curl http://localhost:8000/healthz
```

## 相关文档

- [Adapters](./adapters.md) — 喂入 Memory 的适配器
- [Database](./database.md) — 底层存储详情
- [API Reference](../reference/api.md) — REST API 通用约定
- [Testing](/memory-e2e-testing) — Memory E2E 测试 Skill
