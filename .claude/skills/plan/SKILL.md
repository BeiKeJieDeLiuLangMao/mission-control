---
name: plan
description: Harness Plan 阶段 — 读 docs 生成实现规格 + 冲刺合约
---

# Plan

为当前任务生成实现规格和冲刺合约。这是 Harness 三阶段工作模式的第一步。

## 输出

- `.harness/spec.md` — 功能列表、涉及文件、技术方案、文档更新清单
- `.harness/contract.md` — 可测试的完成标准 (目标 15-30 条)

## 流程

1. **读 CLAUDE.md** 模块索引 → 定位相关模块文档
2. **读 docs/modules/** 相关文档 → 获取架构、关键文件、API 映射
3. **读 .claude/rules/** → 了解约束 (plan-docs-sync, api-workflow, testing)
4. **读关键代码文件** → 了解现有实现
5. **创建 .harness/ 目录** → 生成 spec.md + contract.md

## spec.md 结构

```markdown
# Spec: {任务标题}

## 功能列表
1. 功能 A — 1-3 句描述
2. 功能 B — 1-3 句描述

## 涉及文件
| 文件 | 变更 |
|------|------|
| backend/app/models/xxx.py | 新增 xxx 字段 |

## 技术方案
(高层设计，不预设具体实现代码)

## 文档更新
- docs/modules/xxx.md — 更新 Model 表和 API 映射
- .env.example — 如涉及新环境变量

## 测试策略
- 后端: pytest 覆盖 xxx
- 前端: vitest/playwright
```

## contract.md 结构

```markdown
# Contract: {任务标题}

## 完成标准

### Model
- [ ] 具体的可测试行为 1
- [ ] 具体的可测试行为 2

### API
- [ ] POST /xxx 接受 yyy 参数
- [ ] GET /xxx 返回 yyy 字段

### 文档
- [ ] docs/modules/xxx.md 已更新

### 测试
- [ ] make check 通过
```

## 原则

- **在可交付成果上受约束，在路径上自行摸索** — spec 不预设实现细节
- **合约越细越好** — 每条标准对应一个可验证的行为
- **必须含文档更新** — 参见 .claude/rules/plan-docs-sync.md
