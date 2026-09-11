import {execFileSync} from 'node:child_process';
import {lstat,readFile} from 'node:fs/promises';
import path from 'node:path';

const rawTests=[
  ['private key',/-----BEGIN (?:RSA |EC |OPENSSH )?PRIVATE KEY-----/],
  ['GitHub access token',/\bgh[pousr]_[A-Za-z0-9]{30,}\b/],
  ['GitHub fine-grained token',/\bgithub_pat_[A-Za-z0-9_]{30,}\b/],
  ['AWS access key',/\bAKIA[A-Z0-9]{16}\b/],
  ['machine-specific user path',/(?:\/(?:Users|home)\/|\/workspace\/scratch\/|\/mnt\/[a-z]\/Users\/)[^\s\\/"'<>:|?*]+|(?:[A-Za-z]:|\\\\[^\\/\s]+\\[A-Za-z]\$)[\\/]+(?:Users|Documents and Settings)[\\/]+[^\s\\/"'<>:|?*]+/iu],
  ['email address',/[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Za-z]{2,}/],
  ['IANA timezone or location',/\b(?:Africa|America|Antarctica|Arctic|Asia|Atlantic|Australia|Europe|Indian|Pacific)\/[A-Za-z_+-]+(?:\/[A-Za-z_+-]+)?\b/],
  ['wall-clock timestamp',/\b20[0-9]{2}-[01][0-9]-[0-3][0-9]T[0-2][0-9]:[0-5][0-9](?::[0-6][0-9](?:\.[0-9]+)?)?(?:Z|[+-][0-2][0-9]:?[0-5][0-9])\b/],
  ['analytics identifier',/\b(?:UA-[0-9]+-[0-9]+|G-[A-Z0-9]{8,}|GTM-[A-Z0-9]{6,})\b/],
];
const timestampKeys=new Set([
  'timestamp','observedat','latesttradeat','sessionstartedat','readyat',
  'updatedat','stoppedat','createdat','finishedat',
]);
const privateMetadataKeys=new Set([
  'hostname','computername','deviceid','devicename','username',
]);
const normalizeKey=(key)=>key.normalize('NFKC').toLowerCase().replace(/[_\-\s]/g,'');

function isWallClock(value){
  if(typeof value==='string'&&rawTests[7][1].test(value))return true;
  if(typeof value!=='number'&&typeof value!=='string')return false;
  if(typeof value==='string'&&!/^[+-]?(?:\d+(?:\.\d*)?|\.\d+)(?:e[+-]?\d+)?$/i.test(value.trim()))return false;
  const number=Number(value);
  if(!Number.isFinite(number))return false;
  const magnitude=Math.abs(number);
  return (magnitude>=1e9&&magnitude<1e10)
    ||(magnitude>=1e12&&magnitude<1e13)
    ||(magnitude>=1e15&&magnitude<1e16)
    ||(magnitude>=1e18&&magnitude<1e19);
}

function findJsonViolation(value,trail='$'){
  if(typeof value==='string'){
    for(const [label,test] of rawTests)if(test.test(value))return {label,trail};
    return null;
  }
  if(Array.isArray(value)){
    for(let index=0;index<value.length;index+=1){
      const violation=findJsonViolation(value[index],`${trail}[${index}]`);
      if(violation)return violation;
    }
    return null;
  }
  if(value===null||typeof value!=='object')return null;
  for(const [key,child] of Object.entries(value)){
    const normalized=normalizeKey(key);
    const childTrail=`${trail}.${key}`;
    if(timestampKeys.has(normalized)&&isWallClock(child))return {label:'wall-clock timestamp',trail:childTrail};
    if(privateMetadataKeys.has(normalized))return {label:'device or account metadata',trail:childTrail};
    const violation=findJsonViolation(child,childTrail);
    if(violation)return violation;
  }
  return null;
}

function git(args,encoding='utf8'){
  try{
    return execFileSync('git',args,{encoding,maxBuffer:100*1024*1024});
  }catch(error){
    throw new Error(`Unable to inspect the Git publication tree: ${error.message}`);
  }
}

function stagedFiles(){
  const records=git(['ls-files','--stage','-z']).split('\0').filter(Boolean);
  return records.map((record)=>{
    const match=/^(\d{6}) ([0-9a-f]+) ([0-3])\t([\s\S]+)$/.exec(record);
    if(!match)throw new Error('Unable to parse the Git index.');
    const [,mode,objectId,stage,name]=match;
    if(stage!=='0')throw new Error(`Unresolved Git index entry must be reviewed: ${name}`);
    return {mode,name,read:async()=>git(['cat-file','blob',objectId],null)};
  });
}

async function untrackedFiles(){
  const names=git(['ls-files','--others','--exclude-standard','-z']).split('\0').filter(Boolean);
  const files=[];
  for(const name of names){
    const stats=await lstat(name);
    if(stats.isSymbolicLink())throw new Error(`Symlink must be reviewed before publishing: ${name}`);
    if(!stats.isFile())continue;
    files.push({mode:'100644',name,read:async()=>readFile(name)});
  }
  return files;
}

function checkSelfTests(){
  const rawProbes=[
    [4,['C:','Users','person','file.txt'].join('\\')],
    [4,['','mnt','c','Users','person','file.txt'].join('/')],
    [4,[String.raw`\\HOST\C$`,'Users','\u7528\u6237','file.txt'].join('\\')],
    [6,['America','New_York'].join('/')],
    [7,['2030-01-02','T03:04:05Z'].join('')],
  ];
  for(const [index,value] of rawProbes){
    if(!rawTests[index][1].test(value))throw new Error(`Privacy rule self-test failed: ${rawTests[index][0]}`);
  }
  const sensitiveJson=[
    JSON.parse('{"observed_at":'+['1.789','100385e9'].join('')+'}'),
    JSON.parse('{"observed\\u005fat":'+['17','89100385'].join('')+'}'),
    JSON.parse('{"updated_at":"'+['2030-01-02','T03:04:05Z'].join('')+'"}'),
    JSON.parse('{"user\\u004eame":"local-account"}'),
  ];
  for(const [index,value] of sensitiveJson.entries())if(!findJsonViolation(value))throw new Error(`JSON privacy rule self-test ${index+1} failed.`);
  if(findJsonViolation({timestamp:1000,time_ms:1100}))throw new Error('JSON privacy rule false-positive self-test failed.');
}

function isSensitiveFilename(name){
  const base=path.posix.basename(name.replaceAll('\\','/'));
  return (base.startsWith('.env')&&base!=='.env.example')
    ||/(?:\.key$|keypair.*\.json$|\.sqlite(?:3)?$)/i.test(base);
}

async function scan(file){
  if(file.mode==='120000')throw new Error(`Symlink must be reviewed before publishing: ${file.name}`);
  if(file.mode==='160000')throw new Error(`Git submodule must be reviewed before publishing: ${file.name}`);
  if(isSensitiveFilename(file.name))throw new Error(`Sensitive runtime file found: ${file.name}`);
  const bytes=await file.read();
  const text=Buffer.from(bytes).toString('utf8');
  for(const [label,test] of rawTests)if(test.test(text))throw new Error(`Potential ${label}: ${file.name}`);
  if(path.posix.extname(file.name.replaceAll('\\','/')).toLowerCase()==='.json'){
    let parsed;
    try{parsed=JSON.parse(text);}catch(error){throw new Error(`Invalid JSON publication input ${file.name}: ${error.message}`);}
    const violation=findJsonViolation(parsed);
    if(violation)throw new Error(`Potential ${violation.label}: ${file.name} at ${violation.trail}`);
  }
}

checkSelfTests();
const files=[...stagedFiles(),...await untrackedFiles()];
for(const file of files)await scan(file);
console.log(`Source privacy scan passed for ${files.length} staged or publishable files: no detected credentials, contact data, user paths, location clues, device metadata, analytics IDs, or wall-clock timestamps. Manual review is still required.`);
