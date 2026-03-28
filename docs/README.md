# Mission Control 文档

本目录是 OpenClaw Mission Control 的文档主页。

## 快速开始

- [快速入门](./getting-started/README.md)
- [开发指南](./development/README.md)
- [测试](./testing/README.md)
- [部署](./deployment/README.md)
- [发布清单](./release/README.md)
- [运维](./operations/README.md)
- [故障排查](./troubleshooting/README.md)

## 模块深入

处理具体功能模块时，从这里获取详细上下文。

- [Memory](./modules/memory.md) — AI 持久化记忆 (架构、数据流、环境变量、故障排查)
- [Adapters](./modules/adapters.md) — Claude Code hooks + OpenClaw 插件
- [Database](./modules/database.md) — PostgreSQL + Qdrant + Neo4j
- [Gateway](./modules/gateway.md) — 网关管理与 Agent 生命周期
- [平台核心](./modules/platform.md) — Organizations、Boards、Tasks、Approvals

## 参考

- [配置参考](./reference/configuration.md)
- [认证](./reference/authentication.md)
- [API 约定](./reference/api.md)
- [安全](./reference/security.md)
- [OpenClaw 基线配置](./reference/openclaw-baseline-config.md)

## 其他

- [安装器平台支持](./installer-support.md)
- [文档风格指南](./style-guide.md)
- [每 PR 一个迁移](./policy/one-migration-per-pr.md)
