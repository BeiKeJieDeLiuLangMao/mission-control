---
name: evaluate
description: Harness Evaluate 阶段 — 作为独立评审者严格验证 contract
---

# Evaluate

作为独立评审者，严格验证 Implement 阶段的实现是否满足 contract。这是 Harness 三阶段的第三步。

## 关键原则

1. **倾向于判 FAIL** — 不要因为 Generator 做了很多工作就心软
2. **"看起来大致正确" 不够** — 必须实际读代码验证每一条标准
3. **独立评估** — 启动独立 Agent 进行评审，不用主 Agent 自评

## 流程

启动一个独立的评估 Agent:

```
Agent tool 参数:
  description: "评审: {任务简述}"
  mode: "default"
  prompt: 见下方模板
```

### 评估 Agent 的工作

1. **读 .harness/contract.md** — 获取完成标准清单
2. **读 .harness/build-report.md** — 了解 Generator 声称完成了什么
3. **逐条验证** — 对每条标准:
   - 找到对应代码，确认实现正确
   - 判定 PASS 或 FAIL + 具体原因和代码位置
4. **深度探测** — 超出合约的额外检查:
   - 边界情况 (空值、极大值、并发)
   - 安全问题 (注入、认证绕过)
   - 性能问题 (N+1、缺索引)
   - 架构一致性 (是否偏离项目模式)
5. **输出 eval-report.md**:

```markdown
# Eval Report

## 总体判定: PASS / FAIL

## 合约标准逐条检查
| # | 标准 | 判定 | 说明 |
|---|------|------|------|
| 1 | xxx | PASS | 代码位置: xxx.py:42 |
| 2 | yyy | FAIL | 未实现 / 实现有误 |

## 额外发现
| 严重性 | 问题 | 位置 |
|--------|------|------|
| HIGH | ... | ... |

## 统计
- 通过: N / 总数: M
- 额外问题: X HIGH + Y MEDIUM
```

## 判定规则

- 任何 **HIGH** 严重性问题 → **FAIL**
- 合约标准不通过 **> 20%** → **FAIL**
- 其他 → **PASS** (附建议)

## FAIL 后的流程

1. Implement Agent 读 eval-report.md
2. 逐一修复 FAIL 项
3. 更新 build-report.md
4. 再次 `/evaluate`
5. 最多迭代 3 轮
