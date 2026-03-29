# Adapters

> 适配器将外部 AI 工具连接到 Mission Control 的 Memory 系统。

## 概述

两个适配器通过统一的 HTTP API 将对话数据送入 Memory 系统：
- **Claude Code** — Shell hooks (UserPromptSubmit 召回 + Stop 存储)
- **OpenClaw** — TypeScript 插件 (before_agent_start 召回 + agent_end 存储)

## Claude Code 适配器 (`adapters/claude-code/`)

| 文件 | 作用 |
|------|------|
| `config.sh` | 配置 (API URL, user_id, source) |
| `mem0-retrieve.sh` | UserPromptSubmit hook — 搜索相关记忆注入上下文 |
| `mem0-store.sh` | Stop hook — 异步存储对话到 turns |
| `install.sh` | 全局安装 (写入 `~/.claude/settings.json`) |
| `install-project.sh` | 项目级安装 (写入 `.claude/settings.json`) |
| `lib/api.sh` | HTTP API 封装 (search, store, health) |
| `test-plugin-full.sh` | 完整插件集成测试脚本 |

### Hook 生命周期
```
用户发送消息
  → UserPromptSubmit hook → mem0-retrieve.sh → POST /api/v2/recall (智能并发召回)
  → fallback: GET /api/v2/memories/search (向量搜索)
  → Claude 收到增强上下文
  → Claude 响应
  → Stop hook (async) → mem0-store.sh → POST /api/v2/turns/
  → Worker 处理: fact extraction → graph build
```

### 消息格式
`mem0-store.sh` 保留完整 LLM 消息结构 (`parse_transcript` 函数):
- **text block**: 截断 4000 chars
- **tool_use block**: 保留 name/id/input (input serialize → 2000 chars)
- **tool_result block**: 保留 tool_use_id/content (content → 4000 chars)
- **thinking block**: 过滤
- 字符串 content: 沿用旧逻辑 (ANSI 清理 + 截断)

### Hook 配置 (`.claude/settings.json`)
- **UserPromptSubmit**: timeout 30s (同步，需等待向量搜索)
- **Stop**: timeout 60s, async=true (不阻塞)

详细用法见 `adapters/claude-code/README.md`。

## OpenClaw 适配器 (`adapters/openclaw/`)

| 文件 | 作用 |
|------|------|
| `index.ts` | 插件入口 (40KB，含 5 个 tools + 生命周期 hooks) |
| `config.ts` | 配置解析 (env var 引用、默认值) |
| `providers.ts` | Provider 工厂 |
| `provider.ts` | OpenMemoryProvider HTTP 实现 |
| `filtering.ts` | 消息噪音过滤 (心跳、确认、系统消息) |
| `isolation.ts` | 多 Agent 内存隔离 (per-agent userId 命名空间) |
| `types.ts` | TypeScript 类型定义 |

### Hook 生命周期
```
Agent 请求到达
  → before_agent_start → POST /api/v2/recall (智能并发召回)
  → fallback: GET /api/v2/memories/search (向量搜索)
  → Agent 执行
  → agent_end → POST /api/v2/turns/ (结构化消息)
  → Worker → extract_text_from_messages() → fact extraction + graph build
```

### 消息存储
`agent_end` hook 通过 `provider.recordTurn()` 发送一次结构化消息 (含 tool_use/tool_result blocks)，存入 Turn。
Worker 自动从结构化消息中提取纯文本进行 fact extraction，不再需要单独的 `/api/v1/memories/` POST。

### Agent Tools
`memory_search`, `memory_store`, `memory_list`, `memory_get`, `memory_forget`

详细用法见 `adapters/openclaw/README.md`。

## 适配器与 Memory 的关系

两个适配器都调用相同的 API 端点：
- **存储**: `POST /api/v2/turns/` → Worker 异步处理 → Qdrant + Neo4j
- **召回** (优先): `POST /api/v2/recall` → 智能并发召回 (Qdrant + Neo4j + corrections)
- **召回** (fallback): `GET /api/v2/memories/search` → 向量相似度搜索

API 端点实现见 `backend/app/api/memory/adapter_*.py`。

## 相关文档

- [Memory Module](./memory.md) — Memory 架构和数据流
- [Database](./database.md) — 底层存储
- [API Reference](../reference/api.md) — REST API 约定
- [Plugin Testing](/claude-code-plugin-testing) — 插件测试 Skill
