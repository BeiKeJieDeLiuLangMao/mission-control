# 认证

Mission Control 通过 `AUTH_MODE` 支持两种认证模式：

- `local`：共享 bearer token 认证，适用于自托管部署
- `clerk`：Clerk JWT 认证

## Local 模式

后端：

- `AUTH_MODE=local`
- `LOCAL_AUTH_TOKEN=<token>`

前端：

- `NEXT_PUBLIC_AUTH_MODE=local`
- 通过登录界面提供 token。

## Clerk 模式

后端：

- `AUTH_MODE=clerk`
- `CLERK_SECRET_KEY=<secret>`

前端：

- `NEXT_PUBLIC_AUTH_MODE=clerk`
- `NEXT_PUBLIC_CLERK_PUBLISHABLE_KEY=<key>`

## Agent 认证

自主 agent 主要通过 `X-Agent-Token` 头进行认证。在用户/agent 共享的路由上，如果用户认证未能解析，后端也接受 `Authorization: Bearer <agent-token>`。详见 [API 参考](api.md)。

安全说明：

- Agent 认证的限流为**每个 IP 每 60 秒 20 个请求**。超过此限制将返回 `429 Too Many Requests`。
- 认证失败的日志可能包含 token 的短前缀以便调试，但绝不会包含完整的 token。
