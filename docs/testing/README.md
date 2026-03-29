# 测试

本指南介绍如何在本地运行 Mission Control 测试。

## 快速开始（仓库根目录）

```bash
make setup
make check
```

`make check` 是最接近 CI 的本地检查：

- backend：lint + 类型检查 + 单元测试（带作用域覆盖率门控）
- frontend：lint + 类型检查 + 单元测试（Vitest）+ 生产构建

## 后端测试

在仓库根目录执行：

```bash
make backend-test
make backend-coverage
```

或在 `backend/` 目录下：

```bash
cd backend
uv run pytest
```

注意事项：

- 部分测试可能需要运行中的 Postgres（参见根目录 `compose.yml`）。
- `make backend-coverage` 对指定模块集合强制执行严格的覆盖率门控。

## 前端测试

在仓库根目录执行：

```bash
make frontend-test
```

或在 `frontend/` 目录下：

```bash
cd frontend
npm run test
npm run test:watch
```

## 端到端测试（Cypress）

前端在 `frontend/cypress/` 中配置了 Cypress。

典型流程：

1) 启动整个服务栈（或分别启动 backend + frontend）
2) 运行 Cypress

示例（两个终端）：

```bash
# 终端 1
cp .env.example .env
docker compose -f compose.yml --env-file .env up -d --build
```

```bash
# 终端 2
cd frontend
npm run e2e
```

或以交互模式运行：

```bash
cd frontend
npm run e2e:open
```

## Memory 端到端测试（Playwright）

测试完整的 Memory 管道：OpenClaw/Claude Code -> Turn -> Worker -> Qdrant/Neo4j -> 前端展示。

```bash
cd frontend && npx playwright test e2e/memories/
```

测试文件：`frontend/e2e/memories/openclaw-mem0-e2e.spec.ts`

前置条件：Backend(:8000) + Frontend(:3000) + Qdrant(:6333) + Neo4j(:7687) 已启动运行。

覆盖范围：
- Source badges（OpenClaw/Claude Code）、memory_type badges（fact/summary）
- Source 和 Agent 筛选过滤
- Memory 详情对话框及 Turn 关联（session、status、messages）
- 结构化消息渲染: tool_use blocks (🔧 工具名 + 参数) / tool_result blocks (📋 结果) 的存储与 API 返回
- Graph 可视化、搜索、来源筛选、Agent 筛选联动关系统计、关系类型过滤

规范：
- **必须使用无头模式 (headless)**，不弹出浏览器窗口干扰用户
  - Playwright config: `headless: true` (`frontend/playwright.config.ts`)
  - Playwright MCP: `.mcp.json` 中 args 加 `--headless` (已配置在插件 `.mcp.json`)
- E2E 测试流程: 先用 MCP tool 交互式验证 → 通过后再整理为自动化脚本
- OpenClaw 链路测试必须从 TUI 实际发消息，不能只模拟 API

### 完整性要求 (必读)

**不允许用旧数据冒充测试通过**。每次交互式 E2E 测试必须满足：

1. **时间对齐**: 前端页面展示的数据创建时间必须与本次测试操作时间吻合
2. **异步闭环**: Turn → Worker (fact/summary/graph) 必须等 `processing_status=completed` 后才能验证前端
   - Worker 积压时应清理旧 pending turns (`UPDATE turns SET processing_status='completed' WHERE ...`)，不能无限等待也不能跳过验证
3. **来源追溯**: OpenClaw 测试后，filter 选 OpenClaw 来源必须能看到本次测试产生的 agent 和记忆
4. **典型反例**:
   - 页面有 200 条记忆 → 不代表刚测试的数据已入库
   - OpenClaw (18) filter 有数据 → 但可能全是旧数据，新发的消息可能还在 Worker 队列
   - Worker 日志显示 "extracted 16 facts" → 可能是别的 turn，不是你刚测试的

## 覆盖率策略

当前只对特定模块强制 100% 覆盖率，通过 `make backend-coverage` 执行:

- `app.core.error_handling`
- `app.services.mentions`

详见根目录 `Makefile` 中的 `backend-coverage` target。
