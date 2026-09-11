import {test} from 'node:test';
import assert from 'node:assert/strict';
import {readFile} from 'node:fs/promises';
import {createHash} from 'node:crypto';
import {validateReport,workerBase,meanTrace,FORWARD} from '../web/report.js';

test('worker URLs reject token leaks and unsafe protocols',()=>{
  assert.equal(workerBase('https://worker.example','https://page.example'),'https://worker.example');
  assert.equal(workerBase('http://localhost:8000',''),'http://localhost:8000');
  const authenticated=new URL('https://worker.example');authenticated.username='example';authenticated.password='not-a-credential';
  assert.throws(()=>workerBase(authenticated.toString(),''));
  for(const bad of ['http://remote.example','javascript:alert(1)','https://worker.example/?token=x','https://worker.example/path'])assert.throws(()=>workerBase(bad,''));
});
test('report validator rejects arbitrary and malformed JSON objects',()=>{
  for(const bad of [null,{},[],{schema_version:1},{trading_mode:'live'}])assert.throws(()=>validateReport(bad));
});
test('all reference recordings have valid contracts and trusted file hashes',async()=>{
  const manifest=JSON.parse(await readFile('web/data/manifest.json','utf8'));
  for(const name of ['trend','reversal','liquidity-shock']){
    const raw=await readFile(`web/data/${name}.json`,'utf8');const r=validateReport(JSON.parse(raw));
    assert.equal(createHash('sha256').update(raw).digest('hex'),manifest[name]);
    assert.equal(r.market_source,'synthetic');assert.equal(r.scenario,name);
    assert.equal(meanTrace(r,FORWARD).length,r.traces.time_ms.length);
    const broken=structuredClone(r);broken.rows[0].scores.margin=Infinity;assert.throws(()=>validateReport(broken));
    const chain=structuredClone(r);chain.rows[1].previous_hash='broken';assert.throws(()=>validateReport(chain));
    for(const field of ['config','policy']){const incomplete=structuredClone(r);delete incomplete[field];assert.throws(()=>validateReport(incomplete));}
    const invalidRisk=structuredClone(r);invalidRisk.rows[0].tick.fresh='true';assert.throws(()=>validateReport(invalidRisk));
  }
});
test('public page has controls and no third-party scripts or forms',async()=>{
  const html=await readFile('web/index.html','utf8');
  for(const id of ['play','reset','scrubber','export','import','worker-form'])assert.ok(html.includes(`id="${id}"`));
  assert.ok(!/<script[^>]+src="https?:/i.test(html));assert.ok(!/action="https?:/i.test(html));
});
