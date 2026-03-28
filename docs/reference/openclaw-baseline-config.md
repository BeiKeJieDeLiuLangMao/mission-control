# OpenClaw 基线配置 (快速入门)

本指南将 OpenClaw 基线配置转化为本地开发和 Mission Control 集成的实用起点。

OpenClaw CLI 安装后，默认配置路径为:

- `~/.openclaw/openclaw.json`

## 基线配置 (标准 JSON)

以下是标准化的 JSON 基线配置。

```json
{
  "env": {
    "shellEnv": {
      "enabled": true
    }
  },
  "update": {
    "channel": "stable"
  },
  "agents": {
    "defaults": {
      "model": {
        "primary": "",
        "fallbacks": []
      },
      "models": {
        "": {}
      },
      "workspace": "/home/asaharan/.openclaw/workspace",
      "contextPruning": {
        "mode": "cache-ttl",
        "ttl": "45m",
        "keepLastAssistants": 2,
        "minPrunableToolChars": 12000,
        "tools": {
          "deny": [
            "browser",
            "canvas"
          ]
        },
        "softTrim": {
          "maxChars": 2500,
          "headChars": 900,
          "tailChars": 900
        },
        "hardClear": {
          "enabled": true,
          "placeholder": "[Old tool output cleared]"
        }
      },
      "compaction": {
        "mode": "safeguard",
        "reserveTokensFloor": 12000,
        "memoryFlush": {
          "enabled": true,
          "softThresholdTokens": 5000,
          "prompt": "Write any lasting notes to memory/YYYY-MM-DD.md; reply with NO_REPLY if nothing to store.",
          "systemPrompt": "Session nearing compaction. Store durable memories now."
        }
      },
      "thinkingDefault": "medium",
      "maxConcurrent": 5,
      "subagents": {
        "maxConcurrent": 5
      }
    },
    "list": [
      {
        "id": "main"
      }
    ]
  },
  "messages": {
    "ackReactionScope": "group-mentions"
  },
  "commands": {
    "native": "auto",
    "nativeSkills": "auto"
  },
  "hooks": {
    "internal": {
      "enabled": true,
      "entries": {
        "boot-md": {
          "enabled": true
        },
        "command-logger": {
          "enabled": true
        },
        "session-memory": {
          "enabled": true
        },
        "bootstrap-extra-files": {
          "enabled": true
        }
      }
    }
  },
  "channels": {
    "defaults": {
      "heartbeat": {
        "showOk": true,
        "showAlerts": true,
        "useIndicator": true
      }
    }
  },
  "gateway": {
    "port": 18789,
    "mode": "local",
    "bind": "lan",
    "controlUi": {
      "allowInsecureAuth": true
    },
    "auth": {
      "mode": "token"
    },
    "trustedProxies": [
      "127.0.0.1",
      "::1"
    ],
    "tailscale": {
      "mode": "off",
      "resetOnExit": false
    },
    "reload": {
      "mode": "hot",
      "debounceMs": 750
    },
    "nodes": {
      "denyCommands": [
        "camera.snap",
        "camera.clip",
        "screen.record",
        "calendar.add",
        "contacts.add",
        "reminders.add"
      ]
    }
  },
  "memory": {
    "backend": "qmd",
    "citations": "auto",
    "qmd": {
      "includeDefaultMemory": true,
      "update": {
        "interval": "15m",
        "debounceMs": 15000,
        "onBoot": true
      },
      "limits": {
        "maxResults": 3,
        "maxSnippetChars": 450,
        "maxInjectedChars": 1800,
        "timeoutMs": 8000
      }
    }
  },
  "skills": {
    "install": {
      "nodeManager": "npm"
    }
  }
}
```

## 逐节参考

每个配置节控制什么，以及何时需要调整。

### `env`

控制运行时环境行为。

- `env.shellEnv.enabled`: 设为 `true` 时，OpenClaw 可从 shell 上下文解析环境变量，确保工具和模型/provider 发现与 shell 会话一致。

操作提示:

- 如果 shell 启动缓慢，可设置 `env.shellEnv.timeoutMs` (可选) 限制查找时间。

### `update`

控制 npm/git 安装的更新策略。

