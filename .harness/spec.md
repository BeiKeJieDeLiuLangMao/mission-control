# Spec: Phase 3 — 智能并发召回 API

## 背景

Phase 1 修复了搜索从 SQL LIKE → Qdrant 向量搜索。Phase 2 添加了 TaskSegment + Worker 并发。
当前问题：召回只有单一的 Qdrant 向量搜索（`GET /api/v2/memories/search`），没有图谱搜索、没有纠正/流程优先排序、没有 context budget 控制、没有超时保护。搜索延迟 10-20s（E2E 发现）。

**Phase 3 目标**：新建 `POST /api/v2/recall` 端点，三阶段并发召回，替代简单搜索。向后兼容：现有 `GET /api/v2/memories/search` 保留不动。

## 功能列表

1. **RecallOrchestrator 服务** — 并发协调 Qdrant 向量搜索 + Neo4j 图遍历 + 纠正/流程专项查询，合并去重排序
2. **QueryAnalyzer** — 规则式查询分析（无 LLM），提取意图、实体、文件路径，<100ms
3. **POST /api/v2/recall 端点** — 接受 query/user_id/agent_id/context_budget_tokens/timeout_ms，返回结构化 context_text + sources
4. **适配器升级** — Claude Code `mem0-retrieve.sh` 和 OpenClaw `provider.ts` 调用新 recall API
5. **UniqueViolation 修复** — 随此 commit 一起提交（已在工作区中修复）

## 涉及文件

| 文件 | 变更 |
|------|------|
| `backend/app/memory/services/recall_orchestrator.py` | **新建** — RecallOrchestrator + QueryAnalyzer |
| `backend/app/api/memory/intelligent_recall.py` | **新建** — POST /api/v2/recall 端点 |
| `backend/app/api/memory/adapter_compat.py` | 修改 — 注册 recall 路由 |
| `backend/app/core/config.py` | 修改 — 新增 RECALL_* 配置 |
| `backend/app/memory/services/memory_worker.py` | 修改 — UniqueViolation 修复（已在工作区） |
| `adapters/claude-code/mem0-retrieve.sh` | 修改 — 调用 POST /api/v2/recall |
| `adapters/claude-code/lib/api.sh` | 修改 — 新增 recall_memories() 函数 |
| `adapters/openclaw/provider.ts` | 修改 — 新增 recall() 方法 |
| `adapters/openclaw/index.ts` | 修改 — before_agent_start 调用 recall() |

## 技术方案

### 三阶段并发召回架构

```
Stage 1: Query Analysis (<100ms, 纯 regex)
  → intent: question / task / debug / config / general
  → entities: 文件路径、函数名、错误消息
  → complexity: simple / moderate / complex

Stage 2: Parallel Context Assembly (asyncio.gather, per-source timeout)
  ├─ Task A: Qdrant 向量搜索 (语义相似, timeout 3s)
  ├─ Task B: Neo4j 图遍历 2-hop (实体关系, timeout 3s, 可选)
  └─ Task C: Qdrant 过滤搜索 (memory_type=correction, timeout 2s)

Stage 3: Merge + Rank + Format (<100ms, 内存操作)
  → 优先级: corrections > high-score vectors > graph relations > summaries > facts
  → 内容去重 (content hash)
  → context_budget_tokens 截断
  → 结构化输出
```

### 性能预算

| 阶段 | 目标 | 超时 |
|------|------|------|
| Query Analysis | <100ms | N/A（纯 regex） |
| Qdrant Vector | <3000ms | 超时返回空 |
| Neo4j Graph | <3000ms | 超时返回空 |
| Correction Lookup | <2000ms | 超时返回空 |
| Merge + Format | <100ms | N/A（内存） |
| **总计** | **<5000ms** | 渐进降级 |

### 向后兼容

- `GET /api/v2/memories/search` 保留不变（Phase 1 的向量搜索）
- 新增 `POST /api/v2/recall` 作为增强入口
- 适配器优先调用 recall，失败则 fallback 到 search

### 适配器升级策略

**Claude Code** (`mem0-retrieve.sh`):
- 新增 `recall_memories()` 函数调用 `POST /api/v2/recall`
- 解析响应的 `context_text` 字段（纯文本，直接输出）
- Fallback: 如果 recall 失败，调用原有 `search_memories()`

**OpenClaw** (`provider.ts` + `index.ts`):
- `provider.ts` 新增 `recall()` 方法
- `index.ts` 的 `before_agent_start` hook 优先调用 `recall()`
- Fallback: recall 失败 → 原有 `search()` 链路

## 文档更新

- `docs/modules/memory.md` — API 路由映射表新增 recall 端点 + 架构图更新 + 环境变量
- `.env.example` — RECALL_* 配置项
- `docs/modules/adapters.md` — 协议说明更新

## 测试策略

- 后端: pytest 测试 QueryAnalyzer 规则（纯函数，无外部依赖）
- E2E: `/memory-e2e-testing` 验证完整链路
- 适配器: 手动 curl 验证 POST /api/v2/recall 响应格式
