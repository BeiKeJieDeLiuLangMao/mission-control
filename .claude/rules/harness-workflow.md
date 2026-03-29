# Harness 工作模式

## 触发判定 (三档)

### MUST: 必须走 harness

满足**任一**条件即触发:
- 新功能涉及 2+ 文件变更 (model/api/service/schema/migration)
- 新增或修改 API 端点
- 新增或修改数据库 Model / Migration
- 跨模块重构
- 用户明确说 `/plan` 或 "走 harness"

### SKIP: 直接做，不走 harness

满足**全部**条件可跳过:
- 单文件改动 (config/docs/样式/注释)
- 无 API/Model/Migration 变更
- 用户任务是: 排查问题 / 代码审查 / 运行测试 / 改配置 / 修文档

常见跳过场景:
- "查一下 xxx 怎么实现的" → 直接探索
- "改一下这个配置" → 读 docs → 改 → make check
- "跑一下 E2E 测试" → 调用对应 Skill
- "审查这段代码" → 直接审查
- "修个 typo / 改个注释" → 直接改

### AUTO: 自动判断

介于两者之间时 (如 bug 修复可能涉及 1-3 文件):
1. 先读 docs 定位问题
2. 评估影响面: 如果只改 1 个实现文件 + 1 个测试文件 → SKIP
3. 如果涉及 API/Model 变更或 3+ 文件 → 走 harness
4. 不确定时，简要告知用户 "这个任务我建议走/不走 harness，因为..."

## 三阶段流程

当判定为 MUST 时:

### Plan 阶段
- 读 CLAUDE.md + docs/modules/ 获取上下文
- 创建 .harness/spec.md (功能列表、涉及文件、技术方案、文档更新)
- 创建 .harness/contract.md (15-30 条可测试的完成标准)
- 规格"在可交付成果上受约束，在路径上自行摸索" (不预设实现细节)

### Implement 阶段
- 按 spec 逐步实现，逐条对照 contract 自检
- 完成后在 .harness/build-report.md 记录完成情况
- 运行 make check

### Evaluate 阶段
- 启动独立 Agent 逐条验证 contract
- 倾向于判 FAIL (不要因为 Generator 做了很多工作就心软)
- 输出 .harness/eval-report.md (PASS/FAIL + bug 列表)
- FAIL → 回到 Implement 阶段读 eval-report 修复 → 再次 Evaluate

## 评测

`/progressive-disclosure-testing` 统一评测:
- 单 Agent 行为: `--type exploration,plan,coding,e2e,bugfix,code_review,perf_optimization`
- Harness 协同: `--type harness`