- `update.channel`: 发布通道 (`stable`, `beta`, `dev`)。

推荐:

- 生产环境使用 `stable`。
- 仅在需要预发布功能时使用 `beta`/`dev`。

### `agents`

定义默认 Agent 运行时行为和 Agent 列表。

#### `agents.defaults.model`

模型路由默认值。

- `primary`: Agent 对话的主模型 ID。
- `fallbacks`: 主模型失败时的有序备选模型。

> **注意**: 空 `primary` 表示未选择默认模型，首次使用前必须设置。

#### `agents.defaults.models`

按模型 ID 的覆盖映射。

- 基线中的空键 `""` 需替换为实际模型 ID。
- 值对象可包含该模型的特定参数。

#### `agents.defaults.workspace`

Agent 状态/工作区的文件系统根目录。

- 必须存在且可写。
- 建议与 Mission Control Gateway 的 `workspace_root` 保持一致。

#### `agents.defaults.contextPruning`

控制 prompt 历史中工具输出的修剪，保持上下文大小健康。

- `mode: "cache-ttl"`: 启用 TTL 感知的修剪。
- `ttl`: 修剪间隔 (如 `45m`)。
- `keepLastAssistants`: 保护最近的 assistant 轮次不被修剪。
- `minPrunableToolChars`: 仅当可修剪的工具输出足够大时才执行硬清除。
- `tools.deny`: 排除在修剪之外的工具名。
- `softTrim`: 保留工具输出的头尾上下文。
- `hardClear`: 超出限制时用占位符完全替换。

#### `agents.defaults.compaction`

控制会话历史压缩和 token 溢出保护。

- `mode: "safeguard"`: 保守压缩策略。
- `reserveTokensFloor`: 硬保留量，避免上下文耗尽。
- `memoryFlush`: 压缩前的记忆检查点。

`memoryFlush` 配置:

- `enabled`: 开关。
- `softThresholdTokens`: 触发 flush 的 token 阈值。
- `prompt`: flush 轮次的用户提示文本。
- `systemPrompt`: flush 轮次的系统指令。

作用: 避免在会话接近压缩时丢失持久化上下文。

#### `agents.defaults.thinkingDefault`

默认推理强度，基线使用 `medium` 平衡质量与速度。

#### 并发控制

- `agents.defaults.maxConcurrent`: 最大并行顶级运行数。
- `agents.defaults.subagents.maxConcurrent`: 最大并行子 Agent 运行数。

用于控制吞吐量与主机/API 压力的平衡。

#### `agents.list`

已配置的 Agent 列表。

- `[{ "id": "main" }]` 创建默认主 Agent 身份。

### `messages`

消息收发行为。

- `messages.ackReactionScope`: ACK 反应的触发范围。

可选值: `group-mentions`, `group-all`, `direct`, `all`

基线使用 `group-mentions`，避免在繁忙群组频道中产生噪音。

### `commands`

原生命令注册行为。

- `commands.native`: 命令注册模式 (`true`/`false`/`auto`)。
- `commands.nativeSkills`: 技能命令注册模式 (`true`/`false`/`auto`)。

基线使用 `auto`，由 OpenClaw 根据频道/provider 能力自动决定。

### `hooks`

内部 hook 系统设置。

- `hooks.internal.enabled`: 开关。
- `hooks.internal.entries`: 按 hook 的启用/配置映射。

基线 hook:

- `boot-md`: 运行 BOOT.md 启动清单。
- `command-logger`: 写入命令审计日志。
- `session-memory`: 使用 `/new` 时存储上下文。
- `bootstrap-extra-files`: 自定义/可选 hook。

> **注意**: 运行时未安装的 hook ID 会被忽略或报告缺失。使用 `openclaw hooks list` 查看可用 hook。

### `channels`

跨频道默认值。

#### `channels.defaults.heartbeat`

控制心跳可见性行为。

- `showOk`: 显示正常心跳消息。
- `showAlerts`: 显示异常/告警心跳。
- `useIndicator`: 发出指示器事件。

基线全部设为 `true`，提供完整的运行可见性。

### `gateway`

核心 Gateway 服务器行为。

#### 网络与模式

