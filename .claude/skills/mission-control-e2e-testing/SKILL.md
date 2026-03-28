---
name: mission-control-e2e-testing
description: E2E testing for Mission Control frontend with authentication and Playwright
version: 2.0.0
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

---

**Version**: 2.0.0 (2026-03-28)
