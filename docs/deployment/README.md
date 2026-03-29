# 部署

本节介绍在自托管环境中部署 Mission Control。

> **目标**
> 简单、可复现的部署方式，保留 Postgres 数据卷并支持安全升级。

## 部署模式：单主机 (Docker Compose)

### 前置条件

- Docker + Docker Compose v2 (`docker compose`)
- 浏览器能够访问你配置的 backend URL 的主机（参见下方 `NEXT_PUBLIC_API_URL`）

### 1) 配置环境变量

在仓库根目录执行：

```bash
cp .env.example .env
```

编辑 `.env`：

- `AUTH_MODE=local`（默认）
- **设置** `LOCAL_AUTH_TOKEN` 为非占位符值（至少 50 个字符）
- 如果不是 `http://localhost:8000`，确保 `BASE_URL` 与公共 backend 源匹配
- 确保 `NEXT_PUBLIC_API_URL` 可从浏览器访问（不能是 Docker 内部主机名）

关键变量（来自 `.env.example` / `compose.yml`）：

- Frontend: `FRONTEND_PORT`（默认 `3000`）
- Backend: `BACKEND_PORT`（默认 `8000`）
- Postgres: `POSTGRES_DB`、`POSTGRES_USER`、`POSTGRES_PASSWORD`、`POSTGRES_PORT`
- Backend:
  - `DB_AUTO_MIGRATE`（在 compose 中默认为 `true`）
  - `CORS_ORIGINS`（默认 `http://localhost:3000`）
- 安全 Headers（参见 [配置参考](../reference/configuration.md)）：
  - `SECURITY_HEADER_X_CONTENT_TYPE_OPTIONS`（默认 `nosniff`）
  - `SECURITY_HEADER_X_FRAME_OPTIONS`（默认 `DENY`）
  - `SECURITY_HEADER_REFERRER_POLICY`（默认 `strict-origin-when-cross-origin`）

### 2) 启动服务栈

```bash
docker compose -f compose.yml --env-file .env up -d --build
```

打开：

- Frontend: `http://localhost:${FRONTEND_PORT:-3000}`
- Backend 健康检查: `http://localhost:${BACKEND_PORT:-8000}/healthz`

如需容器在故障和主机重启后自动重启，在 `compose.yml` 中为 `db`、`redis`、`backend` 和 `frontend` 服务添加 `restart: unless-stopped`，并确保 Docker 配置为开机启动。

### 3) 验证

```bash
curl -f "http://localhost:${BACKEND_PORT:-8000}/healthz"
```

如果前端加载正常但 API 调用失败，请检查：

- `NEXT_PUBLIC_API_URL` 已设置且可从**浏览器**访问
- Backend CORS 包含前端源（`CORS_ORIGINS`）

## 数据库持久化

Compose 服务栈使用命名卷：

- `postgres_data` → `/var/lib/postgresql/data`

这意味着：

- `docker compose ... down` 会保留数据
- `docker compose ... down -v` 是**破坏性操作**（会删除数据库卷）

## 迁移 / 升级

### Compose 中的默认行为

在 `compose.yml` 中，backend 容器默认：

- `DB_AUTO_MIGRATE=true`

因此启动时 backend 会自动尝试运行 Alembic 迁移。

> **警告**
> 如果执行滚动部署，迁移必须与当前运行的应用**向后兼容**，以实现零/接近零的停机时间。

### 更安全的操作模式（手动迁移）

如果你需要更多控制，设置 `DB_AUTO_MIGRATE=false` 并在部署时显式运行迁移：

```bash
cd backend
uv run alembic upgrade head
```

## 容器安全

Backend 和 frontend Docker 容器均以**非 root 用户**（`appuser`）运行。这是一项安全加固措施。

如果你将宿主机目录绑定挂载到容器中，请确保挂载路径对容器内的非 root 用户可读（如需要则可写）。可以通过以下命令检查 UID/GID：

```bash
docker compose exec backend id
```

## 反向代理 / TLS

典型配置（概述）：

- 将前端置于 HTTPS 之后（反向代理）
- 确保前端可以通过配置的 `NEXT_PUBLIC_API_URL` 访问 backend

在标准化推荐代理（Caddy/Nginx/Traefik）之前，本节内容保持精简。

## 开机自启（本地安装）

如果你在**不使用 Docker** 的情况下安装了 Mission Control（例如使用 `install.sh` 的 "local" 模式，或在不使用 Docker 的 VM 中），安装程序不会配置开机自启。你可以在每次重启后手动启动服务栈，或配置操作系统自动启动。

