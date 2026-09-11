import {FORWARD, REVERSE, SENSORY, validateReport, meanTrace, workerBase, sha256} from './report.js';
const $ = id => document.getElementById(id);
const money = x => new Intl.NumberFormat('en-US',{style:'currency',currency:'USD',maximumFractionDigits:2}).format(x);
const time = x => `${Math.floor(x / 60).toString().padStart(2,'0')}:${(x % 60).toString().padStart(2,'0')}`;
let report, index = 0, timer, epoch = 0, originLabel = 'Bundled reference recording';
const svgNS = 'http://www.w3.org/2000/svg';
function node(tag, attrs = {}, text = '') { const n = document.createElementNS(svgNS,tag); for(const [k,v] of Object.entries(attrs)) n.setAttribute(k,String(v)); n.textContent=text; return n; }
function element(tag, text, cls='') { const n=document.createElement(tag); n.textContent=text; n.className=cls; return n; }
function notice(message,error=false) { $('notice').textContent=message; $('notice').classList.toggle('error',error); }
function pause() { clearInterval(timer); timer=undefined; $('play').textContent='▶ Play recording'; }
function chart(target, series, colors, selected, labels) {
  const svg=$(target), width=Number(svg.viewBox.baseVal.width),height=Number(svg.viewBox.baseVal.height);
  const left=13,right=58,top=15,bottom=32,w=width-left-right,h=height-top-bottom;
  const all=series.flat(), min=Math.min(...all),max=Math.max(...all),pad=Math.max((max-min)*.15,.001),low=min-pad,high=max+pad;
  const x=i=>left+i/(series[0].length-1)*w,y=v=>top+(high-v)/(high-low)*h;
  svg.replaceChildren();
  for(let i=0;i<=3;i++){const v=low+(high-low)*i/3;svg.append(node('line',{x1:left,y1:y(v),x2:left+w,y2:y(v),stroke:'#29363a','stroke-dasharray':'3 5'}));svg.append(node('text',{x:left+w+9,y:y(v)+4,class:'chart-label'},labels==='mv'?`${v.toFixed(1)}`:`$${v.toFixed(2)}`));}
  series.forEach((values,j)=>{const points=values.map((v,i)=>`${x(i)},${y(v)}`).join(' ');svg.append(node('polyline',{points,fill:'none',stroke:colors[j],'stroke-width':2,'stroke-linecap':'round','stroke-linejoin':'round'}));});
  const at=Math.max(0,Math.min(series[0].length-1,selected));
  svg.append(node('line',{x1:x(at),y1:top,x2:x(at),y2:top+h,stroke:'#839e94','stroke-dasharray':'3 3'}));
  series.forEach((values,j)=>svg.append(node('circle',{cx:x(at),cy:y(values[at]),r:4,fill:colors[j],stroke:'#141c20','stroke-width':2})));
  svg.append(node('text',{x:left,y:height-6,class:'chart-label'},labels==='mv'?'0 ms':'00:00'));
  svg.append(node('text',{x:left+w,y:height-6,'text-anchor':'end',class:'chart-label'},labels==='mv'?`${report.traces.time_ms.at(-1).toFixed(0)} ms`:time(report.rows.at(-1).tick.seconds)));
}
function render() {
  if(!report) return;
  const r=report.rows[index],t=r.tick;
  $('token-label').textContent=report.market_source==='synthetic'?'SYNTH / USD':'REPLAY / USD';
  $('market-kind').textContent=report.market_source==='synthetic'?'Synthetic token · 15-second observations':'Unverified input · 15-second observations';
  $('source-label').textContent=originLabel;
  $('neuron-count').textContent=report.model.neurons;
  $('hero-neurons').textContent=`${Number(report.model.neurons).toLocaleString()} MODEL NEURONS`;
  $('margin').textContent=(r.scores.margin>=0?'+':'')+r.scores.margin.toFixed(3);
  $('direction').textContent=r.scores.margin>0?'Forward-dominant output':r.scores.margin<0?'Reverse-dominant output':'No directional separation';
  $('equity').textContent=money(r.equity);$('pnl').textContent=`${money(r.equity-report.policy.initial_cash)} marked P&L · unrealized included`;
  $('intent').textContent=r.intent;$('intent').className=r.intent==='ENTER'?'pass':r.intent==='EXIT'?'warn':'';
  $('position').textContent=`${r.position} · ${r.units.toFixed(4)} paper units`;
  $('price').textContent=money(t.price);$('time').textContent=`T + ${time(t.seconds)}`;$('duration').textContent=time(report.rows.at(-1).tick.seconds);
  $('scrubber').value=index;$('scrubber').max=report.rows.length-1;
  $('liquidity').textContent=money(t.liquidity);$('flow').textContent=`${(t.flow*100).toFixed(0)}%`;$('impact').textContent=`${t.price_impact_bps} bps`;
  $('forward-score').textContent=r.scores.forward.toFixed(3);$('reverse-score').textContent=r.scores.reverse.toFixed(3);$('forward-bar').value=r.scores.forward;$('reverse-bar').value=r.scores.reverse;
  chart('price-chart',[report.rows.map(x=>x.tick.price)],['#3dff88'],index,'price');
  const neuralAt=report.traces.time_ms.findIndex(x=>x>=report.config.warmup_ms+(index+1)*report.config.episode_ms-report.config.readout_ms/2);
  chart('neural-chart',[meanTrace(report,FORWARD),meanTrace(report,REVERSE)],['#3dff88','#ff8e68'],neuralAt<0?report.traces.time_ms.length-1:neuralAt,'mv');
  $('sensory').replaceChildren(...SENSORY.map(name=>{const item=element('div','','sensory-row');item.append(element('span',name),element('span',`${r.stimulus_pa[name].toFixed(2)} pA`));const bar=document.createElement('progress');bar.max=5;bar.value=r.stimulus_pa[name];bar.setAttribute('aria-label',`${name} input current`);item.append(bar);return item;}));
  $('risk-badge').textContent=r.risk;$('risk-badge').className=`tag ${r.risk==='ALLOW'?'pass':'warn'}`;
  const rules=[['Data freshness',t.fresh,'FRESH','STALE'],['Eligible token',t.eligible,'PASS','BLOCK'],[`Liquidity ≥ ${money(report.policy.min_liquidity)}`,t.liquidity>=report.policy.min_liquidity,'PASS','BLOCK'],[`Price impact ≤ ${report.policy.max_impact_bps} bps`,t.price_impact_bps<=report.policy.max_impact_bps,'PASS','BLOCK'],['Execution authority',true,'PAPER ONLY','']];
  $('risk-rules').replaceChildren(...rules.map(([label,ok,a,b])=>{const item=element('div','','rule');item.append(element('span',label),element('small',ok?a:b,ok?'pass':'warn'));return item;}));
  $('execution-note').textContent=r.execution==='EXIT_UNFILLED'?'Exit requested but NOT filled: unsafe liquidity or stale data. Exposure remains.':r.reasons.length?`External intervention: ${r.reasons.join(', ')}.`:'No live transaction path exists. Fees and price impact are included in paper fills.';
  $('audit-count').textContent=`${index+1} / ${report.rows.length} EVENTS`;
  $('audit').replaceChildren(...report.rows.slice(0,index+1).reverse().map((x,i)=>{const tr=element('tr','',i===0?'current':'');tr.append(element('td',time(x.tick.seconds)));const intent=element('td','');intent.append(element('span',x.intent,`tag ${x.intent==='ENTER'?'pass':x.intent==='EXIT'?'warn':''}`));tr.append(intent,element('td',x.risk+(x.reasons.length?` · ${x.reasons.join(', ')}`:'')),element('td',x.fill?`${x.fill.side} ${x.fill.units.toFixed(3)} @ ${money(x.fill.price)}`:x.execution==='EXIT_UNFILLED'?'UNFILLED EXIT':'NO ORDER'));const digest=element('td',x.event_hash.slice(0,12));digest.title=x.event_hash;tr.append(digest);return tr;}));
  const m=report.model;
  const facts=[['Engine',`c302 ${m.c302} / C1`],['Backend',m.runtime],['Connectivity reader',m.reader],['Neurons / projections',`${m.neurons} / ${m.projections}`],['Temporal model','Continuous within replay'],['Market source',report.market_source],['Model hash',m.network_sha256],['Audit root',report.audit_root]];
  $('model-details').replaceChildren(...facts.map(([k,v])=>{const line=element('div','');line.append(element('dt',k),element('dd',v));return line;}));
}
function acceptReport(value,label) { report=validateReport(value);originLabel=label;index=0;pause();for(const id of ['play','reset','export','scrubber'])$(id).disabled=false;render(); }
async function loadScenario() {
  pause();const ticket=++epoch;const name=$('scenario').value;
  for(const id of ['play','reset','export','scrubber'])$(id).disabled=true;
  try {
    const manifestResponse=await fetch(new URL('./data/manifest.json',import.meta.url));if(!manifestResponse.ok)throw new Error('Reference recordings are not installed. Run the Python replay command to generate them.');
    const manifest=await manifestResponse.json();
    const response=await fetch(new URL(`./data/${name}.json`,import.meta.url));if(!response.ok)throw new Error('This reference recording is unavailable.');
    const raw=await response.text();if(await sha256(raw)!==manifest[name])throw new Error('Recording integrity check failed.');
    if(ticket!==epoch)return;
    acceptReport(JSON.parse(raw),'Verified bundled recording');
    notice('Synthetic market · real c302 simulation · paper fills. Playback does not run a new simulation. Zero trades are a valid result.');
  } catch(error) { if(ticket===epoch)notice(error.message,true); }
}
$('scenario').addEventListener('change',loadScenario);
$('play').addEventListener('click',()=>{if(timer){pause();return;}if(index===report.rows.length-1)index=0;$('play').textContent='Ⅱ Pause recording';timer=setInterval(()=>{index=Math.min(index+1,report.rows.length-1);render();if(index===report.rows.length-1)pause();},Number($('speed').value));render();});
$('speed').addEventListener('change',pause);$('reset').addEventListener('click',()=>{pause();index=0;render();});
$('scrubber').addEventListener('input',event=>{pause();index=Number(event.target.value);render();});
$('export').addEventListener('click',()=>{if(!report)return;const url=URL.createObjectURL(new Blob([JSON.stringify(report,null,2)],{type:'application/json'}));const a=document.createElement('a');a.href=url;a.download='wormstreet-paper-report.json';a.click();setTimeout(()=>URL.revokeObjectURL(url),1000);});
$('import').addEventListener('change',async event=>{const file=event.target.files[0];if(!file)return;try{if(file.size>2_000_000)throw new Error('Maximum report size is 2 MB.');const value=validateReport(JSON.parse(await file.text()));++epoch;acceptReport(value,'Imported report · origin unverified');notice('Imported locally. Schema checked; simulation origin and authenticity are NOT verified. Nothing was uploaded.');}catch(error){notice(error.message,true);}finally{event.target.value='';}});
let working=false;
$('worker-form').addEventListener('submit',async event=>{
  event.preventDefault();if(working)return;
  const token=$('worker-token').value;
  let base;
  try{base=workerBase($('worker-url').value,location.origin);}catch(error){$('worker-status').textContent=error.message;return;}
  working=true;$('run').disabled=true;$('worker-status').textContent='Running a real reference simulation. This can take several minutes.';
  const ticket=++epoch;pause();
  const headers={'Content-Type':'application/json',...(token?{Authorization:`Bearer ${token}`}:{})};
  try {
    const created=await fetch(`${base}/api/jobs`,{method:'POST',headers,body:JSON.stringify({scenario:$('scenario').value}),signal:AbortSignal.timeout(15000),redirect:'error'});
    if(!created.ok)throw new Error(created.status===429?'The worker is busy; try again when its current run finishes.':created.status===401?'Worker token rejected.':'Worker unavailable. Vercel hosts recordings only; start or connect your Python worker.');
    const job=await created.json();if(!/^[a-f0-9]{32}$/.test(job.id))throw new Error('Invalid worker response.');
    const deadline=Date.now()+300000;
    while(Date.now()<deadline){await new Promise(resolve=>setTimeout(resolve,2000));const response=await fetch(`${base}/api/jobs/${job.id}`,{headers,signal:AbortSignal.timeout(15000),redirect:'error'});if(!response.ok)throw new Error('Unable to retrieve worker result.');const status=await response.json();if(status.status==='failed')throw new Error('Reference simulation failed. Check the worker locally.');if(status.status==='complete'){if(ticket===epoch){acceptReport(status.report,'Fresh c302 worker simulation');notice('New c302 simulation completed. Market input is synthetic and every fill is paper-only.');}$('worker-status').textContent=ticket===epoch?'Reference simulation complete. Audit report loaded.':'Simulation finished; a newer selection is being displayed.';return;}}
    throw new Error('Worker timed out. Check its status before starting another simulation.');
  } catch(error){$('worker-status').textContent=error.name==='TypeError'?'Cannot reach worker. Check its URL, HTTPS, and allowed origin.':error.message;}
  finally{working=false;$('run').disabled=false;}
});
if(document.modelContext?.registerTool){try{Promise.resolve(document.modelContext.registerTool({name:'read_paper_replay',description:'Read the currently visible paper-only replay observation; does not run a model or trade.',inputSchema:{type:'object',properties:{},additionalProperties:false},annotations:{readOnlyHint:true,untrustedContentHint:true},execute(input){if(input&&Object.keys(input).length)throw new Error('No arguments accepted');return report?{source:originLabel,scenario:report.scenario,tick:index,intent:report.rows[index].intent,risk:report.rows[index].risk,paper_equity:report.rows[index].equity}: {status:'not_loaded'};}})).catch(()=>{});}catch{}}

