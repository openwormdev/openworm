import {readFile,readdir} from 'node:fs/promises';
import path from 'node:path';
const excluded=new Set(['.git','.venv','__pycache__','node_modules','dist','runs','.sites-runtime','.vercel']);
const tests=[
  /-----BEGIN (?:RSA |EC |OPENSSH )?PRIVATE KEY-----/,
  /\bgh[pousr]_[A-Za-z0-9]{30,}\b/,
  /\bgithub_pat_[A-Za-z0-9_]{30,}\b/,
  /\bAKIA[A-Z0-9]{16}\b/,
  /(?:\/Users\/|\/home\/|\/workspace\/scratch\/)[A-Za-z0-9_-]+/,
  /[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Za-z]{2,}/,
];
async function walk(dir='.') {
  for (const item of await readdir(dir,{withFileTypes:true})) {
    if(excluded.has(item.name)||item.name.endsWith('.egg-info'))continue;
    const name=path.join(dir,item.name);
    if(item.isSymbolicLink())throw new Error(`Symlink must be reviewed before publishing: ${name}`);
    if(item.isDirectory()){await walk(name);continue;}
    if(item.name.startsWith('.env')&&item.name!=='.env.example')throw new Error('Environment secret file found.');
    if(/(?:\.key$|keypair.*\.json$|\.sqlite)/i.test(item.name))throw new Error('Sensitive runtime file found.');
    if(name==='scripts/privacy-check.mjs')continue;
    const text=await readFile(name,'utf8');
    for(const test of tests)if(test.test(text))throw new Error(`Potential identifying data or secret: ${name}`);
  }
}
await walk();
console.log('Source privacy scan passed: no email addresses, private keys, access tokens, or machine-specific paths detected. Manual review is still required.');
