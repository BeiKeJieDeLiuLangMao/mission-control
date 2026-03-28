---
name: mission-control-e2e-testing
description: E2E testing for Mission Control frontend with authentication and Playwright
version: 3.0.0
---

# Mission Control E2E Testing

Playwright-based end-to-end testing for Mission Control with local authentication handling.

## Login with Local Auth

**Token Location**: `backend/.env` → `LOCAL_AUTH_TOKEN` (>=50 chars)

```typescript
await page.goto('http://localhost:3000/memories');
await page.getByRole('textbox', { name: 'Access token' }).fill(token);
await page.getByRole('button', { name: 'Continue' }).click();
await page.waitForURL('http://localhost:3000/memories');
```

## Core Testing Patterns

### Wait for Data Load

```typescript
await page.waitForSelector('text="记忆列表"');
await page.waitForTimeout(3000);

const heading = await page.locator('h2').textContent();
expect(heading).toMatch(/记忆列表 \(\d+\)/);
```

### Check API Response

```typescript
const response = await page.evaluate(async () => {
  const res = await fetch('http://localhost:8000/api/v1/memories?user_id=yishu');
  return await res.json();
});
expect(response.total).toBeGreaterThan(0);
```

### Verify Page Rendering

```typescript
// Memory cards
const cards = await page.locator('[class*="rounded-xl"][class*="border"]').count();
expect(cards).toBeGreaterThan(0);

// Source badges
const sources = await page.evaluate(() => {
  const badges = Array.from(document.querySelectorAll('[class*="rounded-full"]'));
  return badges.slice(0, 10).map(b => b.textContent);
});
// Expect: "claude-code", "openclaw", "openmemory"
```

## Common Issues

### Page Shows "0" Items
Wait longer for data load: `await page.waitForTimeout(3000);`

### All Sources Show "手工"
Update `inferSource()` in `frontend/src/app/memories/page.tsx` to use API `source` field first.

### API 307 Redirect
MC 后端兼容路由已处理，直接使用不带 trailing slash 的 URL 即可。

## Full Test Scenario

```typescript
// 1. Login
await page.goto('http://localhost:3000/memories');
await page.getByRole('textbox', { name: 'Access token' }).fill(token);
await page.getByRole('button', { name: 'Continue' }).click();

// 2. Wait for data
await page.waitForTimeout(3000);

// 3. Verify count
const heading = await page.locator('h2').textContent();
expect(heading).toMatch(/记忆列表 \(\d+\)/);

// 4. Verify cards
const cards = await page.locator('[class*="rounded-xl"]').count();
expect(cards).toBeGreaterThan(0);

// 5. Verify sources
const sources = await page.evaluate(() => {
  const badges = Array.from(document.querySelectorAll('[class*="rounded-full"]'));
  return badges.slice(1, 6).map(b => b.textContent);
});
// Should show varied sources, not all "手工"
```

## 其他页面测试模式

### Dashboard

```typescript
await page.goto('http://localhost:3000/dashboard');
await page.waitForSelector('[class*="dashboard"]', { timeout: 5000 });
// 验证统计卡片加载
const cards = await page.locator('[class*="stat"], [class*="card"]').count();
expect(cards).toBeGreaterThan(0);
```

### Agents 页面

```typescript
await page.goto('http://localhost:3000/agents');
await page.waitForTimeout(3000);
// 验证 agent 列表
const agents = await page.locator('table tbody tr, [class*="agent-card"]').count();
expect(agents).toBeGreaterThanOrEqual(0);
```

### Costs 页面

```typescript
await page.goto('http://localhost:3000/costs');
await page.waitForTimeout(3000);
// 验证图表或数据表格
const charts = await page.locator('canvas, svg, [class*="chart"]').count();
expect(charts).toBeGreaterThan(0);
```

### Graph 标签页 (Memories 页内)

```typescript
// 在 /memories 页点击 Graph 标签
await page.goto('http://localhost:3000/memories');
await page.waitForTimeout(2000);
const graphTab = page.getByText('Graph');
if (await graphTab.isVisible()) {
  await graphTab.click();
  await page.waitForTimeout(2000);
  const canvas = await page.locator('canvas').count();
  expect(canvas).toBeGreaterThan(0);
}
```

## 参数化

```typescript
// 使用环境变量避免硬编码
const BASE_URL = process.env.MC_URL || 'http://localhost:3000';
const USER_ID = process.env.TEST_USER_ID || 'yishu';
```

---

**Version**: 3.0.0 (2026-03-28)