function startSpecimen() {
  const canvas=$('worm-specimen');
  const context=canvas?.getContext('2d',{alpha:false});
  if(!context)return;
  const count=11000,points=new Float32Array(count*4);
  let seed=0x302c1;
  const random=()=>((seed=Math.imul(seed,1664525)+1013904223>>>0)/4294967296);
  const gaussian=()=>Math.sqrt(-2*Math.log(Math.max(random(),1e-7)))*Math.cos(2*Math.PI*random());
  for(let i=0;i<count;i++){
    const u=random(),x=(u-.5)*2;
    const taper=Math.pow(Math.sin(Math.PI*u),.62);
    const radius=(.012+.105*taper)*(random()<.78?.74+random()*.26:Math.sqrt(random()));
    const angle=random()*Math.PI*2;
    points[i*4]=x;
    points[i*4+1]=Math.cos(angle)*radius+gaussian()*.006;
    points[i*4+2]=Math.sin(angle)*radius;
    points[i*4+3]=random();
  }
  const reduced=matchMedia('(prefers-reduced-motion: reduce)').matches;
  let tick=0,pointer=0,targetPointer=0;
  const fit=()=>{const rect=canvas.getBoundingClientRect(),d=Math.min(devicePixelRatio||1,2);canvas.width=Math.max(2,Math.floor(rect.width*d));canvas.height=Math.max(2,Math.floor(rect.height*d));};
  const aim=event=>{targetPointer=(event.clientX/innerWidth-.5)*.18;};
  addEventListener('resize',fit,{passive:true});
  addEventListener('pointermove',aim,{passive:true});
  function draw(){
    const width=canvas.width,height=canvas.height,d=Math.min(devicePixelRatio||1,2);
    context.fillStyle='#06070a';context.fillRect(0,0,width,height);
    pointer+=(targetPointer-pointer)*.035;
    const scale=Math.min(width*.43,height*.61),centerY=height*(innerWidth<640?.34:.35);
    for(let i=0;i<count;i++){
      const x=points[i*4],ry=points[i*4+1],z=points[i*4+2],spark=points[i*4+3];
      const wave=Math.sin(x*3.05+tick*.48)*.13+Math.sin(x*6.7-tick*.22)*.025;
      const twist=Math.sin(x*2.4+tick*.18)*.26+pointer;
      const ct=Math.cos(twist),st=Math.sin(twist),y=ry*ct-z*st,depth=ry*st+z*ct;
      const px=width/2+x*scale;
      const py=centerY+(wave+y)*scale;
      const near=Math.max(0,Math.min(1,.5+depth*4.1));
      const pulse=!reduced&&spark>.992&&Math.sin(tick*5+spark*90)>.45;
      context.globalAlpha=pulse?.95:.16+near*.64;
      context.fillStyle=pulse?'#dffaff':near>.57?'#abddef':'#52798e';
      const size=(.55+near*1.18+(pulse?1.1:0))*d;
      context.fillRect(px,py,size,size);
    }
    context.globalAlpha=1;
    if(!reduced){tick+=.012;requestAnimationFrame(draw);}
  }
  fit();draw();
}

startSpecimen();
loadScenario();
