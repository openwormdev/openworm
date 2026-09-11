export const FORWARD = ['AVBL', 'AVBR', 'PVCL', 'PVCR'];
export const REVERSE = ['AVAL', 'AVAR', 'AVDL', 'AVDR', 'AVEL', 'AVER'];
export const SENSORY = ['ASEL', 'ASER', 'AWAL', 'AWAR', 'AWCL', 'AWCR', 'ASHL', 'ASHR'];
const finite = (x) => typeof x === 'number' && Number.isFinite(x);
const hash = (x) => typeof x === 'string' && /^[a-f0-9]{64}$/.test(x);
export function validateReport(r) {
  const fail = () => { throw new Error('This file is not a supported WormStreet reference report.'); };
  if (!r || r.schema_version !== 1 || r.trading_mode !== 'paper' || r.simulation_mode !== 'real-c302' || r.model?.kind !== 'c302-reference') fail();
  if (!['synthetic', 'user-provided-unverified'].includes(r.market_source) || !['trend','reversal','liquidity-shock','imported-replay'].includes(r.scenario)) fail();
  if (!hash(r.report_hash) || !hash(r.audit_root) || !hash(r.model.network_sha256) || !hash(r.model.jar_sha256)) fail();
  if (!Number.isInteger(r.model.neurons) || r.model.neurons < 10 || r.model.neurons > 1000) fail();
  if (!Number.isInteger(r.model.projections) || r.model.projections < 0) fail();
  for (const n of ['c302','runtime','reader']) if (typeof r.model[n] !== 'string' || r.model[n].length > 200) fail();
  for (const n of ['warmup_ms','episode_ms','readout_ms']) if (!finite(r.config?.[n]) || r.config[n] <= 0 || r.config[n] > 100000) fail();
  if (r.config.readout_ms > r.config.episode_ms) fail();
  for (const n of ['initial_cash','min_liquidity','max_impact_bps']) if (!finite(r.policy?.[n]) || r.policy[n] < 0 || r.policy[n] > 1e12) fail();
  if (!Array.isArray(r.rows) || r.rows.length < 2 || r.rows.length > 24) fail();
  for (let i = 0; i < r.rows.length; i++) {
    const x = r.rows[i];
    if (x.tick?.tick !== i || x.tick.seconds !== i * 15 || !finite(x.tick.price) || x.tick.price <= 0) fail();
    for (const n of ['price','liquidity','flow','price_impact_bps']) if (!finite(x.tick[n]) || Math.abs(x.tick[n]) > 1e12) fail();
    if (x.tick.liquidity < 0 || x.tick.price_impact_bps < 0 || Math.abs(x.tick.flow) > 1) fail();
    for (const n of ['fresh','eligible']) if (typeof x.tick[n] !== 'boolean') fail();
    for (const n of ['cash','units','equity','realized_pnl']) if (!finite(x[n]) || Math.abs(x[n]) > 1e15) fail();
    if (!['ENTER','HOLD','EXIT'].includes(x.intent) || !['ALLOW','BLOCK','FORCE_EXIT'].includes(x.risk)) fail();
    if (!['FILLED','EXIT_UNFILLED','NO_ORDER'].includes(x.execution) || !['FLAT','HELD'].includes(x.position)) fail();
    if (!Array.isArray(x.reasons) || x.reasons.some(n => typeof n !== 'string' || !/^[A-Z_]{1,40}$/.test(n))) fail();
    if (!hash(x.event_hash) || x.previous_hash !== (i ? r.rows[i-1].event_hash : 'genesis')) fail();
    for (const n of ['forward','reverse','margin']) if (!finite(x.scores?.[n]) || Math.abs(x.scores[n]) > 1) fail();
    for (const n of SENSORY) if (!finite(x.stimulus_pa?.[n]) || x.stimulus_pa[n] < 0 || x.stimulus_pa[n] > 5) fail();
    if (x.fill && (!['BUY','SELL'].includes(x.fill.side) || !finite(x.fill.fee) || !finite(x.fill.price) || !finite(x.fill.units))) fail();
  }
  if (r.audit_root !== r.rows.at(-1).event_hash) fail();
  const times = r.traces?.time_ms;
  if (!Array.isArray(times) || times.length < 2 || times.length > 1000 || times.some((t,i) => !finite(t) || (i && t <= times[i-1]))) fail();
  for (const n of [...FORWARD, ...REVERSE, ...SENSORY]) {
    const trace = r.traces.voltage_mv?.[n];
    if (!Array.isArray(trace) || trace.length !== times.length || trace.some(x => !finite(x))) fail();
  }
  return r;
}
export function meanTrace(report, neurons) {
  return report.traces.time_ms.map((_,i) => neurons.reduce((sum,n) => sum + report.traces.voltage_mv[n][i],0)/neurons.length);
}
export function workerBase(input, pageOrigin) {
  const url = new URL(input || pageOrigin);
  const local = ['localhost', '127.0.0.1', '[::1]'].includes(url.hostname);
  if ((url.protocol !== 'https:' && !(url.protocol === 'http:' && local)) || url.username || url.password || url.search || url.hash) throw new Error('Use an HTTPS worker URL, or HTTP on localhost.');
  if (url.pathname !== '/') throw new Error('Use the worker origin without a path.');
  return url.origin;
}
export async function sha256(text) {
  const bytes = await crypto.subtle.digest('SHA-256',new TextEncoder().encode(text));
  return [...new Uint8Array(bytes)].map(b=>b.toString(16).padStart(2,'0')).join('');
}
