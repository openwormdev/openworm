import {cp, mkdir, readFile, rm} from 'node:fs/promises';
import {createHash} from 'node:crypto';
import {validateLiveSnapshot,validateReport} from '../web/report.js';

const files = ['index.html','styles.css','app.js','report.js','live.js','live.css'];
const manifest = JSON.parse(await readFile('web/data/manifest.json','utf8'));
for (const scenario of ['trend','reversal','liquidity-shock']) {
  const path=`data/${scenario}.json`;
  const raw=await readFile(`web/${path}`,'utf8');
  validateReport(JSON.parse(raw));
  if (createHash('sha256').update(raw).digest('hex') !== manifest[scenario]) throw new Error(`Invalid bundled recording: ${scenario}`);
  files.push(path);
}
files.push('data/manifest.json');
if(manifest['live-observer']){
  const path='data/live-observer.json';
  const raw=await readFile(`web/${path}`,'utf8');
  validateLiveSnapshot(JSON.parse(raw));
  if(createHash('sha256').update(raw).digest('hex')!==manifest['live-observer'])throw new Error('Invalid bundled live observer recording');
  files.push(path);
}
await rm('dist',{recursive:true,force:true});
await mkdir('dist/data',{recursive:true});
for (const path of files) await cp(`web/${path}`,`dist/${path}`);
console.log(`Built ${files.length} public assets. No server code, credentials, logs, or user data copied.`);