- `port`: Gateway WebSocket 端口。
- `mode`: `local` 或 `remote`。
- `bind`: 暴露策略 (`loopback`, `lan`, `tailnet`, `auto`, `custom`)。

基线使用 `bind: "lan"`，Gateway 在局域网接口上可达。

#### Control UI 安全

- `controlUi.allowInsecureAuth: true` 允许通过非安全 HTTP 进行 token 认证。

> **警告**: 适合本地开发，不推荐用于暴露的环境。

#### 认证

- `gateway.auth.mode`: `token` 或 `password`。
- 使用 token 模式时，需通过安全方式提供 `gateway.auth.token`。

#### 反向代理感知

- `gateway.trustedProxies`: 代理 IP 白名单，用于正确检测客户端 IP。

#### Tailscale

- `gateway.tailscale.mode`: `off`, `serve` 或 `funnel`。
- `resetOnExit`: 关闭时是否还原 serve/funnel 配置。

#### 配置热加载

- `gateway.reload.mode`: 重载策略 (`off`, `restart`, `hot`, `hybrid`)。
- `gateway.reload.debounceMs`: 应用配置变更前的去抖延迟。

#### 节点命令策略

- `gateway.nodes.denyCommands`: 远程节点调用的命令拒绝列表。

基线阻止了高风险的设备/系统操作。

### `memory`

`memory` 在基线中是插件式配置 (用于 `qmd`)。

> **警告**: 在 OpenClaw `2026.1.30` 核心 schema 中，顶层 `memory` 不是内置键。没有定义此 section 的插件时，配置验证会报告: `Unrecognized key: "memory"`。

处理方式:

1. 如果使用了定义此 block 的插件，保留并用插件集验证。
2. 如果没有，移除此 block，使用核心的 `agents.defaults.memorySearch` + 插件 slots/entries 管理记忆行为。

### `skills`

技能安装/运行时行为。

- `skills.install.nodeManager`: 技能安装使用的包管理器。

可选值: `npm`, `pnpm`, `yarn`, `bun`

基线使用 `npm`，兼容性最高。

## 使用前验证

运行生产工作负载前执行 schema 检查:

```bash
openclaw config get gateway.port
```

如配置无效，OpenClaw 会报告具体的键/路径和修复方法。

## 首次运行前必须修改

以下字段需在正式使用前设置:

1. **`agents.defaults.model.primary`**
   设置具体模型 ID，例如 `openai-codex/gpt-5.2`。

2. **`agents.defaults.models`**
   将空键 (`""`) 替换为实际模型 ID。

3. **`gateway.auth`**
   如果启用了 token 认证，通过安全方式提供 token 值。

4. **`memory` (顶层)**
   仅在运行时/插件集支持时保留，否则移除以通过核心 schema 验证。

## 快速开始

1. 创建配置文件:

```bash
mkdir -p ~/.openclaw
```

2. 将上述 JSON 保存到:

- `~/.openclaw/openclaw.json`

3. 启动 Gateway:

```bash
openclaw gateway
```

4. 验证健康状态:

```bash
openclaw health
```

5. 打开 Control UI:

```bash
openclaw dashboard
```

## Mission Control 连接 (本项目)

在 Mission Control 中添加 Gateway 时:

- **URL**: `ws://127.0.0.1:18789` (或主机/IP + 端口)
- **Token**: 仅在 Gateway 要求 token 认证时提供
- **设备配对**: 默认启用，推荐保持开启
  - 仅在 Gateway 明确配置了跳过设备认证时 (如 `gateway.controlUi.dangerouslyDisableDeviceAuth: true`) 才禁用
- **Workspace root**: 建议与 `agents.defaults.workspace` 保持一致

## 安全说明

- `gateway.bind: "lan"` 在局域网上暴露 Gateway。
- `controlUi.allowInsecureAuth: true` 适合开发，不推荐暴露环境。
- 使用 `gateway.auth.mode: "token"` 时务必设置强 token。

## 为什么这套基线可行

- 合理的并发默认值 (主 Agent 和子 Agent)。
- 上下文修剪 + 压缩设置减少上下文膨胀。
- 压缩前记忆 flush 保护持久化笔记。
- 保守的命令拒绝列表阻止高风险节点操作。
- 稳定更新通道和可预测的本地 Gateway 行为。
