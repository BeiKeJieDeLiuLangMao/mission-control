---
name: memory-e2e-testing
description: E2E testing for OpenClaw and Claude Code memory pipeline (Turn → Worker → Qdrant + Neo4j + AI Learn)
version: 3.0.0
---

# Memory E2E Testing

## 概述

验证 OpenClaw 和 Claude Code 通过 MC 后端存储记忆的完整端到端流程：
- Turn 记录写入
- Worker 异步处理 (fact extraction + graph build)
- Qdrant 向量存储
- Neo4j 图数据库
- 前端展示

## 架构

```
┌─────────────────────────────────────────────────────────────────┐
│  OpenClaw CLI            Claude Code CLI                        │
│  openclaw agent           claude --print                        │
│       │                        │                                │
│       ↓                        ↓                                │
│  ┌──────────────────────────────────────┐                      │
│  │          插件 / hooks 适配层          │                      │
│  │  OpenClaw: adapters/openclaw/ (TS)   │                      │
│  │  Claude:   adapters/claude-code/ (sh)│                      │
│  └──────────────────────────────────────┘                      │
│                         │                                      │
│                         ↓                                      │
│              ┌──────────────────────┐                          │
│              │  MC Backend :8000    │                          │
│              │  /api/v2/turns/      │                          │
│              │  → Worker 队列       │                          │
│              └──────────────────────┘                          │
│                   │          │          │                      │
│                   ↓          ↓          ↓                      │
│             ┌─────────┐ ┌─────────┐ ┌─────────┐              │
│             │ Postgres│ │ Qdrant  │ │ Neo4j   │              │
│             │ turns   │ │ vectors │ │ graph   │              │
│             └─────────┘ └─────────┘ └─────────┘              │
└─────────────────────────────────────────────────────────────────┘
```

## 测试流程

### Phase 1: 前置条件

```bash
echo "=== 服务状态检查 ===" && \
curl -sf http://localhost:8000/healthz && echo " ✓ MC Backend" && \
curl -sf http://127.0.0.1:6333/collections && echo " ✓ Qdrant" && \
docker ps --filter name=neo4j --format "{{.Names}}: {{.Status}}" && echo " ✓ Neo4j"

# 记录基线
curl -s "http://localhost:8000/api/v1/memories?user_id=yishu" | jq '{total: .total}'
curl -s "http://localhost:8000/api/v2/turns/?user_id=yishu" | jq '{total: .total}'
docker exec neo4j-mem0 cypher-shell -u neo4j -p mem0password "MATCH (n) RETURN count(n)" 2>/dev/null
```

### Phase 2: OpenClaw 端测试

```bash
# 存储测试
openclaw agent --agent main --message "记住：用户王五，电话 139-0000-5678，职位是后端工程师" --thinking low

# 等待 Worker 处理
sleep 10

# 验证 Turn
curl -s "http://localhost:8000/api/v2/turns/?user_id=yishu&limit=3" | \
  jq '.items[] | {id: .id[:8], source, created_at}'

# 验证 Memory
curl -s "http://localhost:8000/api/v1/memories?user_id=yishu&limit=5" | \
  jq '.items[] | {content: .content[:40], memory_type, source}'
```

### Phase 3: Claude Code 端测试

```bash
mkdir -p /tmp/mc-test-project && cd /tmp/mc-test-project

# 存储测试
echo "请记住我喜欢用 Neovim 作为主要编辑器" | claude --print --no-input 2>&1
sleep 10

# 验证
curl -s "http://localhost:8000/api/v2/turns/?user_id=yishu&limit=3" | \
  jq '.items[] | {id: .id[:8], source, created_at}'
curl -s "http://localhost:8000/api/v1/memories?user_id=yishu&limit=5" | \
  jq '.items[] | {content: .content[:50], memory_type, source}'
```

### Phase 4: 图谱验证

