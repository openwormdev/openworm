import {FORWARD,REVERSE,SENSORY,meanTrace,workerBase,validateLiveSnapshot,validateTokenMarket} from './report.js';
const $=id=>document.getElementById(id);
let connection=null,pollTimer=null,marketTimer=null,busy=false,lastRoot=null;
let marketOnline=false,marketAttempted=false,observerStatus='idle';
const terminal=new Set(['idle','stopped','failed']);
const observerActive=()=>!terminal.has(observerStatus)&&observerStatus!=='disconnected';
function status(text){$('live-status').textContent=text;}
function paintState(){
  $('live-state').textContent=observerActive()?observerStatus.toUpperCase().replaceAll('-',' '):marketOnline?'TOKEN LIVE':marketAttempted?'FEED RETRYING':'CONNECTING';
}
async function request(path,method='GET'){
  const response=await fetch(connection.base+path,{method,headers:connection.token?{Authorization:`Bearer ${connection.token}`}:{},redirect:'error',signal:AbortSignal.timeout(15000)});
  if(!response.ok)throw new Error(response.status===401?'Worker token rejected.':response.status===429?'Worker is already in use.':'Cannot reach the neural worker. Check its URL and access token below.');
  return response.json();
}
function trace(frame){
  const svg=$('live-chart'),series=[meanTrace(frame,FORWARD),meanTrace(frame,REVERSE)];
  const values=series.flat(),low=Math.min(...values)-.01,high=Math.max(...values)+.01;
  const ns='http://www.w3.org/2000/svg';svg.replaceChildren();
  series.forEach((v,j)=>{const line=document.createElementNS(ns,'polyline');line.setAttribute('points',v.map((y,i)=>`${10+i/(v.length-1)*530},${10+(high-y)/(high-low)*145}`).join(' '));line.setAttribute('fill','none');line.setAttribute('stroke',j?'#f6b396':'#a5f4cb');line.setAttribute('stroke-width','2');svg.append(line);});
  const label=document.createElementNS(ns,'text');label.setAttribute('x','10');label.setAttribute('y','176');label.setAttribute('class','chart-label');label.textContent=`${low.toFixed(2)} to ${high.toFixed(2)} mV · latest neural episode`;svg.append(label);
}
function renderMarket(value){
  const r=validateTokenMarket(value),m=r.recent;
  marketOnline=true;marketAttempted=true;paintState();
  $('live-count').textContent=m.events.toLocaleString();
  $('live-sides').textContent=`${m.buy_events} / ${m.sell_events}`;
  $('live-price').textContent=m.price_quote===null?'Unavailable':m.price_quote.toPrecision(5);
  const age=m.latest_trade_at===null?null:Math.max(0,Math.floor(Date.now()/1000-m.latest_trade_at));
  $('live-coverage').textContent=`Pons indexer · recent indexed window · latest indexed trade ${age===null?'unavailable':age+'s ago'}. Amounts are in GOOGL; receipts, liquidity and executable price impact are unverified.`;
  if(!observerActive())status('Live WORMBRAIN token data connected. The optional Python worker below runs the c302 neural observer.');
}
async function pollMarket(){
  try{
    const response=await fetch('/api/token',{headers:{Accept:'application/json'},redirect:'error',signal:AbortSignal.timeout(15000)});
    if(!response.ok)throw new Error('Token feed unavailable');
    renderMarket(await response.json());
  }catch{
    marketOnline=false;marketAttempted=true;paintState();
    if(!observerActive())status('The WORMBRAIN token feed is temporarily unavailable. Retrying automatically.');
  }finally{marketTimer=setTimeout(pollMarket,15000);}
}
function render(value){
  const r=validateLiveSnapshot(value),frame=r.frames.at(-1);observerStatus=r.status;paintState();
  $('live-count').textContent=r.total_observed_events.toLocaleString();
  $('live-stop').disabled=terminal.has(r.status);$('live-export').disabled=!frame;
  if(!frame){status(r.status==='preparing-brain'?'Preparing all 302 neurons. Export and native compilation can take a few minutes.':r.error||'Waiting for the first real transaction observation.');return;}
  const m=frame.market;
  status(r.error||(r.status==='stopped'?'Session stopped. Live token data remains connected.':`Observed ${r.total_stimulated_events} fresh trades for stimulation. ${m.feed_status==='observed-trades'?'The brain retains its state between updates.':'No new fresh trades: external sensory currents are zero.'}`));
  const age=m.latest_trade_at?Math.max(0,Math.floor(Date.now()/1000-m.latest_trade_at)):null;
  $('live-coverage').textContent=`Pons indexer · ${m.coverage} · ${m.gap_count} polling gaps · latest indexed trade ${age===null?'unavailable':age+'s ago'}. Amounts are in GOOGL; receipts, liquidity and executable price impact are unverified.`;
  if(lastRoot===r.audit_root)return;lastRoot=r.audit_root;
  $('live-sides').textContent=`${m.buy_events??0} / ${m.sell_events??0}`;
  $('live-price').textContent=m.price_quote?m.price_quote.toPrecision(5):'Unavailable';
  $('live-forward').textContent=frame.scores.forward.toFixed(3);$('live-reverse').textContent=frame.scores.reverse.toFixed(3);$('live-time').textContent=`${frame.time_ms.toFixed(0)} ms`;
  $('live-sensory').replaceChildren(...SENSORY.map(name=>{const row=document.createElement('div');row.className='sensory-row';const label=document.createElement('span');label.textContent=name;const value=document.createElement('span');value.textContent=frame.stimulus_pa[name].toFixed(2)+' pA';const bar=document.createElement('progress');bar.max=5;bar.value=frame.stimulus_pa[name];bar.setAttribute('aria-label',name+' live current');row.append(label,value,bar);return row;}));
  trace(frame);
}
async function poll(){
  try{const value=await request('/api/live');render(value);if(terminal.has(value.status)){$('live-start').disabled=false;return;}}
  catch(error){observerStatus='disconnected';paintState();status(marketOnline?`Live token data is connected. ${error.message}`:error.message);$('live-start').disabled=false;return;}
  pollTimer=setTimeout(poll,5000);
}
$('live-start').addEventListener('click',async()=>{
  if(busy)return;busy=true;clearTimeout(pollTimer);lastRoot=null;
  try{
    connection={base:workerBase($('worker-url').value,location.origin),token:$('worker-token').value};
    const current=validateLiveSnapshot(await request('/api/live'));
    if(terminal.has(current.status)){await request('/api/live/start','POST');observerStatus='preparing-brain';paintState();}
    $('live-start').disabled=true;$('live-stop').disabled=false;await poll();
  }catch(error){observerStatus='disconnected';paintState();status(marketOnline?`Live token data is connected. ${error.message}`:error.message);$('live-start').disabled=false;}finally{busy=false;}
});
$('live-stop').addEventListener('click',async()=>{try{await request('/api/live/stop','POST');status('Stopping the neural session. Live token data remains connected.');}catch(error){status(error.message);}});
$('live-export').addEventListener('click',async()=>{try{const value=validateLiveSnapshot(await request('/api/live?history=true'));const url=URL.createObjectURL(new Blob([JSON.stringify(value,null,2)],{type:'application/json'}));const a=document.createElement('a');a.href=url;a.download='wormbrain-live-observations.json';a.click();setTimeout(()=>URL.revokeObjectURL(url),1000);}catch(error){status(error.message);}});

paintState();
pollMarket();
