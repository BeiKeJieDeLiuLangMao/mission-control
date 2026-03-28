# API 参考（说明与约定）

Mission Control 在 `/api/v1/*` 下暴露 JSON HTTP API (FastAPI)。

- 默认后端基础 URL（本地）：`http://localhost:8000`
- 健康检查端点：
  - `GET /health`（存活检测）
  - `GET /healthz`（存活检测别名）
  - `GET /readyz`（就绪检测）

## OpenAPI / Swagger

- OpenAPI schema：`GET /openapi.json`
- Swagger UI（FastAPI 默认）：`GET /docs`

> 如果您正在构建客户端，建议从 `openapi.json` 生成。

## API 版本控制

- 当前前缀：`/api/v1`
- 项目处于活跃开发阶段，向后兼容性为**尽力而为**。

## 认证

所有受保护的端点需要 bearer token：

```http
Authorization: Bearer <token>
```

认证模式通过 `AUTH_MODE` 控制：

- `local`：共享 bearer token 认证（token 即 `LOCAL_AUTH_TOKEN`）
- `clerk`：Clerk JWT 认证

说明：
- 前端在 local 模式下使用相同的 bearer token 方案（用户在界面中粘贴 token）。
- 许多 "agent" 端点使用 agent token 头代替（见下文）。

### Agent 认证（Mission Control agent）

部分端点专为自主 agent 设计，使用 agent token 头：

```http
X-Agent-Token: <agent-token>
```

在用户/agent 共享的路由上，如果用户认证未能解析，后端也接受 `Authorization: Bearer <agent-token>`。如有疑问，请查阅路由的依赖项（例如 `require_user_or_agent`）。

Agent 认证的限流为**每个 IP 每 60 秒 20 个请求**。超过此限制将返回 `429 Too Many Requests`。

## 授权/权限模型（概览）

后端区分以下两种身份：

- **用户**（人类），通过 `AUTH_MODE` 认证
- **Agent**，通过 agent token 认证

常见模式：

- **仅用户**端点：要求已认证的人类用户（非 agent）。组织级别的管理员检查在需要时单独执行（`require_org_admin`）。
- **用户或 agent** 端点：允许已认证的人类用户或已认证的 agent。
- **Board 范围访问**：用户/agent 的访问可能限制在特定 board 内。

> SOC2 说明：API 生成审计友好的请求 ID（见下文），但在接口稳定后，角色/权限策略应按端点记录。

## 安全头

所有 API 响应默认包含以下安全头：

| 头部 | 默认值 |
| --- | --- |
| `X-Content-Type-Options` | `nosniff` |
| `X-Frame-Options` | `DENY` |
| `Referrer-Policy` | `strict-origin-when-cross-origin` |
| `Permissions-Policy` | _(已禁用)_ |

每个头均可通过 `SECURITY_HEADER_*` 环境变量配置。将变量设为空即可禁用对应的头（详见[配置参考](configuration.md)）。

## 限流

以下按 IP 的限流规则适用于敏感端点：

| 端点 | 限制 | 时间窗口 |
| --- | --- | --- |
| Agent 认证（`X-Agent-Token` 或共享路由上的 agent bearer 回退） | 20 个请求 | 60 秒 |
| Webhook 接收（`POST .../webhooks/{id}`） | 60 个请求 | 60 秒 |

当超过限流时，API 返回 `429 Too Many Requests`。

通过 `RATE_LIMIT_BACKEND` 选择存储后端：

| 后端 | 值 | 行为 |
| --- | --- | --- |
| 内存（默认） | `memory` | 每进程限制；无外部依赖。 |
| Redis | `redis` | 跨所有 worker 共享。设置 `RATE_LIMIT_REDIS_URL`，否则回退到 `RQ_REDIS_URL`。启动时验证连接；瞬时故障时放行请求。 |

> **注意** 使用内存后端时，限制是按进程的。多进程部署应切换到 Redis 后端，或在反向代理层（nginx `limit_req`、Caddy 等）应用限流。

## 请求 ID

每个响应都包含 `X-Request-Id` 头。

- 客户端可提供自己的 `X-Request-Id`；否则由服务端生成。
- 使用此 ID 将客户端报告与服务端日志关联。

## 错误

错误以 JSON 格式返回，具有稳定的顶层结构：

```json
{
  "detail": "...",
  "request_id": "..."
}
```

常见状态码：

- `401 Unauthorized`：凭证缺失/无效
- `403 Forbidden`：已认证但无权限
- `404 Not Found`：资源不存在（或不可见）
- `413 Content Too Large`：请求负载超过大小限制（例如 webhook 接收 1 MB 上限）
- `422 Unprocessable Entity`：请求验证错误
- `429 Too Many Requests`：按 IP 的限流超限
- `500 Internal Server Error`：未处理的服务端错误

验证错误（`422`）通常将 `detail` 作为结构化字段错误列表返回（FastAPI/Pydantic 风格）。

## 分页

列表端点通常返回带有分页字段的 `items` 数组（具体因端点而异）。如果您正在实现新的列表端点，建议使用一致的参数：

- `limit`
- `offset`

...并返回：

- `items: []`
- `total`
- `limit`
- `offset`

## 示例 (curl)

### 健康检查

```bash
curl -f http://localhost:8000/healthz
```

### Agent 心跳签到

```bash
curl -s -X POST http://localhost:8000/api/v1/agent/heartbeat \
  -H "X-Agent-Token: $AUTH_TOKEN" \
  -H "Content-Type: application/json" \
  -d '{"name":"Tessa","board_id":"<board-id>","status":"online"}'
```

### 列出 board 的任务

```bash
curl -s "http://localhost:8000/api/v1/agent/boards/<board-id>/tasks?status=inbox&limit=10" \
  -H "X-Agent-Token: $AUTH_TOKEN"
```

## 待完善 / 后续工作

- 按端点的文档：
  - 必需的认证头（`Authorization` 或 `X-Agent-Token`）
  - 必需的角色（admin、member、agent）
  - 每个端点的常见错误响应
- 限流已在上文记录；考虑通过 OpenAPI `x-ratelimit-*` 扩展暴露。
- 添加以下操作的典型示例：
  - 创建/更新任务 + 评论
  - Board memory 流式传输
  - 审批工作流
