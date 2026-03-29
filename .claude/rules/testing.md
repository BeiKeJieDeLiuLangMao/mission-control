# 测试规范

- 后端: pytest, 强制 100% 覆盖: app.core.error_handling, app.services.mentions
- 前端: vitest (单元), Cypress/Playwright (E2E)
- 修改代码后运行 `make check` 验证完整 CI
- Bug 修复必须附带回归测试
- 新功能必须附带单元测试

E2E 测试 Skill:
- Memory 管道: /memory-e2e-testing
- 前端页面: /mission-control-e2e-testing
- Claude Code 插件: /claude-code-plugin-testing

执行 E2E 验证时，优先调用对应的测试 Skill 获取结构化测试流程。
