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
  let memoryWrites = 0;
  let preferenceWrites = 0;
  let preference = { automatic_saving: true, revision: "0", reviewed: false };
  let memory = { id: '00000000-0000-0000-0000-000000000002', subject_key: 'project.shy.database',
    category: 'PROJECT', content: 'SHY uses PostgreSQL.', status: 'ACTIVE', revision: 'a'.repeat(64) };
  await page.route('**/api/shy/memories**', async route => {
    const request = route.request();
    if (new URL(request.url()).pathname.endsWith('/preferences')) {
      if (request.method() === 'GET') return route.fulfill({ json: preference });
      const payload = request.postDataJSON();
      assert.equal(payload.confirmed, true);
      assert.equal(payload.expected_revision, preference.revision);
      preferenceWrites++;
      preference = { automatic_saving: payload.automatic_saving, revision: String(preferenceWrites), reviewed: true };
      return route.fulfill({ json: preference });
    }
    if (request.method() === 'GET') return route.fulfill({ json: { records: memory ? [memory] : [], has_more: false } });
    memoryWrites++;
    const payload = request.postDataJSON();
    assert.equal(payload.confirmed, true);
    assert.equal(payload.expected_revision, memory.revision);
    if (request.method() === 'PATCH') memory = { ...memory, content: payload.content, revision: 'b'.repeat(64) };
    else memory = null;
    return route.fulfill({ json: { corrected: true, deleted: memory === null } });
  });
  await page.route('**/api/shy/health', route => route.fulfill({ json: {
    status: 'degraded', system: 'SHY', version: '0.105.3', database_connected: true,
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
  await page.getByText('Conversation summary', { exact: true }).click();
  assert.equal(await page.getByRole('link', { name: 'This is a fixture reply.', exact: true }).count(), 1);
  assert.equal(preferenceWrites, 0);
  await page.getByRole('button', { name: 'Review automatic memory saving', exact: true }).click();
  await page.getByLabel('Allow automatic memory saving', { exact: true }).uncheck();
  assert.equal(await page.getByRole('button', { name: 'Save memory saving setting', exact: true }).isDisabled(), true);
  await page.getByLabel('I confirm this automatic saving setting.', { exact: true }).check();
  await page.getByRole('button', { name: 'Save memory saving setting', exact: true }).click();
  await page.getByText('Automatic memory saving paused.', { exact: true }).waitFor();
  assert.equal(preferenceWrites, 1);
  assert.equal(preference.automatic_saving, false);
  await page.getByRole('button', { name: 'Review saved memories', exact: true }).click();
  await page.getByText('SHY uses PostgreSQL.', { exact: true }).waitFor();
  await page.getByRole('button', { name: 'Correct project.shy.database', exact: true }).click();
  await page.getByLabel('Memory content', { exact: true }).fill('SHY uses PostgreSQL 16.');
  assert.equal(await page.getByRole('button', { name: 'Save reviewed memory', exact: true }).isDisabled(), true);
  assert.equal(memoryWrites, 0, 'memory changes require explicit review');
  await page.getByLabel('I reviewed this exact memory change and confirm it.', { exact: true }).check();
  await page.getByRole('button', { name: 'Save reviewed memory', exact: true }).click();
  await page.getByText('Saved memory updated.', { exact: true }).waitFor();
  await page.getByText('SHY uses PostgreSQL 16.', { exact: true }).waitFor();
  for (const width of [360, 390, 768, 1440]) {
    await page.setViewportSize({ width, height: 1000 });
    assert.equal(await page.evaluate(() => document.documentElement.scrollWidth <= window.innerWidth), true, `memory overflow at ${width}px`);
  }
  await page.getByRole('button', { name: 'Delete project.shy.database', exact: true }).click();
  assert.equal(await page.getByRole('button', { name: 'Confirm deletion', exact: true }).isDisabled(), true);
  await page.getByLabel('I reviewed this exact memory change and confirm it.', { exact: true }).check();
  await page.getByRole('button', { name: 'Confirm deletion', exact: true }).click();
  await page.getByText('Selected saved memory deleted. Original chat history remains.', { exact: true }).waitFor();
  assert.equal(memoryWrites, 2);
  await page.getByLabel('Search conversations').fill('voice check');
  await page.getByRole('button', { name: /SHY voice check/ }).waitFor();
  await page.reload();
  await page.getByRole('button', { name: /SHY voice check/ }).waitFor();
  assert.equal(await page.getByLabel('Allow browser speech services for this session').isChecked(), false);
  assert.equal(await page.evaluate(() => document.documentElement.scrollWidth <= window.innerWidth), true, 'desktop overflow');
  console.log('PASS: voice transcript review, spoken reply, stop, title persistence, history search, summaries, reviewed memory correction/deletion, confirmed automatic-saving pause, mobile overflow, session-only consent (fixtures).');
})().catch(error => { console.error(error); process.exitCode = 1; }).finally(async () => {
  await browser?.close();
  server?.kill();
});