```bash
# 节点统计
docker exec neo4j-mem0 cypher-shell -u neo4j -p mem0password \
  "MATCH (n) RETURN labels(n)[0] as label, count(*) as cnt ORDER BY cnt DESC LIMIT 10" 2>/dev/null

# 关系统计
docker exec neo4j-mem0 cypher-shell -u neo4j -p mem0password \
  "MATCH ()-[r]->() RETURN type(r) as rel_type, count(*) as cnt ORDER BY cnt DESC LIMIT 10" 2>/dev/null

# Graph API
curl -s "http://localhost:8000/api/v1/graph/stats" | jq
```

### Phase 5: AI Learn 管道测试

```bash
# 启动 AI Learn
curl -X POST http://localhost:8000/api/v1/ailearn/start
sleep 15

# 检查状态
curl -s http://localhost:8000/api/v1/ailearn/status | jq '{status, patterns_detected, skills_extracted}'
```

### Phase 6: 搜索质量验证

```bash
# 语义搜索应返回相关结果
QUERY="王五 电话"
curl -s "http://localhost:8000/api/v2/memories/search?query=${QUERY}&user_id=yishu&limit=3" | \
  jq '.items[] | {content: .content[:60], score}'

# 验证: score > 0.5 表示语义相关
```

### Phase 7: 前端验证

```bash
open http://localhost:3000/memories
```

- 记忆列表加载正常
- 搜索功能工作
- Graph 标签页显示 Neo4j 数据

### Phase 8: 数据比对报告

```bash
echo "============================================"
echo "       MEMORY E2E TEST VERIFICATION"
echo "============================================"

echo -e "\n[1] Memories"
curl -s "http://localhost:8000/api/v1/memories?user_id=yishu" | \
  jq '{total: .total}'

echo -e "\n[2] Turns"
curl -s "http://localhost:8000/api/v2/turns/?user_id=yishu" | \
  jq '{total: .total}'

echo -e "\n[3] Neo4j Graph"
docker exec neo4j-mem0 cypher-shell -u neo4j -p mem0password \
  "MATCH (n) RETURN count(n) as nodes" 2>/dev/null
docker exec neo4j-mem0 cypher-shell -u neo4j -p mem0password \
  "MATCH ()-[r]->() RETURN count(r) as relations" 2>/dev/null

echo -e "\n============================================"
```

## 验证标准

| Phase | 测试项 | 通过标准 | 失败处理 |
|-------|--------|---------|---------|
| 1 | 服务健康 | 3 个服务均 HTTP 200 | 中止，修复基础设施 |
| 2 | OpenClaw Turn | source="openclaw" 的 turn 存在 | 检查 adapter 配置 |
| 3 | Claude Code Turn | source="claude-code" 的 turn 存在 | 检查 hook 路径、timeout |
| 4 | Worker 处理 | processing_status=completed (60s 内) | 检查 LLM_API_KEY、Qdrant |
| 5 | AI Learn | 状态 API 返回 patterns/skills | 检查 ailearn 路由 |
| 6 | 向量搜索 | 结果非空且 score > 0.5 | 检查 embedder 配置 |
| 7 | Neo4j 图节点 | 新增实体节点 | 检查 NEO4J_URI |
| 8 | 前端渲染 | 记忆列表正常，source 正确 | 检查前端 API 调用 |

## 关键文件

| 文件 | 作用 |
|------|------|
| `adapters/openclaw/index.ts` | OpenClaw 插件入口 |
| `adapters/openclaw/provider.ts` | 核心 Provider 实现 |
| `adapters/claude-code/mem0-store.sh` | Claude Code 存储 Hook |
| `adapters/claude-code/mem0-retrieve.sh` | Claude Code 召回 Hook |
| `backend/app/api/memory_compat.py` | 兼容路由 (v1/v2) |
| `backend/app/memory/services/memory_worker.py` | 后台 Worker |

## 测试报告规范

每次测试在 `playground/tests/` 下创建目录：

```
playground/tests/{feature}-{YYYYMMDD}/
├── README.md
├── plan/
├── report/
│   └── TEST_REPORT.md
└── fix/
```

模板见 `references/` 目录。
