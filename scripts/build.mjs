import {cp, mkdir, readFile, rm} from 'node:fs/promises';
import {createHash} from 'node:crypto';
import {validateReport} from '../web/report.js';

const files = ['index.html','styles.css','app.js','report.js'];
const manifest = JSON.parse(await readFile('web/data/manifest.json','utf8'));
for (const scenario of ['trend','reversal','liquidity-shock']) {
  const path=`data/${scenario}.json`;
  const raw=await readFile(`web/${path}`,'utf8');
  validateReport(JSON.parse(raw));
  if (createHash('sha256').update(raw).digest('hex') !== manifest[scenario]) throw new Error(`Invalid bundled recording: ${scenario}`);
  files.push(path);
}
files.push('data/manifest.json');
await rm('dist',{recursive:true,force:true});
await mkdir('dist/data',{recursive:true});
for (const path of files) await cp(`web/${path}`,`dist/${path}`);
console.log(`Built ${files.length} public assets. No server code, credentials, logs, or user data copied.`);
