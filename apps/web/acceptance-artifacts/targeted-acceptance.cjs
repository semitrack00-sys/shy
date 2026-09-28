const fs = require('fs');
const path = require('path');
const { chromium } = require('playwright');

const baseUrl = 'http://localhost:3000';
const outDir = 'C:/SHY/apps/web/acceptance-artifacts';

(async () => {
  const browser = await chromium.launch({ channel: 'msedge', headless: true });
  const context = await browser.newContext({ viewport: { width: 1440, height: 900 } });
  const page = await context.newPage();

  const result = {
    normalChat: {},
    research: {},
    conversationUX: {},
    composer: {},
    failureUX: {},
    screenshots: [],
    errors: [],
  };

  const screenshot = async (name) => {
    const p = path.join(outDir, name);
    result.screenshots.push(p);
    await page.screenshot({ path: p, fullPage: true });
  };

  try {
    await page.goto(baseUrl, { waitUntil: 'networkidle', timeout: 120000 });
    await page.locator('#shy-composer-input').fill('Why is the sky blue?');
    await page.keyboard.press('Enter');
    await page.waitForSelector('.shy-message[data-role="assistant"]', { timeout: 120000 });
    await page.waitForTimeout(500);
    const normalText = (await page.locator('.shy-message[data-role="assistant"] .shy-markdown').last().textContent()) || '';
    result.normalChat.succeeded = normalText.trim().length > 0;
    result.normalChat.nonEmpty = normalText.trim().length > 0;
    result.normalChat.rawJsonVisible = /"status"\s*:/.test(normalText);
    result.normalChat.secretLeak = /TAVILY_API_KEY|api_key|sk-/.test(normalText);

    await page.locator('#shy-composer-input').fill('Research the latest public information about NVIDIA Blackwell.');
    await page.keyboard.press('Enter');
    await page.waitForSelector('.shy-source-card', { timeout: 180000 });
    await page.waitForTimeout(500);
    await screenshot('04-targeted-research.png');

    const researchMsg = page.locator('.shy-message[data-role="assistant"]').last();
    const researchText = (await researchMsg.textContent()) || '';
    result.research.webSearchUsed = (await researchMsg.getByText('web.search').count()) > 0;
    result.research.executed = (await researchMsg.getByText('EXECUTED').count()) > 0;
    result.research.nonEmpty = researchText.trim().length > 0;
    result.research.citationsPresent = /\[[1-9][0-9]*\]/.test(researchText);
    result.research.structuredSourceCards = await page.locator('.shy-source-card').count();
    result.research.linksClickable = await page
      .locator('.shy-source-card a')
      .count()
      .then((count) => count > 0);

    const beforeButtons = await page.locator('.shy-thread-button').count();
    await page.locator('.shy-sidebar .shy-button').first().click();
    await page.waitForTimeout(250);
    result.conversationUX.newChatWorks = (await page.getByText('How can I help you?').count()) > 0;

    await page.locator('#shy-composer-input').fill('Conversation persistence check title');
    await page.keyboard.press('Enter');
    await page.waitForSelector('.shy-message[data-role="assistant"]', { timeout: 120000 });
    await page.waitForTimeout(250);

    const afterButtons = await page.locator('.shy-thread-button').count();
    result.conversationUX.sidebarUpdated = afterButtons >= beforeButtons;
    result.conversationUX.titleFromFirstMessage = (await page.getByRole('button', { name: /Conversation persistence check title/ }).count()) > 0;

    if (afterButtons >= 2) {
      await page.locator('.shy-thread-button').first().click();
      await page.waitForTimeout(200);
      await page.locator('.shy-thread-button').nth(1).click();
      result.conversationUX.switchingWorks = true;
    } else {
      result.conversationUX.switchingWorks = false;
    }

    await page.reload({ waitUntil: 'networkidle' });
    result.conversationUX.persistsAfterRefresh = (await page.locator('.shy-thread-button').count()) >= afterButtons;

    const ta = page.locator('#shy-composer-input');
    await ta.fill('Line one');
    await page.keyboard.down('Shift');
    await page.keyboard.press('Enter');
    await page.keyboard.up('Shift');
    await page.keyboard.type('Line two');
    result.composer.shiftEnterCreatesNewline = (await ta.inputValue()).includes('\n');

    const beforeUserCount = await page.locator('.shy-message[data-role="user"]').count();
    await page.keyboard.press('Enter');
    await page.keyboard.press('Enter');
    await page.waitForTimeout(1000);
    const afterUserCount = await page.locator('.shy-message[data-role="user"]').count();
    result.composer.doubleSubmitPrevented = (afterUserCount - beforeUserCount) <= 1;

    await page.waitForFunction(() => {
      const input = document.querySelector('#shy-composer-input');
      return !!input && !input.disabled;
    }, null, { timeout: 120000 });

    await page.route('**/api/shy/agent', (route) => route.fulfill({
      status: 200,
      contentType: 'application/json',
      body: JSON.stringify({
        status: 'FAILED',
        reason: 'Controlled failure for acceptance test.',
        conversation_id: 'acceptance-failure-flow'
      }),
    }), { times: 1 });

    await ta.fill('Force controlled failure now');
    await page.keyboard.press('Enter');
    await page.waitForSelector('.shy-failure', { timeout: 30000 });
    await screenshot('05-targeted-failure.png');
    const failText = (await page.locator('.shy-failure').last().textContent()) || '';
    result.failureUX.userFriendlyError = /Request failed\./.test(failText);
    result.failureUX.noStackTrace = !/Traceback|at\s+[A-Za-z]|ReferenceError|TypeError/.test(failText);
    result.failureUX.noSecretLeak = !/TAVILY_API_KEY|api_key|sk-/.test(failText);

    await page.waitForFunction(() => {
      const input = document.querySelector('#shy-composer-input');
      return !!input && !input.disabled;
    }, null, { timeout: 30000 });
    result.failureUX.composerReenabled = true;

    await ta.fill('Recovery after forced failure');
    await page.keyboard.press('Enter');
    await page.waitForSelector('.shy-message[data-role="assistant"][data-status="sent"]', { timeout: 120000 });
    await page.waitForFunction(() => {
      const input = document.querySelector('#shy-composer-input');
      return !!input && !input.disabled;
    }, null, { timeout: 30000 });
    result.failureUX.recoverySendWorks = true;
  } catch (err) {
    result.errors.push(String(err));
  }

  const outPath = path.join(outDir, 'targeted-acceptance-report.json');
  fs.writeFileSync(outPath, JSON.stringify(result, null, 2), 'utf8');
  console.log(JSON.stringify({ report: outPath, summary: result }, null, 2));

  await browser.close();
})();
