const fs = require('fs');
const path = require('path');
const { chromium } = require('playwright');

const baseUrl = 'http://localhost:3000';
const outDir = 'C:/SHY/apps/web/acceptance-artifacts';

(async () => {
  const browser = await chromium.launch({ channel: 'msedge', headless: true });
  const context = await browser.newContext({ viewport: { width: 1440, height: 900 } });
  const page = await context.newPage();

  const consoleMessages = [];
  const pageErrors = [];
  const failedRequests = [];
  page.on('console', (msg) => {
    consoleMessages.push({ type: msg.type(), text: msg.text() });
  });
  page.on('pageerror', (err) => pageErrors.push(String(err)));
  page.on('requestfailed', (req) => failedRequests.push({ url: req.url(), failure: req.failure()?.errorText || 'unknown' }));

  const result = {
    server: { url: baseUrl, reachable: false },
    emptyState: {},
    normalChat: {},
    research: {},
    conversationUX: {},
    composer: {},
    status: {},
    failureUX: {},
    responsive: {},
    console: {},
    screenshots: [],
  };

  async function screenshot(name) {
    const filePath = path.join(outDir, name);
    result.screenshots.push(filePath);
    await page.screenshot({ path: filePath, fullPage: true });
  }

  await page.goto(baseUrl, { waitUntil: 'networkidle', timeout: 120000 });
  result.server.reachable = true;
  await screenshot('01-desktop-empty-1440.png');

  result.emptyState.brandingVisible = (await page.getByRole('heading', { name: 'SHY' }).count()) > 0;
  result.emptyState.helpVisible = (await page.getByText('How can I help you?').count()) > 0;
  result.emptyState.composerVisible = await page.locator('#shy-composer-input').isVisible();

  const textarea = page.locator('#shy-composer-input');
  await textarea.click();
  await textarea.fill('Why is the sky blue?');
  await page.keyboard.press('Enter');
  await page.waitForSelector('.shy-message[data-role="assistant"]', { timeout: 120000 });
  await page.waitForTimeout(1000);
  await screenshot('02-after-normal-chat-1440.png');

  const assistantMessages = page.locator('.shy-message[data-role="assistant"] .shy-markdown');
  const lastAssistant = assistantMessages.last();
  const normalChatText = (await lastAssistant.textContent()) || '';
  result.normalChat.succeeded = normalChatText.trim().length > 0;
  result.normalChat.nonEmpty = normalChatText.trim().length > 0;
  result.normalChat.rawJsonVisible = normalChatText.includes('{') && normalChatText.includes('"status"');
  result.normalChat.internalPromptLeak = /UNTRUSTED EXTERNAL EVIDENCE|You are SHY, a high-capability AI system/i.test(normalChatText);
  result.normalChat.secretLeak = /TAVILY_API_KEY|sk-|api_key/i.test(normalChatText);

  await textarea.fill('Research the latest public information about NVIDIA Blackwell.');
  await page.keyboard.press('Enter');
  await page.waitForTimeout(500);
  await page.waitForSelector('.shy-source-card', { timeout: 180000 });
  await screenshot('03-after-research-1440.png');

  const allAssistant = page.locator('.shy-message[data-role="assistant"]');
  const researchMsg = allAssistant.last();
  const researchText = (await researchMsg.textContent()) || '';
  const sourceCards = page.locator('.shy-source-card');
  const sourceCount = await sourceCards.count();
  const citationMatch = researchText.match(/\[[1-9][0-9]*\]/g) || [];

  result.research.webSearchShown = (await researchMsg.getByText('web.search').count()) > 0;
  result.research.synthesizedResponsePresent = researchText.trim().length > 0;
  result.research.citationsPresent = citationMatch.length > 0;
  result.research.structuredSourceCardsPresent = sourceCount > 0;
  result.research.sourceCount = sourceCount;

  let clickableLinks = 0;
  let invalidLinks = 0;
  for (let i = 0; i < sourceCount; i++) {
    const href = await sourceCards.nth(i).locator('a').getAttribute('href');
    if (href && /^https?:\/\//.test(href)) clickableLinks += 1;
    else invalidLinks += 1;
  }
  result.research.clickableSourceLinks = clickableLinks;
  result.research.invalidSourceLinks = invalidLinks;

  await page.locator('.shy-sidebar .shy-button', { hasText: 'New chat' }).first().click();
  await page.waitForTimeout(400);
  result.conversationUX.newChatWorks = (await page.getByText('How can I help you?').count()) > 0;
  await textarea.fill('Conversation title seed message');
  await page.keyboard.press('Enter');
  await page.waitForSelector('.shy-message[data-role="assistant"]', { timeout: 120000 });
  const threadButtons = page.locator('.shy-thread-button');
  const threadCount = await threadButtons.count();
  result.conversationUX.sidebarUpdated = threadCount >= 2;
  result.conversationUX.firstMessageCreatesTitle = (await page.getByRole('button', { name: /Conversation title seed message/ }).count()) > 0;

  if (threadCount >= 2) {
    await threadButtons.first().click();
    await page.waitForTimeout(250);
    await threadButtons.nth(1).click();
    await page.waitForTimeout(250);
    result.conversationUX.switchingWorks = true;
  } else {
    result.conversationUX.switchingWorks = false;
  }

  await page.reload({ waitUntil: 'networkidle' });
  result.conversationUX.persistsAfterRefresh = (await page.locator('.shy-thread-button').count()) >= 2;

  await textarea.click();
  await textarea.fill('Line one');
  await page.keyboard.down('Shift');
  await page.keyboard.press('Enter');
  await page.keyboard.up('Shift');
  await page.keyboard.type('Line two');
  const val = await textarea.inputValue();
  result.composer.shiftEnterCreatesNewline = val.includes('\n');
  await page.keyboard.press('Enter');
  await page.waitForTimeout(300);
  result.composer.enterSends = await page
    .locator('.shy-message[data-role="user"]')
    .last()
    .textContent()
    .then((t) => (t || '').includes('Line one'));
  const sendButton = page.getByRole('button', { name: 'Send' });
  result.composer.loadingStateVisible = await sendButton.isDisabled();

  await page.getByRole('button', { name: /Refresh status/i }).click();
  await page.waitForTimeout(800);
  const statusPanel = page.locator('.shy-status-panel');
  result.status.shyVisible = (await statusPanel.getByText('SHY').count()) > 0;
  result.status.versionVisible = (await statusPanel.getByText('0.11.0').count()) > 0;
  result.status.modelVisible = (await statusPanel.getByText('qwen3.5:4b').count()) > 0;
  result.status.ollamaConnectedVisible = (await statusPanel.getByText('Connected').count()) > 0;

  await page.route('**/api/shy/agent', (route) => route.abort('failed'));
  await textarea.fill('This should fail cleanly');
  await page.keyboard.press('Enter');
  await page.waitForSelector('.shy-failure', { timeout: 30000 });
  result.failureUX.userFriendlyError = (await page.getByText('Request failed.').count()) > 0;
  const failureText = (await page.locator('.shy-failure').last().textContent()) || '';
  result.failureUX.noStackTrace = !/Error:\s|at\s[A-Za-z]|Traceback/i.test(failureText);
  result.failureUX.noSecretLeak = !/TAVILY_API_KEY|api_key|sk-/i.test(failureText);
  await page.unroute('**/api/shy/agent');

  const widths = [360, 390, 430, 768, 1440];
  for (const width of widths) {
    await page.setViewportSize({ width, height: 900 });
    await page.waitForTimeout(300);
    const hasOverflow = await page.evaluate(() => document.documentElement.scrollWidth > document.documentElement.clientWidth);
    const composerVisible = await page.locator('#shy-composer-input').isVisible();
    const sourceCardsVisible = (await page.locator('.shy-source-card').count()) > 0;
    const drawerToggleVisible = await page.locator('.shy-mobile-toggle').first().isVisible();
    result.responsive[String(width)] = {
      horizontalOverflow: hasOverflow,
      composerVisible,
      sourceCardsVisible,
      drawerToggleVisible,
    };
    await screenshot(`responsive-${width}.png`);
  }

  result.console.javascriptErrors = pageErrors;
  result.console.consoleErrors = consoleMessages.filter((m) => m.type === 'error');
  result.console.hydrationWarnings = consoleMessages.filter((m) => /hydration|did not match|server HTML/i.test(m.text));
  result.console.failedRequests = failedRequests;

  const outPath = path.join(outDir, 'acceptance-report.json');
  fs.writeFileSync(outPath, JSON.stringify(result, null, 2), 'utf-8');
  console.log(JSON.stringify({ report: outPath, screenshots: result.screenshots, summary: result }, null, 2));

  await browser.close();
})();
