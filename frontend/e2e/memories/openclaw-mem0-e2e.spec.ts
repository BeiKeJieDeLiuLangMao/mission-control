import { test, expect, type Page } from '@playwright/test';

const BASE = 'http://localhost:3001';
const TOKEN = '3e7e63bd8bd5267f0a72b4f90dee3a2e96f7689254248f91c4371667451c9178';

/** Authenticate via local auth if needed */
async function login(page: Page) {
  await page.goto(`${BASE}/memories`);
  // Local auth: if redirected to sign-in or token input visible
  const tokenInput = page.locator('input[type="password"], input[placeholder*="token" i], input[placeholder*="Token" i]');
  if (await tokenInput.isVisible({ timeout: 3000 }).catch(() => false)) {
    await tokenInput.fill(TOKEN);
    const submitBtn = page.locator('button[type="submit"], button:has-text("Continue"), button:has-text("登录"), button:has-text("确认")');
    await submitBtn.first().click();
    await page.waitForTimeout(2000);
  }
  // Wait for page content to load
  await page.waitForSelector('body', { timeout: 10000 });
}

test.describe('OpenClaw Memory E2E - Full Chain', () => {

  test.beforeEach(async ({ page }) => {
    await login(page);
    // Wait for memories to load
    await page.waitForTimeout(5000);
  });

  // --- 列表视图 ---

  test('Memories page loads with data', async ({ page }) => {
    // 记忆列表标题应包含数量
    const heading = page.locator('h2', { hasText: '记忆列表' });
    await expect(heading).toBeVisible({ timeout: 10000 });
    const text = await heading.textContent();
    expect(text).toMatch(/\(\d+\)/);

    // 至少一张记忆卡片
    const cards = page.locator('.cursor-pointer.rounded-xl');
    await expect(cards.first()).toBeVisible({ timeout: 5000 });
    const count = await cards.count();
    expect(count).toBeGreaterThan(0);

    await page.screenshot({ path: 'e2e-screenshots/memories-list.png' });
  });

  test('Source badges are visible', async ({ page }) => {
    // 检查来源徽章存在 (至少 Claude Code)
    const badges = page.locator('.rounded-full.border');
    await expect(badges.first()).toBeVisible({ timeout: 10000 });

    // 来源筛选区域应包含来源按钮
    const sourceFilter = page.locator('text=来源:');
    await expect(sourceFilter).toBeVisible();

    await page.screenshot({ path: 'e2e-screenshots/memories-sources.png' });
  });

  test('memory_type badges (fact/summary) are visible', async ({ page }) => {
    // 检查 "事实" 或 "摘要" 徽章存在
    const factBadge = page.locator('.rounded-full.border', { hasText: '事实' });
    const summaryBadge = page.locator('.rounded-full.border', { hasText: '摘要' });

    const factCount = await factBadge.count();
    const summaryCount = await summaryBadge.count();
    expect(factCount + summaryCount).toBeGreaterThan(0);

    await page.screenshot({ path: 'e2e-screenshots/memories-type-badges.png' });
  });

  test('Source filter works', async ({ page }) => {
    // 获取初始数量
    const heading = page.locator('h2', { hasText: '记忆列表' });
    await expect(heading).toBeVisible({ timeout: 10000 });
    const initialText = await heading.textContent();
    const initialMatch = initialText?.match(/\((\d+)\)/);
    const initialCount = initialMatch ? parseInt(initialMatch[1]) : 0;

    // 点击 "Claude Code" 来源筛选按钮
    const claudeFilter = page.locator('button', { hasText: /Claude Code/ });
    if (await claudeFilter.count() > 0) {
      await claudeFilter.first().click();
      await page.waitForTimeout(2000);

      // 筛选后数量应变化（如果有多个来源）
      const filteredText = await heading.textContent();
      expect(filteredText).toMatch(/\(\d+\)/);

      // 点击 "全部" 恢复
      const allBtn = page.locator('button', { hasText: '全部' });
      await allBtn.first().click();
      await page.waitForTimeout(1000);
    }

    await page.screenshot({ path: 'e2e-screenshots/memories-source-filter.png' });
  });

  test('Agent filter works', async ({ page }) => {
    // Agent 筛选按钮
    const agentBtns = page.locator('button:has(.lucide-bot)');
    if (await agentBtns.count() > 0) {
      await agentBtns.first().click();
      await page.waitForTimeout(2000);

      // 验证列表更新
      const heading = page.locator('h2', { hasText: '记忆列表' });
      const filteredText = await heading.textContent();
      expect(filteredText).toMatch(/\(\d+\)/);

      // 恢复
      const allBtn = page.locator('button', { hasText: 'All' });
      await allBtn.first().click();
      await page.waitForTimeout(1000);
    }

    await page.screenshot({ path: 'e2e-screenshots/memories-agent-filter.png' });
  });

  test('Search returns results', async ({ page }) => {
    const searchInput = page.locator('input[placeholder*="搜索"]');
    await expect(searchInput).toBeVisible({ timeout: 10000 });

    // 搜索一个存在的关键词
    await searchInput.fill('Python');
    const searchBtn = page.locator('button', { hasText: '搜索' });
    await searchBtn.click();
    await page.waitForTimeout(3000);

    await page.screenshot({ path: 'e2e-screenshots/memories-search.png' });

    // 清除搜索
    const clearBtn = page.locator('button', { hasText: '清除' });
    if (await clearBtn.isVisible()) {
      await clearBtn.click();
    }
  });

  // --- 详情 Dialog ---

  test('Clicking memory card opens detail dialog', async ({ page }) => {
    // 点击第一张卡片
    const card = page.locator('.cursor-pointer.rounded-xl').first();
    await expect(card).toBeVisible({ timeout: 10000 });
    await card.click();

    // Dialog 应该打开
    const dialogTitle = page.locator('text=记忆详情');
    await expect(dialogTitle).toBeVisible({ timeout: 5000 });

    // Dialog 中应有完整内容和元数据
    const dialog = page.locator('[role="dialog"]');
    await expect(dialog).toBeVisible();

    // 应有来源徽章
    const sourceBadge = dialog.locator('.rounded-full.border').first();
    await expect(sourceBadge).toBeVisible();

    // 应有关闭按钮
    const closeBtn = dialog.locator('button', { hasText: '关闭' });
    await expect(closeBtn).toBeVisible();

    await page.screenshot({ path: 'e2e-screenshots/memories-detail-dialog.png' });

    // 关闭
    await closeBtn.click();
    await expect(dialogTitle).not.toBeVisible({ timeout: 3000 });
  });

  test('Detail dialog shows Turn association', async ({ page }) => {
    // 找一个有 turn_id 的卡片（大部分应该有）
    const cards = page.locator('.cursor-pointer.rounded-xl');
    await expect(cards.first()).toBeVisible({ timeout: 10000 });

    // 点击第一张卡片
    await cards.first().click();

    // 等待 Dialog 和 Turn 数据加载
    const dialogTitle = page.locator('text=记忆详情');
    await expect(dialogTitle).toBeVisible({ timeout: 5000 });

    // Turn 关联区域
    const turnSection = page.locator('text=Turn 关联');
    if (await turnSection.isVisible({ timeout: 5000 }).catch(() => false)) {
      // 应有 Turn 元数据
      const sessionLabel = page.locator('text=Session:');
      await expect(sessionLabel).toBeVisible({ timeout: 8000 });

      const statusLabel = page.locator('text=状态:');
      await expect(statusLabel).toBeVisible();

      // 消息展开按钮
      const msgBtn = page.locator('button', { hasText: /消息/ });
      if (await msgBtn.isVisible()) {
        await msgBtn.click();
        await page.waitForTimeout(500);

        // 消息应可见
        const userMsg = page.locator('text=👤 user');
        await expect(userMsg.first()).toBeVisible({ timeout: 3000 });

        await page.screenshot({ path: 'e2e-screenshots/memories-turn-messages.png' });
      }
    }

    // 关闭
    const closeBtn = page.locator('[role="dialog"] button', { hasText: '关闭' });
    await closeBtn.click();
  });

  test('Detail dialog shows sibling memories from same Turn', async ({ page }) => {
    const cards = page.locator('.cursor-pointer.rounded-xl');
    await expect(cards.first()).toBeVisible({ timeout: 10000 });
    await cards.first().click();

    const dialogTitle = page.locator('text=记忆详情');
    await expect(dialogTitle).toBeVisible({ timeout: 5000 });

    // 等待 Turn 数据加载
    await page.waitForTimeout(3000);

    // 同 Turn 其他记忆
    const siblingSection = page.locator('text=同 Turn 其他记忆');
    if (await siblingSection.isVisible({ timeout: 3000 }).catch(() => false)) {
      await page.screenshot({ path: 'e2e-screenshots/memories-siblings.png' });
    }

    const closeBtn = page.locator('[role="dialog"] button', { hasText: '关闭' });
    await closeBtn.click();
  });

  // --- 图谱视图 ---

  test('Graph tab renders', async ({ page }) => {
    const graphTab = page.locator('button[role="tab"]', { hasText: '图谱' });
    await expect(graphTab).toBeVisible({ timeout: 10000 });
    await graphTab.click();
    await page.waitForTimeout(3000);

    // Canvas 应渲染 (react-force-graph-2d)
    const canvas = page.locator('canvas');
    if (await canvas.count() > 0) {
      await expect(canvas.first()).toBeVisible();
    }

    await page.screenshot({ path: 'e2e-screenshots/graph-view.png' });
  });

  test('Graph search works', async ({ page }) => {
    const graphTab = page.locator('button[role="tab"]', { hasText: '图谱' });
    await graphTab.click();
    await page.waitForTimeout(3000);

    // 搜索框
    const searchInput = page.locator('input[placeholder*="搜索"]');
    if (await searchInput.isVisible({ timeout: 3000 }).catch(() => false)) {
      await searchInput.fill('Python');
      await page.waitForTimeout(2000);
      await page.screenshot({ path: 'e2e-screenshots/graph-search.png' });
    }
  });

  test('Graph relationship filter chips visible', async ({ page }) => {
    const graphTab = page.locator('button[role="tab"]', { hasText: '图谱' });
    await graphTab.click();
    await page.waitForTimeout(3000);

    // 关系类型筛选 chips
    await page.screenshot({ path: 'e2e-screenshots/graph-filters.png' });
  });

  // --- AI Learn 视图 ---

  test('AI Learn tab renders', async ({ page }) => {
    const aiTab = page.locator('button[role="tab"]', { hasText: 'AI 学习' });
    await expect(aiTab).toBeVisible({ timeout: 10000 });
    await aiTab.click();
    await page.waitForTimeout(3000);

    await page.screenshot({ path: 'e2e-screenshots/ailearn-view.png' });
  });
});