### Linux (systemd)

使用 [systemd/README.md](./systemd/README.md) 中的示例 systemd 单元文件和说明。简要步骤：

1. 从 `docs/deployment/systemd/` 复制单元文件，将 `REPO_ROOT`、`BACKEND_PORT` 和 `FRONTEND_PORT` 替换为你的实际路径和端口。
2. 将单元文件安装到 `~/.config/systemd/user/`（用户级）或 `/etc/systemd/system/`（系统级）。
3. 启用并启动 backend、frontend 和 RQ worker 服务。

RQ 队列 worker 是 gateway 生命周期（唤醒/签到）和 webhook 投递所必需的；将其作为单独的服务单元运行。

### macOS (launchd)

LaunchAgents 在**用户登录时**运行，而非机器启动时。使用 LaunchAgents 使 backend、frontend 和 worker 在你的用户下运行，并在失败时自动重启。如需真正的开机启动，需要使用 LaunchDaemons 或其他配置（此处不涉及）。

1. 在 `~/Library/LaunchAgents/` 下为每个进程创建一个 plist 文件，例如 `com.openclaw.mission-control.backend.plist`：

```xml
<?xml version="1.0" encoding="UTF-8"?>
<!DOCTYPE plist PUBLIC "-//Apple//DTD PLIST 1.0//EN" "http://www.apple.com/DTDs/PropertyList-1.0.dtd">
<plist version="1.0">
<dict>
  <key>Label</key>
  <string>com.openclaw.mission-control.backend</string>
  <key>ProgramArguments</key>
  <array>
    <string>/usr/bin/env</string>
    <string>uv</string>
    <string>run</string>
    <string>uvicorn</string>
    <string>app.main:app</string>
    <string>--host</string>
    <string>0.0.0.0</string>
    <string>--port</string>
    <string>8000</string>
  </array>
  <key>WorkingDirectory</key>
  <string>REPO_ROOT/backend</string>
  <key>EnvironmentVariables</key>
  <dict>
    <key>PATH</key>
    <string>/usr/local/bin:/opt/homebrew/bin:REPO_ROOT/backend/.venv/bin</string>
  </dict>
  <key>KeepAlive</key>
  <true/>
  <key>RunAtLoad</key>
  <true/>
</dict>
</plist>
```

将 `REPO_ROOT` 替换为实际仓库路径。确保 `uv` 在 `PATH` 中（例如在 plist 的 `PATH` 中添加 `~/.local/bin`）。使用以下命令加载：

```bash
launchctl load ~/Library/LaunchAgents/com.openclaw.mission-control.backend.plist
```

2. 为 frontend（在 `REPO_ROOT/frontend` 中运行 `npm run start -- --hostname 0.0.0.0 --port 3000`）和 RQ worker（运行 `uv run python ../scripts/rq worker`，`WorkingDirectory=REPO_ROOT/backend`，`ProgramArguments` 指向 `uv`、`run`、`python`、`../scripts/rq`、`worker`）添加类似的 plist 文件。

## macOS launchd (MC 本地开发)

> 以下为本项目自用的 launchd 配置，适用于非 Docker 模式。
> 配置文件在 `~/Library/LaunchAgents/`，登录后自动启动前后端服务。

| 服务 | plist 文件 | 端口 |
|---|---|---|
| Backend (FastAPI) | `ai.openclaw.mc.backend.plist` | 8000 |
| Frontend (Next.js) | `ai.openclaw.mc.frontend.plist` | 3000 |

```bash
# 查看服务状态
launchctl list | grep ai.openclaw.mc

# 重新加载服务 (修改 plist 后需执行)
launchctl unload ~/Library/LaunchAgents/ai.openclaw.mc.backend.plist
launchctl unload ~/Library/LaunchAgents/ai.openclaw.mc.frontend.plist
launchctl load ~/Library/LaunchAgents/ai.openclaw.mc.backend.plist
launchctl load ~/Library/LaunchAgents/ai.openclaw.mc.frontend.plist

# 查看日志
cat ~/.openclaw/logs/mc-backend.log
cat ~/.openclaw/logs/mc-backend-error.log
cat ~/.openclaw/logs/mc-frontend.log
cat ~/.openclaw/logs/mc-frontend-error.log
```

> 注意：LaunchAgents 在**用户登录后**启动，非机器开机。如需开机即启动需用 LaunchDaemons。

