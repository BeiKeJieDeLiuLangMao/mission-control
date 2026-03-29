# 文档优先开发

修改任何模块代码前，先读对应的 docs/modules/*.md 获取关键文件表和架构概览。

| 代码路径 | 先读文档 |
|----------|---------|
| backend/app/memory/ | docs/modules/memory.md |
| backend/app/api/memory/ | docs/modules/memory.md |
| adapters/ | docs/modules/adapters.md |
| backend/app/models/board* backend/app/api/board* | docs/modules/boards.md |
| backend/app/models/task* backend/app/api/task* | docs/modules/tasks.md |
| backend/app/services/openclaw/ backend/app/api/gateway* | docs/modules/gateway.md |
| backend/app/models/organization* backend/app/api/organization* | docs/modules/organizations.md |
| backend/app/models/skill* backend/app/api/skill* | docs/modules/skills.md |
| backend/app/core/ | docs/reference/configuration.md 或 docs/reference/security.md |

文档中的关键文件表提供精确的代码入口，比 Grep/Glob 盲搜更快。
