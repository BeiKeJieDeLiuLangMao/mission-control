# 快速入门

## 什么是 Mission Control？

Mission Control 是用于运营 OpenClaw 的 Web UI 和 HTTP API。

它提供了一个控制平面，用于管理 boards、tasks、agents、approvals，以及（可选的）gateway 连接。

## 快速开始（Docker Compose）

在仓库根目录执行：

```bash
cp .env.example .env

# AUTH_MODE=local 时必须设置
# 将 LOCAL_AUTH_TOKEN 设置为一个非占位符的值，至少 50 个字符。

docker compose -f compose.yml --env-file .env up -d --build
```

打开：
- 前端：http://localhost:3000
- 后端健康检查：http://localhost:8000/healthz

## 下一步

- [认证](../reference/authentication.md)
- [部署](../deployment/README.md)
- [开发](../development/README.md)
