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
  let lastChatBody;
  let lastMemoryUrl;
  let memoryWrites = 0;
  let preferenceWrites = 0;
  let replyWrites = 0;
  const replyProfiles = new Map();
  const defaultReply = {enabled:false,language:"auto",detail:"standard",tone:"plain",revision:"0",reviewed:false};
  let preference = { automatic_saving: true, revision: "0", reviewed: false };
  let memory = { id: '00000000-0000-0000-0000-000000000002', subject_key: 'project.shy.database',
    category: 'PROJECT', content: 'SHY uses PostgreSQL.', status: 'ACTIVE', revision: 'a'.repeat(64) };
  await page.route('**/api/shy/memories**', async route => {
    const request = route.request();
    lastMemoryUrl = request.url();
    if (new URL(request.url()).pathname.endsWith('/response-preferences')) {
      const project=new URL(request.url()).searchParams.get('project_id') ?? 'default';
      const current=replyProfiles.get(project) ?? defaultReply;
      if(request.method()==='GET')return route.fulfill({json:current});
      const payload=request.postDataJSON();assert.equal(payload.confirmed,true);assert.equal(payload.expected_revision,current.revision);
      replyWrites++;const updated={enabled:payload.enabled,language:payload.language,detail:payload.detail,tone:payload.tone,revision:String(Number(current.revision)+1),reviewed:true};replyProfiles.set(project,updated);
      return route.fulfill({json:updated});
    }
    if (new URL(request.url()).pathname.endsWith('/preferences')) {
      if (request.method() === 'GET') return route.fulfill({ json: preference });
      const payload = request.postDataJSON();
      assert.equal(payload.confirmed, true);
      assert.equal(payload.expected_revision, preference.revision);
      preferenceWrites++;
      preference = { automatic_saving: payload.automatic_saving, revision: String(preferenceWrites), reviewed: true };
      return route.fulfill({ json: preference });
    }
    if (new URL(request.url()).pathname.endsWith('/preview')) {
      const payload=request.postDataJSON();
      assert.equal(payload.confirmed,undefined);
      assert.equal(payload.subject_key,memory.subject_key);
      return route.fulfill({json:{status:'review_required',records:[memory],saved:false,semantic_conflict_verified:false,multiple_active_records:false}});
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
  let documentWrites = 0;
  let extractionRequests = 0;
  let document = null;
  let showComparisonFixture = false;
  const comparisonSource = {id:"00000000-0000-0000-0000-000000000004",name:"reordered.txt",kind:"text",revision:"e".repeat(64),characters:24};
  await page.route('**/api/shy/documents**', async route => {
    const request = route.request();
    const url = new URL(request.url());
    assert.equal(url.searchParams.get('project_id'), 'gud-express');
    if (request.method() === 'GET') return route.fulfill({ json: { documents:document ? (showComparisonFixture ? [document,comparisonSource] : [document]) : [] } });
    const payload = request.postDataJSON();
    if (url.pathname.endsWith('/extract')) {
      extractionRequests++;
      assert.equal(payload.confirmed, true);
      assert.equal(payload.kind, 'pdf');
      return route.fulfill({ json: { content:'[Extracted PDF fixture text]\nSource excerpt.',binary_stored:false } });
    }
    if (url.pathname.endsWith('/search')) {
      assert.deepEqual(payload.document_ids, [document.id]);
      return route.fulfill({ json: { evidence:[{document_id:document.id,name:document.name,revision:document.revision,
        chunk:1,start_line:1,end_line:2,excerpt:document.content}] } });
    }
    if (url.pathname.endsWith('/compare')) {
      assert.deepEqual(payload.document_ids,[document.id,comparisonSource.id]);
      return route.fulfill({json:{documents:[document,comparisonSource],common_unique_lines:1,unique_line_counts:[1,0],differences:[[{line:2,text:'Source line two.'}],[]],semantic_equivalence_checked:false,ordered_comparison:{status:'evaluated',method:'ordered_logical_lines',line_limit:1000,left_line_count:2,right_line_count:1,inserted_lines:0,deleted_lines:1,equal_lines:1,text_identical:false,line_sequence_equal:false,line_endings_compared:false,semantic_equivalence_checked:false,minimal_patch_guaranteed:false,change_hunk_count:1,hunks:[{kind:'delete',left:{start_line:2,line_count:1,samples:[{line:2,text:'Source line two.',truncated:false}],omitted_lines:0},right:{start_line:2,line_count:0,samples:[],omitted_lines:0}}],omitted_hunks:0,preview_truncated:false,hunk_limit:10,sample_lines_per_side:2,sample_character_limit:150}}});
    }
    documentWrites++;
    assert.equal(payload.confirmed, true);
    if (document) assert.equal(payload.expected_revision, document.revision);
    if (url.pathname.endsWith('/delete')) document = null;
    else document = { id:'00000000-0000-0000-0000-000000000003',name:payload.name,kind:payload.kind,
      revision:(documentWrites === 1 ? 'c' : 'd').repeat(64),characters:payload.content.length,content:payload.content };
    return route.fulfill({ json: { document, deleted:document === null } });
  });
  await page.route('**/api/shy/health', route => route.fulfill({ json: {
    status: 'degraded', system: 'SHY', version: '0.105.26', database_connected: true,
    ollama_connected: false, local_model_available: false,
  } }));
  await page.route('**/api/shy/agent', route => {
    submitted++;
    lastChatBody = route.request().postDataJSON();
    if (lastChatBody.document_question) {
      assert.deepEqual(lastChatBody.document_question.document_ids,[document.id]);
      if (lastChatBody.document_question.answer_mode === 'local_answer') {
        assert.equal(lastChatBody.document_question.confirmed_local_generation,true);
        return route.fulfill({json:{status:'RESPOND',message:'Local document answer fixture: PostgreSQL [1].',conversation_id:'fixture',document_answer:{method:'local_keyword_search',answer_kind:'model_answer_from_selected_excerpts',model_invoked:true,semantic_support_verified:false,citation_membership_checked:true,cited_source_numbers:[1],found_evidence:true,selected_documents:[document.id],evidence:[{number:1,document_id:document.id,name:document.name,revision:document.revision,chunk:1,start_line:1,end_line:2,excerpt:document.content}]}}});
      }
      return route.fulfill({json:{status:'RESPOND',message:'Selected excerpt fixture: [untrusted](https://evil.example) PostgreSQL.',conversation_id:'fixture',document_answer:{method:'local_keyword_search',answer_kind:'verbatim_evidence_excerpts_not_generated_claims',model_invoked:false,semantic_support_verified:false,found_evidence:true,selected_documents:[document.id],evidence:[{document_id:document.id,name:document.name,revision:document.revision,chunk:1,start_line:1,end_line:2,excerpt:document.content}]}}});
    }
    if (lastChatBody.research_request) return route.fulfill({json:{status:'RESPOND',message:'Explicit historical research fixture needs source text.',conversation_id:'fixture',research_answer:{mode:'missing_excerpts',model_invoked:false,semantic_truth_verified:false,source_count:1,date_window_days:null,date_window_basis:'user_selected'}}});
    if (lastChatBody.option_comparison) return route.fulfill({json:{status:'RESPOND',message:'Comparison fixture: A scores 100.000000; B scores 0.000000.',conversation_id:'fixture'}});
    if (lastChatBody.message === 'Research context fixture') return route.fulfill({ json: {
      status:'RESPOND',message:'Please provide newer dated evidence.',conversation_id:'fixture',
      research_answer:{mode:'missing_recent_evidence',model_invoked:false,semantic_truth_verified:false,source_count:1,date_window_days:7,date_window_basis:'english_hint'},
      sources:[{number:1,title:'Research context source',url:'https://example.com/context',source:'example.com',source_date_status:'unknown'}],
    } });
    return route.fulfill({ json: { status: 'RESPOND', message: 'This is a fixture reply.', conversation_id: 'fixture' } });
  });
  await page.goto('http://127.0.0.1:3000');
  await page.locator('.shy-avatar--welcome img').waitFor();
  await page.waitForFunction(() => [...document.querySelectorAll('.shy-avatar img')].every(image => image.complete && image.naturalWidth > 0));
  assert.equal(await page.getByText('AI avatar', {exact:true}).count(), 2);
  for (const width of [390, 1440]) {
    await page.setViewportSize({width, height:900});
    assert.equal(await page.evaluate(() => document.documentElement.scrollWidth > document.documentElement.clientWidth), false, 'Avatar must not cause horizontal overflow');
    if (process.env.SHY_AVATAR_SCREENSHOTS) {
      require('node:fs').mkdirSync(process.env.SHY_AVATAR_SCREENSHOTS, {recursive:true});
      await page.screenshot({path:require('node:path').join(process.env.SHY_AVATAR_SCREENSHOTS, `shy-avatar-${width}.png`), fullPage:false});
    }
  }
  await page.setViewportSize({width:390,height:844});
  await page.getByRole('button', { name: 'Speak to SHY' }).click();
  assert.equal(await page.locator('.shy-avatar--voice[data-state="listening"]').count(), 1);
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
  await page.getByRole('button',{name:'Review reply preferences',exact:true}).click();
  await page.getByLabel('Use reviewed reply defaults',{exact:true}).check();
  await page.getByLabel('Reply language',{exact:true}).selectOption('ht');
  await page.getByLabel('Reply detail',{exact:true}).selectOption('short');
  assert.equal(await page.getByRole('button',{name:'Save reviewed reply defaults',exact:true}).isDisabled(),true);
  await page.getByLabel('I reviewed these exact reply defaults and confirm them.',{exact:true}).check();
  await page.getByRole('button',{name:'Save reviewed reply defaults',exact:true}).click();
  await page.getByText('Reviewed reply defaults saved.',{exact:true}).waitFor();
  assert.equal(replyWrites,1);assert.equal(replyProfiles.get('default').language,'ht');
  for(const width of [360,390,768,1440]) {
    await page.setViewportSize({width,height:1000});
    assert.equal(await page.evaluate(()=>document.documentElement.scrollWidth <= window.innerWidth),true,`reply preferences overflow at ${width}px`);
  }
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
  await page.getByRole('button',{name:'Remember this',exact:true}).click();
  await page.getByLabel('Memory subject',{exact:true}).fill('project.shy.database');
  await page.getByLabel('Memory category',{exact:true}).selectOption('PROJECT');
  await page.getByLabel('Memory content',{exact:true}).fill('SHY uses PostgreSQL 17.');
  await page.getByRole('button',{name:'Check existing memory subject',exact:true}).click();
  await page.getByText('This subject has a different saved value or category. Review it before making a correction.',{exact:true}).waitFor();
  assert.equal(memoryWrites,1,'preview cannot write');
  await page.getByRole('button',{name:'Review correction of existing value',exact:true}).click();
  assert.equal(await page.getByLabel('Memory content',{exact:true}).inputValue(),'SHY uses PostgreSQL 17.');
  assert.equal(await page.getByRole('button',{name:'Save reviewed memory',exact:true}).isDisabled(),true);
  await page.getByRole('button',{name:'Cancel memory change',exact:true}).click();
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
  await page.getByRole('button', { name: 'Settings', exact: true }).click();
  await page.getByLabel('New project ID', { exact: true }).fill('gud-express');
  await page.getByRole('button', { name: 'Start project chat', exact: true }).click();
  await page.getByRole('button', { name: 'Review automatic memory saving', exact: true }).click();
  await page.getByLabel('Allow automatic memory saving', { exact: true }).waitFor();
  assert.equal(new URL(lastMemoryUrl).searchParams.get('project_id'), 'gud-express');
  await page.getByRole('button', { name: 'Close settings', exact: true }).click();
  await page.getByLabel('Message SHY', { exact: true }).fill('Project fixture message');
  await page.getByRole('button', { name: 'Send', exact: true }).click();
  await page.getByText('This is a fixture reply.', { exact: true }).waitFor();
  assert.equal(lastChatBody.project_id, 'gud-express');
  await page.waitForFunction(() => {
    const store = JSON.parse(localStorage.getItem('shy.web.chat-store.v1'));
    return store.conversations.find(item => item.id === store.activeConversationId).projectId === 'gud-express';
  });
  await page.reload();
  await page.getByRole('main').getByText('Project fixture message', { exact: true }).waitFor();
  const storedProject = await page.evaluate(() => {
    const store = JSON.parse(localStorage.getItem('shy.web.chat-store.v1'));
    return store.conversations.find(item => item.id === store.activeConversationId).projectId;
  });
  assert.equal(storedProject, 'gud-express');
  await page.getByRole('button', { name: 'Settings', exact: true }).click();
  await page.getByRole('button',{name:'Review reply preferences',exact:true}).click();
  assert.equal(await page.getByLabel('Reply language',{exact:true}).inputValue(),'auto');
  assert.equal(await page.getByLabel('Use reviewed reply defaults',{exact:true}).isChecked(),false);
  assert.equal(replyWrites,1,'project switch must not write preferences');
  await page.getByRole('button', { name: 'Review local documents', exact: true }).click();
  await page.getByLabel('Selected document file', { exact: true }).setInputFiles({name:'notes.txt',mimeType:'text/plain',buffer:Buffer.from('Project uses PostgreSQL.\nSource line two.')});
  assert.equal(await page.getByRole('button', { name: 'Save reviewed document', exact: true }).isDisabled(), true);
  assert.equal(documentWrites, 0);
  await page.getByLabel('I reviewed this exact document change and confirm it.', { exact: true }).check();
  await page.getByRole('button', { name: 'Save reviewed document', exact: true }).click();
  await page.getByText('Document change saved. The project index now reflects it.', { exact: true }).waitFor();
  await page.getByLabel('Select notes.txt', { exact: true }).check();
  await page.getByLabel('Document search keywords', { exact: true }).fill('PostgreSQL');
  await page.getByRole('button', { name: 'Search selected documents', exact: true }).click();
  await page.getByText('notes.txt · lines 1–2 · chunk 1', { exact: true }).waitFor();
  await page.getByRole('button',{name:'Show selected excerpts in chat',exact:true}).click();
  await page.getByText('Selected excerpt fixture: [untrusted](https://evil.example) PostgreSQL.',{exact:true}).waitFor();
  assert.equal(lastChatBody.project_id,'gud-express');
  assert.equal(lastChatBody.document_question.query,'PostgreSQL');
  assert.equal(lastChatBody.document_question.limit,5);
  assert.equal(await page.getByRole('link',{name:'untrusted',exact:true}).count(),0);
  for (const width of [360,390,768,1440]) {
    await page.setViewportSize({width,height:1000});
    assert.equal(await page.evaluate(() => document.documentElement.scrollWidth <= window.innerWidth),true,`document chat overflow at ${width}px`);
  }
  await page.reload();
  await page.getByText('Selected excerpt fixture: [untrusted](https://evil.example) PostgreSQL.',{exact:true}).waitFor();
  assert.equal(await page.getByRole('link',{name:'untrusted',exact:true}).count(),0);
  await page.getByRole('button',{name:'Settings',exact:true}).click();
  await page.getByRole('button',{name:'Review local documents',exact:true}).click();
  await page.getByLabel('Select notes.txt',{exact:true}).check();
  await page.getByLabel('Document search keywords',{exact:true}).fill('PostgreSQL');
  assert.equal(await page.getByRole('button',{name:'Answer from selected excerpts locally',exact:true}).isDisabled(),true);
  await page.getByLabel('Use my configured local model to answer from selected excerpts.',{exact:true}).check();
  await page.getByRole('button',{name:'Answer from selected excerpts locally',exact:true}).click();
  await page.getByText('Local document answer fixture: PostgreSQL [1].',{exact:true}).waitFor();
  assert.equal(lastChatBody.project_id,'gud-express');
  await page.getByText('A local model generated this reply from selected keyword excerpts. Numeric reference membership was checked; factual support and completeness were not independently verified.',{exact:true}).waitFor();
  await page.reload();
  await page.getByText('Local document answer fixture: PostgreSQL [1].',{exact:true}).waitFor();
  assert.equal(await page.getByRole('link',{name:'untrusted',exact:true}).count(),0);
  showComparisonFixture = true;
  await page.getByRole('button',{name:'Settings',exact:true}).click();
  await page.getByRole('button',{name:'Review local documents',exact:true}).click();
  await page.getByLabel('Select notes.txt',{exact:true}).check();
  await page.getByLabel('Select reordered.txt',{exact:true}).check();
  await page.getByRole('button',{name:'Compare two selected documents',exact:true}).click();
  const orderedPreview=page.getByText(/Ordered line comparison: 0 inserted, 1 deleted, 1 equal lines/);
  await orderedPreview.waitFor();
  assert.equal(await orderedPreview.evaluate(element=>element.textContent.includes('revision '+'e'.repeat(64))),true);
  assert.equal(documentWrites,1,'comparison must not mutate documents');
  for (const width of [360,390,768,1440]) {
    await page.setViewportSize({width,height:1000});
    assert.equal(await page.evaluate(()=>document.documentElement.scrollWidth <= window.innerWidth),true,`ordered comparison overflow at ${width}px`);
  }
  showComparisonFixture = false;
  await page.getByRole('button', { name: 'Review refresh notes.txt', exact: true }).click();
  await page.getByLabel('Selected document file', { exact: true }).setInputFiles({name:'notes.txt',mimeType:'text/plain',buffer:Buffer.from('Revised project source.')});
  assert.equal(await page.getByRole('button', { name: 'Save reviewed document', exact: true }).isDisabled(), true);
  await page.getByLabel('I reviewed this exact document change and confirm it.', { exact: true }).check();
  await page.getByRole('button', { name: 'Save reviewed document', exact: true }).click();
  await page.getByText('Document change saved. The project index now reflects it.', { exact: true }).waitFor();
  assert.equal(documentWrites, 2);
  await page.getByRole('button', { name: 'Review delete notes.txt', exact: true }).click();
  assert.equal(await page.getByRole('button', { name: 'Confirm document deletion', exact: true }).isDisabled(), true);
  await page.getByLabel('I reviewed this exact document change and confirm it.', { exact: true }).check();
  await page.getByRole('button', { name: 'Confirm document deletion', exact: true }).click();
  await page.getByText('Document change saved. The project index now reflects it.', { exact: true }).waitFor();
  assert.equal(documentWrites, 3);
  for (const width of [360,390,768,1440]) {
    await page.setViewportSize({width,height:1000});
    assert.equal(await page.evaluate(() => document.documentElement.scrollWidth <= window.innerWidth), true, `document overflow at ${width}px`);
  }
  await page.getByLabel('Selected document file', { exact: true }).setInputFiles({name:'source.pdf',mimeType:'application/pdf',buffer:Buffer.from('%PDF-fixture')});
  assert.equal(await page.getByRole('button', { name: 'Extract selected document text', exact: true }).isDisabled(), true);
  assert.equal(extractionRequests, 0);
  await page.getByLabel('Allow local text extraction of this selected file.', { exact: true }).check();
  await page.getByRole('button', { name: 'Extract selected document text', exact: true }).click();
  await page.getByText('Extracted text is ready for review. The original binary was not stored. Review and confirm separately before saving the text.', { exact: true }).waitFor();
  assert.equal(extractionRequests, 1);
  assert.equal(documentWrites, 3);
  assert.equal(await page.getByRole('button', { name: 'Save reviewed document', exact: true }).isDisabled(), true);
  await page.getByRole('button', { name: 'Close settings', exact: true }).click();
  await page.getByText('Voice settings and privacy', { exact: true }).click();
  const startWake = page.getByRole('button', { name: 'Start wake voice session', exact: true });
  assert.equal(await startWake.isDisabled(), true);
  const beforeWake = submitted;
  await page.getByLabel('Allow a bounded wake voice session.', { exact: true }).check();
  await startWake.click();
  await page.evaluate(() => window.voiceFixture.recognition.onresult({results:[{isFinal:true,0:{transcript:'Hey SHY browser wake draft'}}]}));
  await page.waitForFunction(() => document.querySelector('#shy-composer-input').value === 'browser wake draft');
  assert.equal(submitted, beforeWake, 'default wake mode must not send');
  await page.getByLabel('Message SHY', { exact: true }).fill('');
  await page.getByLabel('Allow a bounded wake voice session.', { exact: true }).check();
  await page.getByLabel('Send wake-recognized messages automatically for this session.', { exact: true }).check();
  assert.equal(await startWake.isDisabled(), true, 'changing automatic sending invalidates prior consent');
  await page.getByLabel('Allow a bounded wake voice session.', { exact: true }).check();
  await startWake.click();
  await page.evaluate(() => window.voiceFixture.recognition.onresult({results:[{isFinal:true,0:{transcript:'Hey SHY automatic browser question'}}]}));
  await page.getByRole('main').getByText('automatic browser question', { exact: true }).waitFor();
  await page.waitForFunction(() => window.voiceFixture.spoken.length > 0);
  assert.equal(submitted, beforeWake + 1);
  assert.equal(lastChatBody.message, 'automatic browser question');
  assert.equal(lastChatBody.project_id, 'gud-express');
  assert.equal(lastChatBody.approval_token, undefined);
  await page.getByRole('button', { name: 'Stop voice', exact: true }).click();
  assert.equal(await startWake.isDisabled(), true);
  assert.equal(await page.getByLabel('Read new replies aloud', { exact: true }).isChecked(), false);
  await page.reload();
  assert.equal(await page.getByLabel('Allow a bounded wake voice session.', { exact: true }).isChecked(), false);
  assert.equal(await page.getByLabel('Send wake-recognized messages automatically for this session.', { exact: true }).isChecked(), false);
  await page.getByText('Research public sources', {exact:true}).click();
  await page.getByLabel('Public research question',{exact:true}).fill('Istwa Ayiti jodi a');
  await page.getByLabel('Research source date window',{exact:true}).selectOption('any_date');
  await page.getByRole('button',{name:'Search public web',exact:true}).click();
  await page.getByText('Explicit historical research fixture needs source text.',{exact:true}).waitFor();
  assert.deepEqual(lastChatBody.research_request,{freshness:'any_date'});
  assert.equal(lastChatBody.message,'Istwa Ayiti jodi a');
  assert.equal(lastChatBody.project_id,'gud-express');
  const explicitContext=page.getByRole('region',{name:'Research answer context'}).last();
  await explicitContext.getByText('Checks and limits',{exact:true}).click();
  assert.equal(await explicitContext.getByText('You selected any source date; older or undated excerpts may be used.',{exact:true}).isVisible(),true);
  for (const width of [360,390,768,1440]) {
    await page.setViewportSize({width,height:1000});
    assert.equal(await page.evaluate(() => document.documentElement.scrollWidth <= window.innerWidth),true,`explicit research overflow at ${width}px`);
  }
  await page.reload();
  await page.getByText('Explicit historical research fixture needs source text.',{exact:true}).waitFor();
  await page.getByRole('region',{name:'Research answer context'}).last().getByText('Checks and limits',{exact:true}).click();
  assert.equal(await page.getByText('You selected any source date; older or undated excerpts may be used.',{exact:true}).isVisible(),true);
  await page.getByLabel('Message SHY', { exact: true }).fill('Research context fixture');
  await page.getByRole('button', { name: 'Send', exact: true }).click();
  await page.getByText('Research context source', { exact: true }).waitFor();
  await page.getByText('SHY generated this clarification without a model.', { exact: true }).last().waitFor();
  await page.getByRole('region',{name:'Research answer context'}).last().getByText('Checks and limits', { exact: true }).click();
  assert.equal(await page.getByRole('region',{name:'Research answer context'}).last().getByText('1 source record checked. This is not a count of independent authorities.', { exact: true }).isVisible(),true);
  assert.equal(await page.getByText('Recent sources must be within 7 UTC calendar days. This window comes from English recency phrases.', { exact: true }).isVisible(),true);
  assert.equal(lastChatBody.project_id,'gud-express');
  for (const width of [360,390,768,1440]) {
    await page.setViewportSize({width,height:1000});
    assert.equal(await page.evaluate(() => document.documentElement.scrollWidth <= window.innerWidth),true,`research context overflow at ${width}px`);
  }
  await page.reload();
  await page.getByText('Research context source', { exact: true }).waitFor();
  assert.equal(await page.getByText('SHY generated this clarification without a model.', { exact: true }).last().isVisible(),true);
  assert.equal(await page.getByRole('region',{name:'Research answer context'}).last().getByText('Checks and limits', { exact: true }).evaluate(element => element.closest('details').open),false);
  await page.getByText('Compare options', {exact:true}).click();
  await page.getByLabel('Criterion 1 name', {exact:true}).fill('Cost');
  await page.getByLabel('Criterion 1 unit', {exact:true}).fill('USD');
  await page.getByLabel('Option 1 name', {exact:true}).fill('A');
  await page.getByLabel('Option 2 name', {exact:true}).fill('B');
  await page.getByLabel('Option 1 criterion 1 value', {exact:true}).fill('100');
  await page.getByLabel('Option 2 criterion 1 value', {exact:true}).fill('200');
  for (const width of [360,390,768,1440]) {
    await page.setViewportSize({width,height:1000});
    assert.equal(await page.evaluate(() => document.documentElement.scrollWidth <= window.innerWidth),true,`comparison overflow at ${width}px`);
  }
  await page.getByRole('button',{name:'Calculate comparison',exact:true}).click();
  await page.getByText('Comparison fixture: A scores 100.000000; B scores 0.000000.',{exact:true}).waitFor();
  assert.equal(lastChatBody.project_id,'gud-express');
  assert.equal(lastChatBody.option_comparison.criteria[0].direction,'minimize');
  assert.equal(lastChatBody.option_comparison.criteria[0].unit,'USD');
  assert.equal(lastChatBody.option_comparison.options[1].values.c1,'200');
  await page.reload();
  await page.getByText('Comparison fixture: A scores 100.000000; B scores 0.000000.',{exact:true}).waitFor();
  console.log('PASS: voice transcript review, spoken reply, stop, title persistence, history search, summaries, reviewed memory correction/deletion, confirmed automatic-saving pause, persisted project chat scope, confirmed document upload/search/refresh/deletion, separately confirmed binary extraction, mobile overflow, session-only consent, reviewed wake drafting and separately consented hands-free sending, ordinary research source cards, bounded answer context, numeric comparison requests and reload persistence, read-only memory preview and separately reviewed corrections, selected document chat with literal source rendering and reload persistence, ordered document comparisons with revision provenance, reviewed reply defaults and project isolation (fixtures).');
})().catch(error => { console.error(error); process.exitCode = 1; }).finally(async () => {
  await browser?.close();
  server?.kill();
});

