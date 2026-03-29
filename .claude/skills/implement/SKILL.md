---
name: implement
description: Harness Implement 阶段 — 按 spec 实现代码 + 逐条自检 contract
---

# Implement

按照 Plan 阶段的 spec 和 contract 实现代码。这是 Harness 三阶段的第二步。

## 前置条件

- `.harness/spec.md` 和 `.harness/contract.md` 必须存在
- 如不存在，先运行 `/plan`

## 流程

1. **读 spec.md + contract.md** — 了解要实现什么、完成标准是什么
2. **按 spec 逐步实现**:
   - Model → Migration → Schema → API → Service → 文档 → 测试
   - 遵循 docs/modules/ 中的现有架构模式
   - 不跳过文档更新和测试
3. **逐条对照 contract 自检** — 完成每个模块后核对
4. **运行 make check** — lint + typecheck + tests + build
5. **生成 build-report.md**:

```markdown
# Build Report

## 已完成
- [x] Model: xxx 字段添加
- [x] API: POST/PATCH/GET 透传
- [x] 文档: docs/modules/xxx.md 更新
- [x] 测试: 8 个新测试通过

## 跳过 (如有)
- [ ] 前端: 需要 make api-gen (后端未运行)
  原因: ...

## make check 结果
通过 / 失败 (详情)

## 已知问题
(无 / 列出)
```

## 完成标志

输出: "实现完成，build-report.md 已更新，请 Evaluator 审查。"

然后运行 `/evaluate` 进入评审阶段。
