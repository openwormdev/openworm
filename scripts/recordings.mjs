import {readFile, writeFile} from 'node:fs/promises';
import {createHash} from 'node:crypto';
import {validateReport} from '../web/report.js';
const manifest={};
for(const name of ['trend','reversal','liquidity-shock']) {
  const raw=await readFile(`web/data/${name}.json`,'utf8');
  const report=validateReport(JSON.parse(raw));
  if(report.market_source!=='synthetic'||report.scenario!==name)throw new Error('Only named synthetic-market recordings may be bundled.');
  manifest[name]=createHash('sha256').update(raw).digest('hex');
}
await writeFile('web/data/manifest.json',JSON.stringify(manifest,null,2)+'\n');
console.log('Reference recording integrity manifest refreshed.');
