---
name: claude-code-plugin-testing
description: Claude Code plugin integration testing via CLI hooks against MC backend
version: 4.0.0
---

# Claude Code Plugin Testing

## 概述

通过 **Claude Code CLI** 测试记忆插件的完整工作流程（hooks → MC 后端 → 记忆存储/召回）。

**核心原则**：使用 `claude` 命令行工具进行端到端测试，而不是直接调用 API。

## 前置条件

### 1. 确认服务运行

```bash
# MC 后端
curl http://localhost:8000/healthz

# Qdrant
curl -sf http://127.0.0.1:6333/collections | jq '.result.collections[].name'

# Neo4j
docker ps --filter name=neo4j --format "{{.Names}}: {{.Status}}"
```

### 2. 确认插件已安装

```bash
# 检查 hooks 配置
cat ~/.claude/settings.json | jq '.hooks'
```

预期输出应包含 `UserPromptSubmit`（召回）和 `Stop`（存储）hooks，路径指向 `openclaw-mission-control/adapters/claude-code/`。

## 测试工作流

### Phase 1: 基础设施验证

```bash
echo "=== 服务状态检查 ===" && \
curl -sf http://localhost:8000/healthz && echo " ✓ MC Backend" && \
curl -sf http://127.0.0.1:6333/collections && echo " ✓ Qdrant" && \
docker ps --filter name=neo4j --format "{{.Names}}: {{.Status}}" && echo " ✓ Neo4j"
```

### Phase 2: Hook 配置验证

```bash
# 检查 hooks 脚本路径
RETRIEVE_SCRIPT=$(cat ~/.claude/settings.json | jq -r '.hooks.UserPromptSubmit[0].hooks[0].command')
STORE_SCRIPT=$(cat ~/.claude/settings.json | jq -r '.hooks.Stop[0].hooks[0].command')

echo "Retrieve: $RETRIEVE_SCRIPT"
echo "Store: $STORE_SCRIPT"

# 验证脚本存在
ls -la "$RETRIEVE_SCRIPT" "$STORE_SCRIPT"
```

### Phase 3: Claude Code CLI 端到端测试

**测试存储功能（Stop hook）**：

```bash
cd /tmp/mc-test-project

# 发送一条需要记忆的消息
echo "请记住我喜欢用 Neovim 作为主要编辑器" | claude --print --no-input
```

**验证存储结果**：

```bash
# 查看最新的 turn 记录
curl -s "http://localhost:8000/api/v2/turns/?user_id=yishu&limit=3" | \
  jq '.items[] | {id: .id, source: .source, created_at: .created_at}'
```

**测试召回功能（UserPromptSubmit hook）**：

```bash
echo "我之前说过我喜欢用什么编辑器？" | claude --print --no-input 2>&1
```

### Phase 4: 验证记忆提取

```bash
# 等待 Worker 处理（~10 秒）
sleep 10

# 查询 fact/summary
curl -s "http://localhost:8000/api/v2/memories/?user_id=yishu&limit=10" | \
  jq '.items[] | {content: .content[:60], memory_type: .memory_type, source: .source}'
```

### Phase 5: 搜索质量验证

```bash
# 语义搜索：用不同表述查询之前存储的内容
curl -s "http://localhost:8000/api/v2/memories/search?query=编辑器偏好&user_id=yishu&limit=3" | \
  jq '.items[] | {content: .content[:60], score}'

# 验证: score > 0.5 表示语义相关
```

### Phase 6: Worker 处理状态验证

```bash
# 轮询等待 Worker 完成处理
for i in $(seq 1 12); do
  STATUS=$(curl -s "http://localhost:8000/api/v2/turns/?user_id=yishu&limit=1" | \
    jq -r '.items[0].processing_status // "unknown"')
  echo "[$i] status: $STATUS"
  [[ "$STATUS" == "completed" ]] && echo "✓ Worker 处理完成" && break
  sleep 5
done
```

### Phase 7: 前端验证

```bash
open http://localhost:3000/memories
```

验证：记忆总数增加，source 显示 "claude-code"。

## 快速测试

```bash
(
  echo "记住我喜欢用 Zed Studio 写代码" | claude --print --no-input 2>&1 | tail -5
  sleep 10
  curl -s "http://localhost:8000/api/v2/turns/?user_id=yishu&limit=1" | \
    jq '{total: .total, latest_source: .items[0].source}'
)
```

## 故障排查

### Hook timeout 说明

项目级 `.claude/settings.json` 中 hook timeout 应设为：
- **UserPromptSubmit (retrieve)**: 30 秒 (需等待向量搜索)
- **Stop (store)**: 60 秒 (异步，需完成 turn 写入)

timeout=1 会导致 hook 被提前终止。

### Hook 未触发
```bash
# 手动测试 hook 脚本
echo '{"message":{"role":"user","content":"测试"}}' | \
  bash adapters/claude-code/mem0-retrieve.sh
```

### API 连接失败
```bash
curl http://localhost:8000/healthz
lsof -i :8000
```

### 记忆召回为空
```bash
curl -s "http://localhost:8000/api/v2/memories/search?query=编辑器&user_id=yishu&limit=3" | \
  jq '.results[] | {content: .content, score: .score}'
```

## 相关文件

- Hook 脚本：`adapters/claude-code/mem0-retrieve.sh`, `mem0-store.sh`
- 配置：`adapters/claude-code/config.sh`
- Hooks 配置：`~/.claude/settings.json`
- API 文档：`http://localhost:8000/docs`
