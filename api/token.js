const TOKEN='0x2703295342c5914e0292adfdb612618ce24105d1';
const TRADE_URL=`https://www.ponsfamily.com/api/pons-v2-market/${TOKEN}/trades`;
const EVENT=/^4663:(\d+):(0x[0-9a-f]{64}):(\d+)$/i;
const UINT=/^[0-9]{1,78}$/;
const MAX_RESPONSE_BYTES=2_000_000;

function validAmount(value){
  return typeof value==='string'&&UINT.test(value)&&BigInt(value)>0n&&BigInt(value)<2n**256n;
}

function decimalRatio(numerator,denominator){
  const value=Number(numerator)/Number(denominator);
  if(!Number.isFinite(value)||value<=0)throw new Error('Invalid indexed trade price');
  return value;
}

export function summarizeTrades(payload,now=Math.floor(Date.now()/1000)){
  if(!payload||!Array.isArray(payload.trades)||payload.trades.length>500)throw new Error('Invalid indexer response');
  const unique=new Map();
  for(const row of payload.trades){
    if(!row||typeof row!=='object')throw new Error('Invalid indexed trade');
    const match=typeof row.id==='string'?EVENT.exec(row.id):null;
    if(!match||typeof row.transactionHash!=='string'||row.transactionHash.toLowerCase()!==match[2].toLowerCase())throw new Error('Invalid indexed trade identity');
    if(!Number.isSafeInteger(row.blockNumber)||row.blockNumber!==Number(match[1])||row.blockNumber<=0)throw new Error('Invalid indexed block');
    const logIndex=Number(match[3]);
    if(!Number.isSafeInteger(logIndex)||logIndex>1_000_000)throw new Error('Invalid indexed log');
    if(!Number.isSafeInteger(row.timestamp)||row.timestamp<=0||row.timestamp>now+10)throw new Error('Invalid indexed timestamp');
    if(!['buy','sell'].includes(row.side)||!['curve','pool'].includes(row.venue))throw new Error('Invalid indexed trade kind');
    if(!validAmount(row.tokenAmount)||!validAmount(row.quoteAmount))throw new Error('Invalid indexed amount');
    const safe={id:row.id.toLowerCase(),block:row.blockNumber,logIndex,timestamp:row.timestamp,side:row.side,venue:row.venue,tokenAmount:row.tokenAmount,quoteAmount:row.quoteAmount};
    const previous=unique.get(safe.id);
    if(previous&&JSON.stringify(previous)!==JSON.stringify(safe))throw new Error('Conflicting indexed trade');
    unique.set(safe.id,safe);
  }
  const trades=[...unique.values()].sort((a,b)=>a.block-b.block||a.logIndex-b.logIndex);
  const latest=trades.at(-1);
  return {
    schema_version:1,
    kind:'wormbrain-token-market',
    status:'connected',
    source:{provider:'pons-public-indexer',token:TOKEN,chain_id:4663,quote_symbol:'GOOGL',coverage:'recent-indexed-window'},
    recent:{
      events:trades.length,
      buy_events:trades.filter(row=>row.side==='buy').length,
      sell_events:trades.filter(row=>row.side==='sell').length,
      price_quote:latest?decimalRatio(latest.quoteAmount,latest.tokenAmount):null,
      latest_trade_at:latest?.timestamp??null,
      latest_block:latest?.block??null,
    },
  };
}

export async function GET(){
  const timeout=AbortSignal.timeout(12_000);
  try{
    const upstream=await fetch(TRADE_URL,{headers:{Accept:'application/json'},redirect:'error',signal:timeout});
    if(!upstream.ok)throw new Error('Indexer unavailable');
    const declared=Number(upstream.headers.get('content-length'));
    if(Number.isFinite(declared)&&declared>MAX_RESPONSE_BYTES)throw new Error('Indexer response too large');
    const raw=await upstream.text();
    if(Buffer.byteLength(raw)>MAX_RESPONSE_BYTES)throw new Error('Indexer response too large');
    const snapshot=summarizeTrades(JSON.parse(raw));
    return Response.json(snapshot,{headers:{'Cache-Control':'public, s-maxage=10, stale-while-revalidate=20','X-Content-Type-Options':'nosniff'}});
  }catch{
    return Response.json({schema_version:1,kind:'wormbrain-token-market',status:'unavailable'},{status:503,headers:{'Cache-Control':'no-store','X-Content-Type-Options':'nosniff'}});
  }
}
