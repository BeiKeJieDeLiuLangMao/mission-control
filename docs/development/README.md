# 开发指南

本章面向在本地开发 Mission Control 的贡献者。

## 推荐工作流（快速迭代）

在 Docker 中运行 Postgres，在宿主机上运行 backend + frontend。

### 1) 启动 Postgres

在仓库根目录执行：

```bash
cp .env.example .env
docker compose -f compose.yml --env-file .env up -d db
```

### 2) 运行后端（开发模式）

```bash
cd backend
cp .env.example .env

uv sync --extra dev
uv run uvicorn app.main:app --reload --host 0.0.0.0 --port 8000
```

验证：

```bash
curl -f http://localhost:8000/healthz
```

### 3) 运行前端（开发模式）

```bash
cd frontend
cp .env.example .env.local
npm install
npm run dev
```

打开 http://localhost:3000。

## 常用仓库根目录命令

```bash
make help
make setup
make check
```

- `make setup`：同步 backend + frontend 依赖
- `make check`：lint + 类型检查 + 测试 + 构建（最接近 CI 的本地检查）

## CI 迁移完整性检查

CI 强制执行迁移完整性检查，防止合并时的 schema 损坏。

### 检查内容

- Alembic 迁移可以从干净的 Postgres 数据库应用 (`upgrade head`)
- 迁移应用后 Alembic revision graph 解析到一个 head revision
- 在涉及迁移的 PR 中，CI 还会检查 model 变更是否附带了迁移更新

任何检查失败都会导致 CI 失败并阻止 PR 合并。

### 本地复现

```bash
make backend-migration-check
```

此命令启动临时 Postgres 容器，运行迁移检查，然后清理容器。

## 相关文档

- [测试](../testing/README.md)
- [发布检查清单](../release/README.md)
