# 实现计划必须包含文档更新

每个实现计划必须有一个"文档更新"章节，列出需要同步的文件。

检查清单:
- 新增/修改 Model → 更新 docs/modules/database.md 和对应模块文档的 Model 表
- 新增 API 端点 → 更新对应模块文档的 API 路由映射表
- 新增环境变量 → 更新 .env.example + docs/modules/ 中的环境变量表
- 新增 service/关键文件 → 更新对应模块文档的关键文件表
- 新增目录 → 更新 CLAUDE.md 的 Backend/Frontend 结构树
- 前端 API 变更 → 包含 `make api-gen` 步骤
- 数据库变更 → 包含 `make backend-migration-check` 步骤

如果计划中没有"文档更新"章节，必须明确说明"本次改动不涉及文档更新"及原因。
