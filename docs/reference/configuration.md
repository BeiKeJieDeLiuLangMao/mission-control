# 配置参考

本页汇总了最重要的配置项。

## 根目录 `.env` (Compose)

默认值和必填项请参见 `.env.example`。

### `NEXT_PUBLIC_API_URL`

- **设置位置:** `.env` (前端容器环境变量)
- **用途:** 浏览器用于调用后端的公共 URL。
- **注意事项:** 必须从*浏览器*（宿主机）可达，而非 Docker 网络别名。

### `LOCAL_AUTH_TOKEN`

- **设置位置:** `.env` (后端)
- **何时必填:** `AUTH_MODE=local`
- **策略:** 必须为非占位符值，且长度至少 50 个字符。

### `WEBHOOK_MAX_PAYLOAD_BYTES`

- **默认值:** `1048576` (1 MiB)
- **用途:** 入站 webhook 负载的最大可接受大小，超过此值 API 将返回 `413 Content Too Large`。

### `RATE_LIMIT_BACKEND`

- **默认值:** `memory`
- **允许值:** `memory`、`redis`
- **用途:** 选择限流是在每个进程的内存中追踪，还是通过 Redis 共享。

### `RATE_LIMIT_REDIS_URL`

- **默认值:** _(空)_
- **何时必填:** `RATE_LIMIT_BACKEND=redis` 且 `RQ_REDIS_URL` 未设置时
- **用途:** 用于共享限流的 Redis 连接字符串。
- **回退逻辑:** 如果为空且启用了 Redis 限流，后端会回退到 `RQ_REDIS_URL`。

### `TRUSTED_PROXIES`

- **默认值:** _(空)_
- **用途:** 以逗号分隔的可信反向代理 IP 或 CIDR 列表，用于识别 `Forwarded` / `X-Forwarded-For` 客户端 IP 头。
- **注意事项:** 除非直接对端是您控制的代理，否则请留空。

## 安全响应头

以下环境变量控制添加到每个 API 响应中的安全头。将任意变量设为空字符串 (`""`) 即可禁用相应的头。

### `SECURITY_HEADER_X_CONTENT_TYPE_OPTIONS`

- **默认值:** `nosniff`
- **用途:** 防止浏览器对响应进行 MIME 类型嗅探。

### `SECURITY_HEADER_X_FRAME_OPTIONS`

- **默认值:** `DENY`
- **用途:** 防止 API 被嵌入到 iframe 中。

> **注意** 如果您的部署需要将 API 嵌入到 iframe 中，请将此值设为 `SAMEORIGIN` 或留空。

### `SECURITY_HEADER_REFERRER_POLICY`

- **默认值:** `strict-origin-when-cross-origin`
- **用途:** 控制请求中发送的 referrer 信息量。

### `SECURITY_HEADER_PERMISSIONS_POLICY`

- **默认值:** _(空 — 已禁用)_
- **用途:** 设置后可限制浏览器功能（摄像头、麦克风等）。
