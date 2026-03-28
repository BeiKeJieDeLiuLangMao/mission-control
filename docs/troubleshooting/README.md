# 故障排查

本页汇总常见问题和排查方法。

## 常见问题速查

### 前端加载但 API 调用失败

- 检查 `NEXT_PUBLIC_API_URL` 是否可从浏览器访问 (不是 Docker 内部主机名)
- 检查 `CORS_ORIGINS` 是否包含前端域名
- 检查后端健康状态: `curl http://localhost:8000/healthz`

### 认证错误 (401/403)

- `AUTH_MODE` 与 `NEXT_PUBLIC_AUTH_MODE` 是否一致
- local 模式: `LOCAL_AUTH_TOKEN` 是否已设置且 ≥ 50 字符
- Agent 认证: 检查 `X-Agent-Token` header 或 `Authorization: Bearer` fallback

### 数据库连接/迁移问题

- 运行 `make backend-migration-check` 验证迁移图
- 检查 `POSTGRES_*` 环境变量和数据库连接
- 检查 `backend/migrations/versions/` 中的迁移文件顺序

### Webhook 签名失败 (403)

- 确认 webhook secret 与发送方一致
- 检查 signature_header 配置是否匹配
- 验证 HMAC-SHA256 计算方式

### 限流 (429)

- Agent 认证: 20 请求/60秒/IP
- Webhook 入站: 60 请求/60秒/IP
- Redis 后端: 检查 `RATE_LIMIT_REDIS_URL` 连接

### API 客户端生成失败

- 确保后端运行在 `127.0.0.1:8000` (不是 localhost)
- 检查后端健康状态: `curl http://localhost:8000/healthz`
- 运行 `make api-gen` 重新生成

### Docker 构建问题

- 完全重新构建: `docker compose -f compose.yml --env-file .env build --no-cache --pull`

### Memory / 数据库问题

- 详见 [Memory 模块文档](../modules/memory.md) 的故障排查章节
- 数据库检查命令见 [Database 模块文档](../modules/database.md)

### Gateway Agent 问题

- 详见 [Gateway Agent Provisioning 故障排查](./gateway-agent-provisioning.md)

## 日志位置

| 服务 | 日志路径 |
|------|---------|
| Backend (launchd) | `~/.openclaw/logs/mc-backend.log` |
| Frontend (launchd) | `~/.openclaw/logs/mc-frontend.log` |
| Backend (Docker) | `docker compose logs backend` |
| Frontend (Docker) | `docker compose logs frontend` |

## 相关文档

- [Gateway Agent Provisioning 故障排查](./gateway-agent-provisioning.md)
- [运维](../operations/README.md) — 健康检查、备份、限流
- [配置参考](../reference/configuration.md) — 环境变量
