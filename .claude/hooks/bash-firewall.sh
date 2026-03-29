#!/bin/bash
# 阻断危险 Bash 命令 (exit 2 = 阻断)
INPUT=$(cat)
COMMAND=$(echo "$INPUT" | jq -r '.tool_input.command // ""')

for pattern in "rm -rf /" "git reset --hard" "git push --force" "DROP TABLE" "DROP DATABASE" "--no-verify"; do
  if echo "$COMMAND" | grep -qi "$pattern"; then
    echo "BLOCKED: 检测到危险命令模式 '$pattern'。请使用更安全的替代方案。" >&2
    exit 2
  fi
done
exit 0
