---
paths:
  - "backend/app/api/**"
  - "backend/app/schemas/**"
---
# API 开发流程

修改 API 路由或 Schema 时，遵循以下流程:

1. 修改 backend/app/api/ 中的路由
2. 修改 backend/app/schemas/ 中的 Pydantic 模型
3. 确保后端运行在 127.0.0.1:8000
4. 运行 `make api-gen` 重新生成前端 API 客户端
5. 在 frontend/src/app/ 或组件中使用生成的客户端
6. 更新 docs/modules/ 对应文档的 API 路由映射表
