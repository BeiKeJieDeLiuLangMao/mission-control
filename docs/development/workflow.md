# 开发工作流规范

> 本文档定义 Claude Code 执行开发任务时的标准流程。每次开发都应遵循此流程以确保质量和一致性。

## 执行流程 (五步法)

```
1. Doc 先行 → 2. 代码实现 → 3. 交互验证 → 4. 修复问题 → 5. 脚本固化
```

### Step 1: Doc 先行

**在写任何代码之前**，先在 `docs/` 中描述要做什么：
- 功能点 (做什么)
- 涉及文件 (改哪里，引用代码路径)
- API 变更 (新增/修改的端点)
- 测试方法 (怎么验证)

**为什么**: 文档是思考的载体。先写文档能发现设计盲点，也让后续 session 能快速理解上下文。

**对应文件**:
- 模块功能 → `docs/modules/<module>.md`
- 测试方法 → `docs/testing/README.md`
- API 变更 → `docs/reference/api.md` 或模块文档的 API 路由映射表

### Step 2: 代码实现

遵循渐进式披露读取顺序：
1. 先读 `CLAUDE.md` (Layer 1) 了解全局
2. 再读 `docs/modules/` (Layer 2) 了解模块上下文
3. 最后读代码 (Layer 3) 实施修改

**代码-文档一致性**: 代码中的关键路径必须在文档中有引用，文档中的描述必须与代码实际行为一致。

### Step 3: 交互验证 (MCP 先行)

**先用 MCP 工具逐步交互验证，不要直接写脚本**。

流程:
1. 用 Playwright MCP (headless) 逐步操作页面
2. 每一步截图验证实际效果
3. 用 snapshot 获取 accessibility tree 定位元素
4. 发现问题记录并修复

**为什么**: 交互式测试能实时发现脚本无法预见的问题（元素定位、加载时序、认证流程等）。

### Step 4: 修复问题

交互验证中发现的问题：
- **优先修复根因**，不绕过
- 端口不通 → 排查日志修复配置，不换端口
- 依赖缺失 → 安装依赖重启服务，不 mock
- API 404 → 补充路由，不改客户端
- 每个修复同步更新文档

### Step 5: 脚本固化

交互测试全部通过后，将步骤组织为自动化脚本：
- Playwright `.spec.ts` 文件
- 脚本中的断言来自交互验证时确认的实际值
- 脚本必须使用 headless 模式

---

## E2E 测试规范

### 通用规则

| 规则 | 说明 |
|------|------|
| **headless** | 必须使用无头模式，不弹浏览器干扰用户 |
| **端口稳定** | Backend :8000, Frontend :3000，遇到问题修复而非换端口 |
| **真实链路** | OpenClaw 链路从 TUI 实测，不能只模拟 API |
| **认证注入** | 用 `sessionStorage.setItem('mc_local_auth_token', token)` 跳过 UI 登录 |

### 认证模式

```typescript
async function login(page: Page) {
  await page.goto(BASE);
  await page.evaluate((token) => {
    window.sessionStorage.setItem('mc_local_auth_token', token);
  }, TOKEN);
  await page.goto(`${BASE}/target-page`);
  await page.waitForSelector('target-element', { timeout: 15000 });
}
```

### 固定测试目录 (已在 .gitignore)

| 目录 | 用途 | 说明 |
|------|------|------|
| `frontend/e2e-screenshots/` | MCP 交互截图 + 脚本截图 | 命名: `step{N}-{description}.png` |
| `frontend/test-results/` | Playwright 测试结果 | 失败截图、trace 文件 |
| `.playwright-mcp/` | Playwright MCP 日志 | console log、snapshot 文件 |

**必须使用这些固定目录**，不要每次创建不同的目录。

---

## 故障排查规范

### 服务不可用

```
问题 → 查日志 → 找根因 → 修复 → 验证
```

不要做:
- 换端口绕过
- 关闭功能绕过
- mock 数据绕过

常见根因:
- launchd plist WorkingDirectory 指向错误目录
- venv shebang 指向旧路径 (需 `rm -rf .venv && uv sync`)
- pip 依赖缺失 (如 `langchain-neo4j`, `rank-bm25`)
- 配置中端口/URL 指向旧值

### Worker 不处理 Turn

检查顺序:
1. `grep "memory_worker" ~/.openclaw/logs/mc-backend.log | tail -5` — Worker 是否运行
2. `grep "Failed to initialize memory client"` — Memory client 是否初始化成功
3. 检查 Qdrant/Neo4j 是否可达
4. 检查 `LLM_API_KEY` 是否设置

---

## 文档更新检查清单

每次开发完成后确认：

- [ ] `docs/modules/<module>.md` 中的 API 路由映射表已更新
- [ ] 新增的前端功能已在文档 "前端页面" 章节描述
- [ ] `docs/testing/README.md` 中的测试覆盖范围已更新
- [ ] `CLAUDE.md` 的模块索引表无需改动（仅在新增模块时更新）
- [ ] 代码中的关键路径在文档中有引用 (`file:function` 格式)
