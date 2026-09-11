import {CURRENT_LIMITS,FORWARD,REVERSE,SENSORY,meanTrace,workerBase,validateLiveSnapshot,validateTokenMarket} from './report.js';
const $=id=>document.getElementById(id);
let connection=null,pollTimer=null,marketTimer=null,publishedTimer=null,busy=false,lastRoot=null,recordedSnapshot=false,publishedRecording=null,publishedIndex=0;
let marketOnline=false,marketAttempted=false,observerStatus='idle';
const terminal=new Set(['idle','stopped','failed']);
const observerActive=()=>!terminal.has(observerStatus)&&observerStatus!=='disconnected';
function status(text){$('live-status').textContent=text;}
function paintState(){
  $('live-state').textContent=observerActive()?observerStatus.toUpperCase().replaceAll('-',' '):recordedSnapshot?`RECORDED ${publishedRecording?.frames.length??0} TICKS`:marketOnline?'TOKEN LIVE':marketAttempted?'FEED RETRYING':'CONNECTING';
}
function clock(seconds){return `T + ${String(Math.floor(seconds/60)).padStart(2,'0')}:${String(seconds%60).padStart(2,'0')}`;}
function stopPublishedPlayback(){clearInterval(publishedTimer);publishedTimer=null;$('live-replay').textContent='▶ Replay observer run';}
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
  if(!observerActive())status(recordedSnapshot?'Live WORMBRAIN token data connected. The neural panel shows the published continuous observer run; start a worker for fresh neural ticks.':'Live WORMBRAIN token data connected. The optional Python worker below runs the c302 neural observer.');
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
function render(value,{recorded=false}={}){
  const r=validateLiveSnapshot(value),frame=recorded?r.frames[publishedIndex]:r.frames.at(-1);observerStatus=r.status;paintState();
  $('live-stop').disabled=terminal.has(r.status);$('live-export').disabled=!frame;
  if(!frame){status(r.status==='preparing-brain'?'Preparing the complete generated network. Export and native compilation can take a few minutes.':r.error||'Waiting for the first real transaction observation.');return;}
  const m=frame.market;
  status(recorded?'Published continuous token observer run. Absolute wall-clock fields were removed; relative neural and paper-risk timelines remain.':r.error||(r.status==='stopped'?'Session stopped. Live token data remains connected.':`Observed ${r.total_stimulated_events} fresh trades for stimulation. ${m.feed_status==='observed-trades'?'The brain, plastic gain, decoder, and paper-risk state persist between updates.':'No new fresh trades: external sensory currents are zero.'}`));
  if(!recorded){
    const age=m.latest_trade_at?Math.max(0,Math.floor(Date.now()/1000-m.latest_trade_at)):null;
    $('live-count').textContent=r.total_observed_events.toLocaleString();$('live-sides').textContent=`${m.buy_events??0} / ${m.sell_events??0}`;$('live-price').textContent=m.price_quote?m.price_quote.toPrecision(5):'Unavailable';
    $('live-coverage').textContent=`Pons indexer · ${m.coverage} · ${m.gap_count} polling gaps · latest indexed trade ${age===null?'unavailable':age+'s ago'}. Amounts are in GOOGL; receipts, liquidity and executable price impact are unverified.`;
  }else{
    const tick=frame.paper_tick;
    $('live-scrubber').value=publishedIndex;$('live-frame-label').textContent=`${frame.decoder.state} · ${frame.risk}`;$('live-frame-time').textContent=clock(tick.seconds);$('live-frame-count').textContent=`${publishedIndex+1} / ${r.frames.length}`;
    $('live-frame-summary').textContent=`${m.new_events} new indexed events · ${m.stimulated_events} fresh stimuli · recorded price ${m.price_quote?m.price_quote.toPrecision(5):'unavailable'} GOOGL · ${m.feed_status.replaceAll('-',' ')}`;
  }
  const renderKey=`${r.audit_root}:${frame.event_hash}`;if(lastRoot===renderKey)return;lastRoot=renderKey;
  $('live-forward').textContent=frame.scores.forward.toFixed(3);$('live-reverse').textContent=frame.scores.reverse.toFixed(3);$('live-time').textContent=`${frame.time_ms.toFixed(0)} ms`;
  $('live-decoder').textContent=frame.decoder?.state??'LEGACY';
  $('live-rim-rib').textContent=frame.scores.vector?.rim==null?'NOT RECORDED':`${frame.scores.vector.rim.toFixed(3)} / ${frame.scores.vector.rib.toFixed(3)}`;
  $('live-plasticity').textContent=frame.plasticity?`${frame.plasticity.applied_gain.toFixed(3)} → ${frame.plasticity.next_gain.toFixed(3)}`:'NOT ACTIVE';
  const feedback=frame.next_feedback_pa;$('live-feedback').textContent=feedback?`${Math.max(feedback.PVCL,feedback.PVCR).toFixed(2)} / ${feedback.DVA.toFixed(2)} pA`:'NOT ACTIVE';
  $('live-risk').textContent=frame.risk?`${frame.risk} · ${frame.execution}`:'OBSERVER ONLY';
  $('live-reasons').textContent=frame.reasons?.length?frame.reasons.join(' · '):'NONE';
  $('live-model-proof').textContent=r.model?`${r.model.neurons} neurons · ${r.model.projections} projections · ${(r.model.reader??'unknown reader').replace('cect.readers.','')} · model ${r.model.network_sha256?.slice(0,12)??'unpublished'} · reader ${r.model.reader_cache_sha256?.slice(0,12)??'legacy'}`:'Model identity unavailable.';
  $('live-sensory').replaceChildren(...SENSORY.map(name=>{const row=document.createElement('div');row.className='sensory-row';const label=document.createElement('span');label.textContent=name;const value=document.createElement('span');value.textContent=frame.stimulus_pa[name].toFixed(2)+' pA';const bar=document.createElement('progress');bar.max=CURRENT_LIMITS[name];bar.value=frame.stimulus_pa[name];bar.setAttribute('aria-label',name+' live current');row.append(label,value,bar);return row;}));
  trace(frame);
}
async function poll(){
  try{const value=await request('/api/live');render(value);if(terminal.has(value.status)){$('live-start').disabled=false;return;}}
  catch(error){observerStatus='disconnected';paintState();status(marketOnline?`Live token data is connected. ${error.message}`:error.message);$('live-start').disabled=false;return;}
  pollTimer=setTimeout(poll,5000);
}
async function loadPublishedRecording(){
  try{
    const response=await fetch('/data/live-observer.json',{headers:{Accept:'application/json'},redirect:'error',signal:AbortSignal.timeout(15000)});
    if(!response.ok)return;
    publishedRecording=validateLiveSnapshot(await response.json());publishedIndex=publishedRecording.frames.length-1;recordedSnapshot=true;$('live-recording-link').hidden=false;$('live-timeline').hidden=false;$('live-scrubber').max=publishedIndex;render(publishedRecording,{recorded:true});paintState();
  }catch{}
}
$('live-scrubber').addEventListener('input',event=>{if(!publishedRecording)return;stopPublishedPlayback();publishedIndex=Number(event.target.value);lastRoot=null;render(publishedRecording,{recorded:true});});
$('live-replay').addEventListener('click',()=>{if(!publishedRecording)return;if(publishedTimer){stopPublishedPlayback();return;}publishedIndex=0;lastRoot=null;render(publishedRecording,{recorded:true});$('live-replay').textContent='Ⅱ Pause observer run';publishedTimer=setInterval(()=>{if(++publishedIndex>=publishedRecording.frames.length){publishedIndex=publishedRecording.frames.length-1;stopPublishedPlayback();return;}lastRoot=null;render(publishedRecording,{recorded:true});},1800);});
$('live-start').addEventListener('click',async()=>{
  if(busy)return;busy=true;clearTimeout(pollTimer);stopPublishedPlayback();lastRoot=null;
  try{
    connection={base:workerBase($('worker-url').value,location.origin),token:$('worker-token').value};
    const current=validateLiveSnapshot(await request('/api/live'));
    recordedSnapshot=false;$('live-timeline').hidden=true;
    if(terminal.has(current.status)){await request('/api/live/start','POST');observerStatus='preparing-brain';paintState();}
    $('live-start').disabled=true;$('live-stop').disabled=false;await poll();
  }catch(error){observerStatus='disconnected';if(publishedRecording){recordedSnapshot=true;$('live-timeline').hidden=false;lastRoot=null;render(publishedRecording,{recorded:true});}paintState();status(`${marketOnline?'Live token data is connected. ':''}${error.message}${publishedRecording?' The published observer run remains available.':''}`);$('live-start').disabled=false;}finally{busy=false;}
});
$('live-stop').addEventListener('click',async()=>{try{await request('/api/live/stop','POST');status('Stopping the neural session. Live token data remains connected.');}catch(error){status(error.message);}});
$('live-export').addEventListener('click',async()=>{try{const value=recordedSnapshot?validateLiveSnapshot(publishedRecording):validateLiveSnapshot(await request('/api/live?history=true'));const url=URL.createObjectURL(new Blob([JSON.stringify(value,null,2)],{type:'application/json'}));const a=document.createElement('a');a.href=url;a.download='wormbrain-live-observations.json';a.click();setTimeout(()=>URL.revokeObjectURL(url),1000);}catch(error){status(error.message);}});

paintState();
pollMarket();
loadPublishedRecording();
