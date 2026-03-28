# Gateway Agent Provisioning 与 Check-In 故障排查

本指南说明 agent provisioning 如何收敛到健康状态，以及当 agent 看起来卡住时如何调试。

## 快速收敛策略

Mission Control 对 wake/check-in 使用快速收敛策略：

- 每次 wake 后的 check-in 截止时间: **30 秒**
- 未收到 check-in 时的最大 wake 尝试次数: **3 次**
- 第三次尝试后仍无 check-in: agent 被标记为 **offline**，provisioning 升级停止

此策略同时适用于 gateway-main 和 board agent。

## 预期生命周期

1. Mission Control 配置/更新 agent 并发送 wake。
2. 一个延迟的 reconcile 任务被加入队列，等待 check-in 截止时间。
3. Agent 应在启动/bootstrap 后迅速调用 heartbeat。
4. 如果 heartbeat 到达:
   - `last_seen_at` 被更新
   - wake 升级状态被重置 (`wake_attempts=0`，check-in 截止时间被清除)
5. 如果 heartbeat 在截止时间前未到达:
   - reconcile 重新运行生命周期 (再次 wake)
   - 最多共 3 次 wake 尝试
6. 如果 3 次尝试后仍无 heartbeat:
   - agent 状态变为 `offline`
   - `last_provision_error` 被设置

## 启动时的 Check-In 行为

模板现在明确要求启动后立即进行首次 check-in：

- Main agent 的 heartbeat 指令要求在 wake/bootstrap 后立即 check-in。
- Board lead 的 bootstrap 要求在编排之前先完成 heartbeat check-in。
- Board worker 的 bootstrap 已包含立即 check-in。

如果 gateway 仍使用旧版模板，请运行 template sync 并重新 provision/wake。

## 日志中应看到的内容

健康流程通常包括：

- `lifecycle.queue.enqueued`
- `queue.worker.success` (对应 lifecycle 任务)
- `lifecycle.reconcile.skip_not_stuck` (heartbeat 到达后)

如果 agent 未 check-in：

- `lifecycle.reconcile.deferred` (截止时间之前)
- `lifecycle.reconcile.retriggered` (重试 wake)
- `lifecycle.reconcile.max_attempts_reached` (第 3 次尝试的最终安全阀)

如果完全看不到 lifecycle 事件，请先验证 queue worker 的健康状态。

## 常见故障模式

### Wake 已发送，但未收到 check-in

可能原因：

- Agent 进程从未启动或在 bootstrap 过程中崩溃
- Agent 由于模板过时而忽略了启动指令
- Heartbeat 调用失败 (网络/认证/base URL 不匹配)

处理步骤：

1. 确认当前模板已同步到 gateway。
2. 重新运行 provisioning/update 以触发新的 wake。
3. 验证 agent 能访问 Mission Control API 并使用 `X-Agent-Token` 发送 heartbeat。

### Agent 停留在 provisioning/updating 状态且无重试

可能原因：

- Queue worker 未运行
- API 进程和 worker 进程之间 Queue/Redis 配置不匹配

处理步骤：

1. 验证 worker 进程持续运行中。
2. 验证 API 和 worker 的 `rq_redis_url` 和 `rq_queue_name` 完全一致。
3. 检查 worker 日志中的 dequeue/handler 错误。

### Agent 迅速变为 offline

这是在 3 次 wake 尝试后均未收到 check-in 时的预期行为。系统设计为快速失败。

处理步骤：

1. 先修复 check-in 路径 (启动、网络、token、API 可达性)。
2. 重新运行 provisioning/update 以开始新的尝试周期。

## 运维恢复清单

1. 确保 queue worker 正在运行。
2. 为 gateway 同步模板。
3. 从 Mission Control 触发 agent update/provision。
4. 观察日志中的以下内容：
   - `lifecycle.queue.enqueued`
   - `lifecycle.reconcile.retriggered` (如需要)
   - heartbeat 活动 / `skip_not_stuck`
5. 如仍然失败，收集以下信息：
   - gateway 在 bootstrap 期间的日志
   - worker 在 lifecycle 事件期间的日志
   - agent 的 `last_provision_error`、`wake_attempts`、`last_seen_at`

## Mission Control 与 OpenClaw 认证 token 不同步时的重新同步

Mission Control 存储每个 agent token 的哈希值，并通过写入模板 (例如 `TOOLS.md`) 中包含 `AUTH_TOKEN` 来配置 OpenClaw。如果 gateway 上的 token 与后端哈希不一致 (例如重新安装、token 变更或手动编辑后)，heartbeat 可能返回 401，agent 可能显示为 offline。

重新同步步骤：

1. 确保 Mission Control 正在运行 (API 和 queue worker)。
2. 运行**带 token 轮换的 template sync**，使后端签发新的 agent token 并将 `AUTH_TOKEN` 重新写入 gateway 的 agent 文件。

**通过 API (curl):**

```bash
curl -X POST "http://localhost:8000/api/v1/gateways/GATEWAY_ID/templates/sync?rotate_tokens=true" \
  -H "Authorization: Bearer YOUR_LOCAL_AUTH_TOKEN"
```

将 `GATEWAY_ID` 替换为 Gateways 列表或 UI 中 gateway URL 中的 ID，将 `YOUR_LOCAL_AUTH_TOKEN` 替换为你的 local auth token。

**通过 CLI (从项目根目录):**

```bash
cd backend && uv run python scripts/sync_gateway_templates.py --gateway-id GATEWAY_ID --rotate-tokens
```

同步成功后，OpenClaw agent 的工作区文件中将包含新的 `AUTH_TOKEN` 值；下次 heartbeat 或 bootstrap 将使用新 token。如果 gateway 处于 offline 状态，请从 Mission Control 触发 wake/update，使 agent 重启并获取新 token。
