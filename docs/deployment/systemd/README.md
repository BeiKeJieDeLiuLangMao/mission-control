# Systemd 单元文件（本地安装，开机自启）

示例 systemd 单元文件，用于在**不使用 Docker** 安装 Mission Control 时实现开机自启（例如在 VM 中本地安装）。

## 前置条件

- **Backend**: 已安装 `uv`、Python 3.12+，且 `backend/.env` 已配置（包括 `DATABASE_URL`，如使用队列 worker 还需配置 `RQ_REDIS_URL`）。
- **Frontend**: 已安装 Node.js 22+，且 `frontend/.env` 已配置（例如 `NEXT_PUBLIC_API_URL`）。
- **RQ worker**: Redis 必须运行且可访问；`backend/.env` 中必须设置 `RQ_REDIS_URL` 和 `RQ_QUEUE_NAME`，与 backend API 匹配。

如果你仅使用 Docker 运行 Postgres 和/或 Redis，请先启动它们（例如 `docker compose up -d db` 以及可选的 Redis），或添加 `After=docker.service` 并通过单独的单元或脚本启动服务栈。

## 占位符

安装前，请在每个单元文件中替换以下内容：

- `REPO_ROOT` — Mission Control 仓库的绝对路径（例如 `/home/user/openclaw-mission-control`）。路径不能包含空格（systemd 单元值不支持 shell 风格的引号）。
- `BACKEND_PORT` — backend 端口（默认 `8000`）。
- `FRONTEND_PORT` — frontend 端口（默认 `3000`）。

示例（在仓库根目录执行）：

```bash
REPO_ROOT="$(pwd)"
for f in docs/deployment/systemd/openclaw-mission-control-*.service; do
  sed -e "s|REPO_ROOT|$REPO_ROOT|g" -e "s|BACKEND_PORT|8000|g" -e "s|FRONTEND_PORT|3000|g" "$f" \
    > "$(basename "$f")"
done
# 然后将生成的 .service 文件复制到 ~/.config/systemd/user/ 或 /etc/systemd/system/
```

**用户级单元**默认在**用户登录时**启动。如需在**未登录时开机启动**服务，请为你的用户启用 lingering：`loginctl enable-linger $USER`。或者使用 `/etc/systemd/system/` 中的系统级单元（见下文）。

## 安装和启用

**用户级单元**（推荐用于单用户 / VM 环境）：

```bash
cp openclaw-mission-control-backend.service openclaw-mission-control-frontend.service openclaw-mission-control-rq-worker.service ~/.config/systemd/user/
systemctl --user daemon-reload
systemctl --user enable openclaw-mission-control-backend openclaw-mission-control-frontend openclaw-mission-control-rq-worker
systemctl --user start openclaw-mission-control-backend openclaw-mission-control-frontend openclaw-mission-control-rq-worker
```

**系统级单元**（例如放在 `/etc/systemd/system/` 下）：

```bash
sudo cp openclaw-mission-control-*.service /etc/systemd/system/
sudo systemctl daemon-reload
sudo systemctl enable --now openclaw-mission-control-backend openclaw-mission-control-frontend openclaw-mission-control-rq-worker
```

## 启动顺序

Backend、frontend 和 worker 之间的启动顺序没有严格要求；它们都使用 `After=network-online.target`。请确保 Postgres（以及 Redis，如果使用的话）在 backend/worker 之前或同时运行（例如先启动 Docker 服务，或使用系统级单元运行 Postgres/Redis 并让 Mission Control 单元依赖它们）。

## 日志

- `journalctl --user -u openclaw-mission-control-backend -f`（系统级单元使用 `sudo journalctl -u openclaw-mission-control-backend -f`）
- `openclaw-mission-control-frontend` 和 `openclaw-mission-control-rq-worker` 同理。
