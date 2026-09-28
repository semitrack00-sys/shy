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
  page.on('console', (msg) => consoleMessages.push({ type: msg.type(), text: msg.text() }));
  page.on('pageerror', (err) => pageErrors.push(String(err)));
  page.on('requestfailed', (req) => failedRequests.push({ url: req.url(), failure: req.failure()?.errorText || 'unknown' }));

  await page.goto(baseUrl, { waitUntil: 'networkidle', timeout: 120000 });

  const responsive = {};
  const widths = [360, 390, 430, 768, 1440];
  for (const width of widths) {
    await page.setViewportSize({ width, height: 900 });
    await page.waitForTimeout(250);
    const hasOverflow = await page.evaluate(() => document.documentElement.scrollWidth > document.documentElement.clientWidth);
    const composerVisible = await page.locator('#shy-composer-input').isVisible();
    const sourceCardsVisible = (await page.locator('.shy-source-card').count()) > 0;
    const drawerToggleVisible = await page.locator('.shy-mobile-toggle').first().isVisible();
    const filePath = path.join(outDir, `responsive-${width}.png`);
    await page.screenshot({ path: filePath, fullPage: true });
    responsive[String(width)] = {
      horizontalOverflow: hasOverflow,
      composerVisible,
      sourceCardsVisible,
      drawerToggleVisible,
      screenshot: filePath,
    };
  }

  const report = {
    responsive,
    conversationButtons: await page.locator('.shy-thread-button').count(),
    consoleErrors: consoleMessages.filter((m) => m.type === 'error'),
    hydrationWarnings: consoleMessages.filter((m) => /hydration|did not match|server HTML/i.test(m.text)),
    pageErrors,
    failedRequests,
  };

  const outPath = path.join(outDir, 'responsive-console-report.json');
  fs.writeFileSync(outPath, JSON.stringify(report, null, 2), 'utf8');
  console.log(JSON.stringify({ report: outPath, summary: report }, null, 2));

  await browser.close();
})();
