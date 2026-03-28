# Database

> 三个数据库协同工作：PostgreSQL (主存储) + Qdrant (向量) + Neo4j (图谱)。

## 概览

| 数据库 | 端口 | 是否必需 | 用途 |
|--------|------|---------|------|
| PostgreSQL | 5432 | 必需 | 主存储 (用户、任务、boards、turns、memories) |
| Qdrant | 6333 | Memory 功能需要 | 向量嵌入存储，支持语义搜索 |
| Neo4j | 7687 | 可选 | 知识图谱 (实体+关系)，不启动则图谱功能跳过 |

## PostgreSQL

- **ORM**: SQLAlchemy + SQLModel，迁移用 Alembic
- **连接**: `compose.yml` 中的 `db` 服务，或本地开发通过 `.env` 的 `POSTGRES_*` 变量

### 主要 Model (backend/app/models/)

| Model | 表名 | 说明 |
|-------|------|------|
| Board | boards | 看板/项目 |
| Task | tasks | 任务 |
| Agent | agents | AI Agent |
| Organization | organizations | 组织 |
| Gateway | gateways | OpenClaw 网关 |
| Approval | approvals | 审批请求 |
| User | users | 用户 |
| Webhook | webhooks | Webhook 配置 |
| Skill | skills | 技能市场 |

### Memory Model (backend/app/memory/models/)

| Model | 表名 | 说明 |
|-------|------|------|
| Turn | turns | 对话轮次 (user_id, messages, source, processing_status) |
| VectorMemory | vector_memories | 提取的记忆 (content, memory_type, metadata, embedding) |

### 迁移工作流

```bash
# 1. 修改 backend/app/models/ 中的模型
# 2. 生成迁移
cd backend && uv run alembic revision --autogenerate -m "描述"
# 3. 检查 backend/migrations/versions/ 中的迁移文件
# 4. 应用迁移
make backend-migrate
# 5. 验证
make backend-migration-check
```

**Policy**: 每个 PR 最多一个迁移文件。详见 [one-migration-per-pr](../policy/one-migration-per-pr.md)。

## Qdrant (向量存储)

- **用途**: 存储 Memory 的向量嵌入，支持语义相似度搜索
- **集合**: `memories` (默认)，1536 维向量 (text-embedding-3-small)
- **不在 compose.yml 中**，需独立运行

```bash
# 启动
docker run -d --name qdrant -p 6333:6333 -v qdrant_data:/qdrant/storage qdrant/qdrant

# 检查
curl -s http://127.0.0.1:6333/collections | jq
```

## Neo4j (图数据库)

- **用途**: Memory 知识图谱，存储实体和关系
- **Graceful degradation**: Neo4j 未启动时图谱功能自动跳过
- **不在 compose.yml 中**，需独立运行

```bash
# 启动
docker run -d --name neo4j-mem0 -p 7687:7687 -p 7474:7474 \
  -e NEO4J_AUTH=neo4j/mem0password neo4j:5

# 检查
docker exec neo4j-mem0 cypher-shell -u neo4j -p mem0password \
  "MATCH (n) RETURN labels(n) as label, count(*) as count ORDER BY count DESC;"

# Web 浏览器
open http://localhost:7474
```

## 数据库健康检查

```bash
# PostgreSQL (通过 MC Backend)
curl http://localhost:8000/healthz

# Qdrant
curl -s http://127.0.0.1:6333/collections | jq '.result.collections | length'

# Neo4j
docker exec neo4j-mem0 cypher-shell -u neo4j -p mem0password "RETURN 1"
```

## 相关文档

- [Memory Module](./memory.md) — Memory 数据流和 Worker 处理
- [Configuration](../reference/configuration.md) — 环境变量参考
- [Migration Policy](../policy/one-migration-per-pr.md) — 每 PR 一个迁移
- [Operations](../operations/README.md) — 备份和恢复
