#!/bin/bash
# 保护关键配置文件不被直接修改 (exit 2 = 阻断)
INPUT=$(cat)
FILE=$(echo "$INPUT" | jq -r '.tool_input.file_path // .tool_input.path // ""')

# 保护 .env 文件 (可能含密钥)
if echo "$FILE" | grep -qE '\.env$|\.env\.local$'; then
  echo "BLOCKED: 禁止直接修改 .env 文件 (可能含密钥)。请修改 .env.example 并提醒用户更新。" >&2
  exit 2
fi
exit 0
