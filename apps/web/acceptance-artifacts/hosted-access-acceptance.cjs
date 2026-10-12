const assert=require('node:assert/strict');
const http=require('node:http');
const {spawn}=require('node:child_process');
const password='fixture8',token='fixture-token-'+'t'.repeat(40);
const base='http://127.0.0.1:3011';let hits=0;
const backend=http.createServer((req,res)=>{
  hits++;assert.equal(req.headers.authorization,'Bearer '+token);
  res.setHeader('content-type','application/json');
  res.end(JSON.stringify({status:'RESPOND',message:'Owner proxy fixture verified.',configured:false}));
});
let app;
(async()=>{
  await new Promise(resolve=>backend.listen(8018,'127.0.0.1',resolve));
  app=spawn('npm',['run','start','--','--hostname','127.0.0.1','--port','3011'],{env:{...process.env,SHY_REQUIRE_AUTH:'1',SHY_OWNER_USERNAME:'owner',SHY_OWNER_PASSWORD:password,SHY_ACCESS_TOKEN:token,SHY_PUBLIC_ORIGIN:base,SHY_BACKEND_BASE_URL:'http://127.0.0.1:8018'},stdio:'ignore',detached:true});
  let ready=false;
  for(let i=0;i<100;i++){
    try{if((await fetch(base)).status===401){ready=true;break;}}catch{}
    await new Promise(r=>setTimeout(r,100));
  }
  assert.equal(ready,true,'Protected production server should start');
  const authorization='Basic '+Buffer.from('owner:'+password).toString('base64');
  assert.equal((await fetch(base,{headers:{authorization:'Basic '+Buffer.from('owner:incorrect').toString('base64')}})).status,401);
  const page=await fetch(base,{headers:{authorization}});assert.equal(page.status,200);
  const html=await page.text();assert.ok(!html.includes(password)&&!html.includes(token),'Server credentials must not enter client HTML');
  assert.equal(page.headers.get('cache-control'),'private, no-store');
  const before=hits;
  assert.equal((await fetch(base+'/api/shy/agent',{method:'POST',body:'{}'})).status,401);
  assert.equal((await fetch(base+'/api/shy/agent',{method:'POST',headers:{authorization,origin:'https://evil.example'},body:'{}'})).status,403);
  assert.equal(hits,before,'Rejected browser requests must not reach backend');
  for(const path of ['/health','/documents','/memories','/voice']){
    const response=await fetch(base+'/api/shy'+path,{headers:{authorization}});assert.equal(response.status,200,path);
  }
  const reply=await fetch(base+'/api/shy/agent',{method:'POST',headers:{authorization,origin:base,'content-type':'application/json'},body:JSON.stringify({message:'Owner access fixture'})});
  assert.equal(reply.status,200);assert.equal((await reply.json()).message,'Owner proxy fixture verified.');
  console.log('PASS: protected production frontend, server-only bearer proxy headers, rejected unauthenticated/cross-site writes and authorized owner requests (fixtures).');
})().catch(err=>{console.error(err);process.exitCode=1;}).finally(()=>{if(app?.pid){try{process.kill(-app.pid,'SIGTERM');}catch{}}backend.close();});
