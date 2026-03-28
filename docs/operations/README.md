# 运维

Mission Control 的运行手册和运维说明。

## 健康检查

Backend 暴露以下端点：

- `/healthz` — 存活检查
- `/readyz` — 就绪检查

示例：

```bash
curl -f http://localhost:8000/healthz
curl -f http://localhost:8000/readyz
```

## 日志

### Docker Compose

```bash
# 查看所有服务日志
docker compose -f compose.yml --env-file .env logs -f --tail=200

# 仅查看 backend 日志
docker compose -f compose.yml --env-file .env logs -f --tail=200 backend
```

Backend 支持通过 `REQUEST_LOG_SLOW_MS` 记录慢请求日志。

## 备份

数据库运行在 Postgres（Compose 的 `db` 服务）中，数据持久化到 `postgres_data` 命名卷。

### 最小备份（逻辑备份）

使用 `pg_dump` 的示例（在宿主机上运行）：

```bash
# 从 .env 加载变量（仅限受信任的文件）
set -a
. ./.env
set +a

: "${POSTGRES_DB:?set POSTGRES_DB in .env}"
: "${POSTGRES_USER:?set POSTGRES_USER in .env}"
: "${POSTGRES_PORT:?set POSTGRES_PORT in .env}"
: "${POSTGRES_PASSWORD:?set POSTGRES_PASSWORD in .env (strong, unique value; not \"postgres\")}"

PGPASSWORD="$POSTGRES_PASSWORD" pg_dump \
  -h 127.0.0.1 -p "$POSTGRES_PORT" -U "$POSTGRES_USER" \
  -d "$POSTGRES_DB" \
  --format=custom > mission_control.backup
```

> **注意**
> 在正式生产环境中，建议使用自动化备份 + 保留策略 + 定期恢复演练。

## 升级 / 回滚

### 升级 (Compose)

```bash
docker compose -f compose.yml --env-file .env up -d --build
```

### 回滚

回滚通常意味着部署之前的镜像/commit。

> **警告**
> 如果你应用了不向后兼容的数据库迁移，回滚应用可能需要恢复数据库。

## 限流

Backend 对敏感端点应用基于 IP 的限流：

| 端点 | 限制 | 时间窗口 |
| --- | --- | --- |
| Agent 认证 | 20 次请求 | 60 秒 |
| Webhook 接收 | 60 次请求 | 60 秒 |

被限流的请求会收到 HTTP `429 Too Many Requests` 响应。

通过 `RATE_LIMIT_BACKEND` 设置存储后端：

| 后端 | 值 | 运维说明 |
| --- | --- | --- |
| 内存（默认） | `memory` | 每进程独立限流；各 worker 独立追踪。无外部依赖。 |
| Redis | `redis` | 限流在所有 worker 之间共享。设置 `RATE_LIMIT_REDIS_URL`，否则回退到 `RQ_REDIS_URL`。启动时会验证连接；Redis 临时故障时采用放行策略（允许请求，记录警告日志）。 |

在多进程部署中使用内存后端时，还应在反向代理层（nginx `limit_req`、Caddy 限流等）应用限流。

## 常见问题

### 前端加载正常但 API 调用失败

- 确认 `NEXT_PUBLIC_API_URL` 已设置且可从浏览器访问。
- 确认 backend CORS 包含前端源（`CORS_ORIGINS`）。

### 认证不匹配

- Backend: `AUTH_MODE`（`local` 或 `clerk`）
- Frontend: `NEXT_PUBLIC_AUTH_MODE` 应与之匹配

### Webhook 签名错误 (403)

如果 webhook 配置了 `secret`，入站请求必须包含有效的 HMAC-SHA256 签名。如果 webhook 还设置了 `signature_header`，则必须使用该指定的 header 名称。否则 backend 会检查以下默认 header：

- `X-Hub-Signature-256: sha256=<hex-digest>`（GitHub 风格）
- `X-Webhook-Signature: sha256=<hex-digest>`

缺失或无效的签名会返回 `403 Forbidden`。如果在 webhook 接收时遇到意外的 403 错误，请验证发送方是否使用 webhook 的 secret 正确计算了 HMAC，并在配置的 header 中发送。

### Webhook 请求体过大 (413)

Webhook 接收默认强制 **1 MB** 的请求体大小限制。超过此限制的请求会返回 `413 Content Too Large`。如需提高限制，请设置 `WEBHOOK_MAX_PAYLOAD_BYTES`；否则考虑发送 URL 引用而非内联内容。
