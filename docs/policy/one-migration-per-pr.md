# 策略: 每个 PR 仅允许一个数据库迁移

## 规则
如果一个 pull request 在以下路径添加迁移文件：

- `backend/migrations/versions/*.py`

……则最多只能添加**一个**迁移文件。

## 原因
- 使 review 和回滚更简单。
- 减少意外的 Alembic 多 head 情况。
- 使 CI/installer 故障更容易调试。

## 常见例外 / 指导
- 如果存在多个 Alembic head，优先创建**一个** merge 迁移。
- 如果变更不相关，请拆分为多个 PR。

## CI 强制执行
CI 在 PR 上运行 `scripts/ci/one_migration_per_pr.sh`，如果添加了超过 1 个迁移文件则会失败。

## 备注
此策略不替代现有的迁移完整性检查 (`make backend-migration-check`)。它是一个轻量级护栏，用于防止多迁移 PR。
