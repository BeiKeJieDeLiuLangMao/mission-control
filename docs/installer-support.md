# 安装器平台支持

本文档定义 `./install.sh` 当前的平台支持状态。

## 支持状态

- **Stable**: 在 CI 中经过完整测试，预期可端到端正常运行。
- **Scaffolded**: 发行版已被识别并提供可操作的安装指引，但完整的自动包安装尚未实现。
- **Unsupported**: 发行版/包管理器未被安装器识别。

## 当前支持矩阵

| 发行版系列 | 包管理器 | 状态 | 备注 |
|---|---|---|---|
| Debian / Ubuntu | `apt` | **Stable** | 完整的自动依赖安装路径。 |
| Fedora / RHEL / CentOS | `dnf` / `yum` | **Scaffolded** | 已实现检测和可操作命令；自动安装路径待完成。 |
| openSUSE | `zypper` | **Scaffolded** | 已实现检测和可操作命令；自动安装路径待完成。 |
| Arch Linux | `pacman` | **Scaffolded** | 已实现检测和可操作命令；自动安装路径待完成。 |
| 其他 Linux 发行版 | unknown | **Unsupported** | 安装器退出并提示需要包管理器相关指引。 |
| macOS (Darwin) | Homebrew | **Stable** | Docker 模式需要 Docker Desktop。Local 模式通过 Homebrew 安装 curl、git、make、openssl、Node.js。 |

## 防护措施

- Debian/Ubuntu 的行为在每个可移植性 PR 中必须保持稳定。
- 新增发行版支持应在显式的包管理器适配器和测试之后添加。
- 如果某个发行版处于 scaffolded 状态但尚未完全自动化，安装器应快速失败并提供可操作的手动命令 (而非通用错误信息)。
