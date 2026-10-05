const { chromium } = require('playwright');
const assert = require('node:assert/strict');
const { spawn } = require('node:child_process');
const path = require('node:path');
let server;
let browser;

(async () => {
  server = spawn(process.execPath, [require.resolve('next/dist/bin/next'), 'start', '--hostname', '127.0.0.1', '--port', '3000'], { cwd: path.resolve(__dirname, '..'), stdio: 'ignore' });
  const deadline = Date.now() + 30000;
  while (true) {
    try { const response = await fetch('http://127.0.0.1:3000'); if (response.ok) break; } catch {}
    if (Date.now() > deadline) throw new Error('Web server readiness timed out');
    await new Promise(resolve => setTimeout(resolve, 250));
  }
  browser = await chromium.launch({ headless: true });
  const page = await browser.newPage({ viewport: { width: 390, height: 844 } });
  await page.addInitScript(() => {
    class Recognition {
      processLocally = true;
      start() { window.voiceFixture.recognition = this; }
      stop() { this.onend?.(); }
      abort() { this.onend?.(); }
    }
    class Utterance { constructor(text) { this.text = text; } }
    Object.defineProperty(window, 'SpeechSynthesisUtterance', { value: Utterance, configurable: true });
    window.voiceFixture = { recognition: null, spoken: [], cancelled: 0 };
    Object.defineProperty(window, 'SpeechRecognition', { value: Recognition, configurable: true });
    Object.defineProperty(window, 'speechSynthesis', { configurable: true, value: {
      cancel() { window.voiceFixture.cancelled++; },
      speak(utterance) { window.voiceFixture.spoken.push(utterance.text); },
      getVoices() { return [{ voiceURI: 'test-local', name: 'Fixture voice', lang: 'en-US', localService: true }]; },
      addEventListener() {}, removeEventListener() {},
    } });
  });
  let submitted = 0;
  await page.route('**/api/shy/health', route => route.fulfill({ json: {
    status: 'degraded', system: 'SHY', version: '0.103.0', database_connected: true,
    ollama_connected: false, local_model_available: false,
  } }));
  await page.route('**/api/shy/agent', route => {
    submitted++;
    return route.fulfill({ json: { status: 'RESPOND', message: 'This is a fixture reply.', conversation_id: 'fixture' } });
  });
  await page.goto('http://127.0.0.1:3000');
  await page.getByRole('button', { name: 'Speak to SHY' }).click();
  await page.evaluate(() => window.voiceFixture.recognition.onresult({ results: [{ isFinal: true, 0: { transcript: 'Hello SHY from a voice fixture' } }] }));
  await page.waitForFunction(() => document.querySelector('#shy-composer-input').value === 'Hello SHY from a voice fixture');
  assert.equal(await page.getByLabel('Message SHY', { exact: true }).inputValue(), 'Hello SHY from a voice fixture');
  assert.equal(submitted, 0, 'voice transcript must not be auto-submitted');
  await page.getByText('Voice settings and privacy', { exact: true }).click();
  await page.getByLabel('Read new replies aloud').check();
  await page.getByRole('button', { name: 'Send', exact: true }).click();
  await page.getByText('This is a fixture reply.', { exact: true }).waitFor();
  await page.waitForFunction(() => window.voiceFixture.spoken.length === 1);
  await page.getByRole('button', { name: 'Stop voice' }).click();
  assert.equal(await page.getByRole('button', { name: 'Stop voice' }).isDisabled(), true);
  assert.equal(await page.evaluate(() => document.documentElement.scrollWidth <= window.innerWidth), true, 'mobile overflow');
  for (const width of [360, 390, 768]) {
    await page.setViewportSize({ width, height: 844 });
    assert.equal(await page.evaluate(() => document.documentElement.scrollWidth <= window.innerWidth), true, `overflow at ${width}px`);
  }
  await page.setViewportSize({ width: 1440, height: 1000 });
  await page.getByRole('button', { name: 'Settings', exact: true }).click();
  await page.getByLabel('Conversation title', { exact: true }).fill('SHY voice check');
  await page.getByRole('button', { name: 'Save title', exact: true }).click();
  await page.getByLabel('Search conversations').fill('voice check');
  await page.getByRole('button', { name: /SHY voice check/ }).waitFor();
  await page.reload();
  await page.getByRole('button', { name: /SHY voice check/ }).waitFor();
  assert.equal(await page.getByLabel('Allow browser speech services for this session').isChecked(), false);
  assert.equal(await page.evaluate(() => document.documentElement.scrollWidth <= window.innerWidth), true, 'desktop overflow');
  console.log('PASS: voice transcript review, spoken reply, stop, title persistence, history search, mobile overflow, session-only consent (fixtures).');
})().catch(error => { console.error(error); process.exitCode = 1; }).finally(async () => {
  await browser?.close();
  server?.kill();
});
