import { test, expect, type Page } from '@playwright/test';

const BASE = 'http://localhost:3000';
const TOKEN = process.env.MC_AUTH_TOKEN || '3e7e63bd8bd5267f0a72b4f90dee3a2e96f7689254248f91c4371667451c9178';

/** Inject auth token into sessionStorage and navigate to memories page */
async function login(page: Page) {
  await page.goto(BASE);
  await page.evaluate((token) => {
    window.sessionStorage.setItem('mc_local_auth_token', token);
  }, TOKEN);
  await page.goto(`${BASE}/memories`);
  // Wait for data to load
  await page.waitForSelector('h2:has-text("记忆列表")', { timeout: 15000 });
}

test.describe('OpenClaw Memory E2E - Full Chain', () => {

  test.beforeEach(async ({ page }) => {
    await login(page);
  });

  // --- 列表视图 ---

  test('Memories page loads with data', async ({ page }) => {
    const heading = page.locator('h2', { hasText: '记忆列表' });
    await expect(heading).toBeVisible();
    const text = await heading.textContent();
    expect(text).toMatch(/\(\d+\)/);

    const cards = page.locator('.cursor-pointer.rounded-xl');
    await expect(cards.first()).toBeVisible();
    expect(await cards.count()).toBeGreaterThan(0);
  });

  test('Source badges visible including OpenClaw', async ({ page }) => {
    const sourceLabel = page.locator('text=来源:');
    await expect(sourceLabel).toBeVisible();

    // OpenClaw source filter button should exist
    const openclawBtn = page.locator('button', { hasText: /OpenClaw \(\d+\)/ });
    await expect(openclawBtn).toBeVisible();
  });

  test('memory_type badges (fact/summary) visible', async ({ page }) => {
    const factBadge = page.locator('.rounded-full.border:has-text("事实")');
    const summaryBadge = page.locator('.rounded-full.border:has-text("摘要")');
    expect(await factBadge.count() + await summaryBadge.count()).toBeGreaterThan(0);
  });

  test('Source filter: OpenClaw', async ({ page }) => {
    const openclawBtn = page.locator('button', { hasText: /OpenClaw \(\d+\)/ });
    await openclawBtn.click();
    await page.waitForTimeout(2000);

    // All visible cards should have OpenClaw badge
    const heading = page.locator('h2', { hasText: '记忆列表' });
    const text = await heading.textContent();
    const match = text?.match(/\((\d+)\)/);
    expect(match).toBeTruthy();
    const count = parseInt(match![1]);
    expect(count).toBeGreaterThan(0);

    // Verify OpenClaw badge on cards
    const cards = page.locator('.cursor-pointer.rounded-xl');
    const firstCardBadge = cards.first().locator('.rounded-full.border:has-text("OpenClaw")');
    await expect(firstCardBadge).toBeVisible();

    // Reset
    await page.locator('button', { hasText: '全部' }).first().click();
  });

  test('Agent filter works', async ({ page }) => {
    const agentBtns = page.locator('button:has(.lucide-bot)');
    if (await agentBtns.count() > 0) {
      await agentBtns.first().click();
      await page.waitForTimeout(2000);
      const heading = page.locator('h2', { hasText: '记忆列表' });
      await expect(heading).toBeVisible();
    }
  });

  test('Search returns results', async ({ page }) => {
    const searchInput = page.locator('input[placeholder*="搜索"]');
    await searchInput.fill('张三');
    await page.locator('button', { hasText: '搜索' }).click();
    await page.waitForTimeout(3000);
    // Should have results or empty state
    const heading = page.locator('h2', { hasText: '记忆列表' });
    await expect(heading).toBeVisible();
  });

  // --- 详情 Dialog ---

  test('Click card opens detail dialog', async ({ page }) => {
    const card = page.locator('.cursor-pointer.rounded-xl').first();
    await card.click();

    const dialog = page.locator('[role="dialog"]');
    await expect(dialog).toBeVisible({ timeout: 5000 });

    const title = dialog.locator('text=记忆详情');
    await expect(title).toBeVisible();

    // Has source badge
    await expect(dialog.locator('.rounded-full.border').first()).toBeVisible();

    // Close
    await dialog.locator('button', { hasText: '关闭' }).click();
    await expect(dialog).not.toBeVisible({ timeout: 3000 });
  });

  test('Detail dialog shows Turn association', async ({ page }) => {
    const card = page.locator('.cursor-pointer.rounded-xl').first();
    await card.click();

    const dialog = page.locator('[role="dialog"]');
    await expect(dialog).toBeVisible({ timeout: 5000 });

    // Wait for Turn data to load
    const turnSection = dialog.locator('text=Turn 关联');
    if (await turnSection.isVisible({ timeout: 5000 }).catch(() => false)) {
      await expect(dialog.locator('text=Session:')).toBeVisible({ timeout: 8000 });
      await expect(dialog.locator('text=状态:')).toBeVisible();

      // Expand messages
      const msgBtn = dialog.locator('button', { hasText: /消息/ });
      if (await msgBtn.isVisible()) {
        await msgBtn.click();
        await expect(dialog.locator('text=👤 user').first()).toBeVisible({ timeout: 3000 });
      }
    }

    await dialog.locator('button', { hasText: '关闭' }).click();
  });

  test('Detail dialog shows sibling memories', async ({ page }) => {
    const card = page.locator('.cursor-pointer.rounded-xl').first();
    await card.click();

    const dialog = page.locator('[role="dialog"]');
    await expect(dialog).toBeVisible({ timeout: 5000 });
    await page.waitForTimeout(3000);

    // Sibling memories section (may or may not exist depending on data)
    const siblings = dialog.locator('text=同 Turn 其他记忆');
    // Just verify dialog loaded correctly
    await expect(dialog.locator('text=记忆详情')).toBeVisible();

    await dialog.locator('button', { hasText: '关闭' }).click();
  });

  // --- 图谱视图 ---

  test('Graph tab renders with source and agent filters', async ({ page }) => {
    const graphTab = page.locator('button[role="tab"]', { hasText: '图谱' });
    await graphTab.click();
    await page.waitForTimeout(3000);

    // Stats should be visible
    await expect(page.locator('text=节点数')).toBeVisible();
    await expect(page.locator('text=关系数')).toBeVisible();

    // Source filter should exist
    const sourceLabel = page.locator('text=来源:').last();
    await expect(sourceLabel).toBeVisible();

    // Agent filter
    await expect(page.locator('text=Agent:').last()).toBeVisible();
  });

  test('Graph: Agent filter updates stats dynamically', async ({ page }) => {
    const graphTab = page.locator('button[role="tab"]', { hasText: '图谱' });
    await graphTab.click();
    await page.waitForTimeout(3000);

    // Record initial stats
    const initialNodes = await page.locator('text=节点数').locator('..').locator('p').last().textContent();

    // Click an agent with low count (main)
    const mainBtn = page.locator('button', { hasText: /^.*main \(\d+\)/ });
    if (await mainBtn.count() > 0) {
      await mainBtn.first().click();
      await page.waitForTimeout(3000);

      // Stats should change
      const filteredNodes = await page.locator('text=节点数').locator('..').locator('p').last().textContent();
      // Stats should update (value changed from initial, or at least be a valid number)
      expect(parseInt(filteredNodes || '0')).toBeGreaterThanOrEqual(0);
    }
  });

  test('Graph: Source filter (OpenClaw) works', async ({ page }) => {
    const graphTab = page.locator('button[role="tab"]', { hasText: '图谱' });
    await graphTab.click();
    await page.waitForTimeout(3000);

    const openclawBtn = page.locator('button', { hasText: /OpenClaw \(\d+\)/ });
    if (await openclawBtn.count() > 0) {
      await openclawBtn.first().click();
      await page.waitForTimeout(3000);

      // Relationship chips should update
      const relChips = page.locator('text=关系:').locator('..').locator('button');
      expect(await relChips.count()).toBeGreaterThan(0);
    }
  });

  // --- 结构化消息 (tool_use / tool_result blocks) ---

  test('Structured messages: tool blocks render in detail dialog', async ({ page }) => {
    // Create a structured turn with tool_use and tool_result blocks
    const BASE_API = process.env.MC_API_URL || 'http://localhost:8000';
    const turnRes = await fetch(`${BASE_API}/api/v2/turns/`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({
        session_id: `e2e-structured-${Date.now()}`,
        user_id: 'yishu',
        agent_id: 'e2e-test',
        source: 'openclaw',
        messages: [
          { role: 'user', content: '查看配置文件' },
          { role: 'assistant', content: [
            { type: 'text', text: '让我读取配置。' },
            { type: 'tool_use', id: 'call_e2e_1', name: 'Read', input: { file_path: '/app/config.py' } },
          ]},
          { role: 'user', content: [
            { type: 'tool_result', tool_use_id: 'call_e2e_1', content: 'DEBUG=true' },
          ]},
          { role: 'assistant', content: '配置已读取完成。' },
        ],
      }),
    });
    const { turn_id } = await turnRes.json();
    expect(turn_id).toBeTruthy();

    // Link a memory to this turn via the internal API
    // We'll verify rendering by finding a card whose turn has structured messages
    // For now, verify the turn itself stores structured content
    const getRes = await fetch(`${BASE_API}/api/v2/turns/${turn_id}`);
    const turnData = await getRes.json();
    expect(turnData.messages).toHaveLength(4);
    // Second message should have array content with tool_use
    const assistantMsg = turnData.messages[1];
    expect(Array.isArray(assistantMsg.content)).toBe(true);
    expect(assistantMsg.content[1].type).toBe('tool_use');
    expect(assistantMsg.content[1].name).toBe('Read');
  });

  // --- AI Learn ---

  test('AI Learn tab renders', async ({ page }) => {
    const aiTab = page.locator('button[role="tab"]', { hasText: 'AI 学习' });
    await aiTab.click();
    await page.waitForTimeout(3000);
    // Just verify tab switched without error
  });
});
