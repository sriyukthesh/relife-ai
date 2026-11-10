const $ = (id) => document.getElementById(id);
const esc = (s) => String(s ?? '').replace(/[&<>"']/g, (c) => ({ '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;', "'": '&#39;' }[c]));
const usd = (c) => '$' + (c / 100).toFixed(2);
const fmt = (iso) => (iso ? new Date(iso).toLocaleString([], { month: 'short', day: 'numeric', hour: '2-digit', minute: '2-digit' }) : '-');
const supplierUrl = (value) => {
  try {
    const url = new URL(value);
    return url.protocol === 'http:' || url.protocol === 'https:' ? url.href : '';
  } catch {
    return '';
  }
};
let state = null;

function say(t, cls = 'note') { $('msg').className = cls; $('msg').textContent = t; }

async function api(path, opts = {}) {
  const headers = new Headers(opts.headers);
  const token = localStorage.getItem('sl_token');
  if (token) headers.set('Authorization', `Bearer ${token}`);
  if (opts.body) headers.set('Content-Type', 'application/json');
  const r = await fetch(path, { ...opts, headers });
  let data = null;
  try { data = await r.json(); } catch { /* Non-JSON error responses use their status text. */ }
  if (!r.ok) {
    const d = data && data.detail;
    throw new Error((typeof d === 'string' ? d : d ? JSON.stringify(d) : '') || r.statusText);
  }
  return data;
}

function refreshFrames() {
  for (const id of ['gantt', 'scheduler']) {
    const w = $(id).contentWindow;
    if (w) w.postMessage({ type: 'reload' }, location.origin);
  }
}

function render(s) {
  state = s;
  const has = s.exists;
  const m = has ? s.metrics : null;
  $('cards').innerHTML = has ? [
    ['Finish', fmt(m.finish), `Deadline ${esc(m.deadline)}`, m.on_time ? 'ok' : 'bad'],
    ['Status', m.on_time ? 'On track' : `${m.late_days} day(s) late`, m.within_budget ? 'Within budget' : 'Over budget', m.on_time && m.within_budget ? 'ok' : 'bad'],
    ['Spend', usd(m.cost_cents), `Budget ${usd(m.budget_cents)}`, m.within_budget ? 'ok' : 'bad'],
    ['Salvaged vs bought', `${m.salvaged_units} / ${m.purchased_units}`, `${Math.round(m.salvage_rate * 100)}% of parts reused`, 'ok'],
  ].map(([a, b, c, k]) => `<div class="card"><span>${a}</span><b class="${k}">${esc(b)}</b><span>${c}</span></div>`).join('') : '';

  $('options').innerHTML = has && s.recombination.length ? s.recombination.map((o) => `
    <div class="opt"><div><b>${o.names.map(esc).join(' + ')}</b><br>
      <span class="note">${Math.round(o.salvage_rate * 100)}% reused (${o.salvaged_units} salvaged, ${o.purchased_units} to buy), est. spend ${usd(o.cost_cents)}</span></div>
      <button class="secondary" data-keys="${esc(o.keys.join(','))}">Build this</button></div>`).join('')
    : '<span class="note">Build a plan to see ranked project combinations.</span>';
  document.querySelectorAll('#options button').forEach((b) => (b.onclick = () => build(b.dataset.keys.split(','))));

  const active = has ? s.purchases : [];
  $('delay-part').innerHTML = active.filter((p) => ['planned', 'in_cart', 'ordered'].includes(p.status))
    .map((p) => `<option value="${esc(p.id)}">${esc(p.part)} (${esc(p.status)})</option>`).join('') || '<option value="">No active purchases</option>';
  $('fail-part').innerHTML = has ? s.inventory.map((it, i) => `<option value="${i}">${esc(it.name)} (${it.quantity - (it.failed || 0)} working)</option>`).join('') : '';

  const STATUS = { planned: 'planned', ordered: 'user-confirmed ordered' };
  $('purchases').innerHTML = active.length ? `<table><tr><th>For</th><th>Part</th><th>Supplier listing</th><th>Source</th><th>Packs</th><th>Cost</th><th>Sim. ETA</th><th>Status</th><th></th></tr>${
    active.map((p) => `<tr><td>${esc(p.project)}</td><td>${esc(p.part)}</td><td>${esc(p.title)}</td>
      <td>${esc(p.source || 'unknown')}</td><td>${p.packs}</td>
      <td>${usd(p.packs * p.unit_price_cents)}</td><td>${p.eta_days + p.delay_days}d${p.delay_days ? ' (delayed)' : ''}</td>
      <td>${esc(STATUS[p.status] || p.status)}</td><td>${supplierUrl(p.url) ? `<a href="${esc(supplierUrl(p.url))}" target="_blank" rel="noopener noreferrer">Open supplier</a>` : 'Supplier link unavailable'}
      ${p.status === 'planned' ? `<button class="secondary" data-purchase="${esc(p.id)}">Mark ordered</button>` : ''}</td></tr>`).join('')}</table>`
    : '<span class="note">Nothing to buy. Everything comes from your salvaged inventory.</span>';
  document.querySelectorAll('#purchases [data-purchase]').forEach((button) => {
    button.onclick = () => markOrdered(button.dataset.purchase);
  });
  if (has && s.unsourced.length) $('purchases').innerHTML += `<p class="err">No listing found for: ${s.unsourced.map((u) => esc(u.part)).join(', ')}</p>`;

  $('log').innerHTML = has && s.log.length ? s.log.map((l) => `
    <div class="log ${l.kind === 'plan_created' || l.kind === 'payment_sync' || l.kind === 'optimize' ? '' : 'warnlog'}">
      <small>${esc(fmt(l.ts))} - ${esc(l.kind.replace('_', ' '))}${l.ai_used ? ' - reasoning by Muse Spark' : ''}</small>
      ${esc(l.summary)}
      ${l.reason ? `<br><i>${esc(l.reason)}</i>` : ''}
      ${l.considered ? '<br>' + l.considered.map((c) => `<span class="chip ${c.chosen ? 'pick' : ''}">${esc(c.title)}: ${c.late_days}d late, ${c.extra_cost_cents >= 0 ? '+' : '-'}${usd(Math.abs(c.extra_cost_cents))}${c.feasible ? '' : ' (not feasible)'}</span>`).join('') : ''}
    </div>`).join('') : '<span class="note">No decisions yet.</span>';

  refreshFrames();
}

async function run(label, fn) {
  say(label + '...');
  document.querySelectorAll('button').forEach((b) => (b.disabled = true));
  try { render(await fn()); say('Done.'); }
  catch (e) { say(e.message, 'err'); }
  finally { document.querySelectorAll('button').forEach((b) => (b.disabled = false)); if (state) render(state); }
}

function build(keys) {
  return run('Recombining your inventory and building the plan', () => api('/api/timeline/demo', {
    method: 'POST',
    body: JSON.stringify({ budget_usd: parseFloat($('budget').value), deadline_days: parseInt($('deadline').value, 10), project_keys: keys || null }),
  }));
}
$('build').onclick = () => build(null);
$('do-delay').onclick = () => run('Agent is recovering from the delay', () => api('/api/timeline/event', {
  method: 'POST', body: JSON.stringify({ type: 'delivery_delay', purchase_id: $('delay-part').value, days: parseInt($('delay-days').value, 10) }) }));
$('do-fail').onclick = () => run('Agent is recovering from the failed part', () => api('/api/timeline/event', {
  method: 'POST', body: JSON.stringify({ type: 'component_failed', inventory_index: parseInt($('fail-part').value, 10), quantity: 1 }) }));
$('do-deadline').onclick = () => {
  const cur = Math.round((new Date(state.metrics.deadline) - new Date(state.settings.start_date)) / 86400000);
  return run('Agent is adapting to the new deadline', () => api('/api/timeline/event', {
    method: 'POST', body: JSON.stringify({ type: 'deadline_change', deadline_days: Math.max(1, cur - 3) }) }));
};
$('do-budget').onclick = () => run('Agent is adapting to the new budget', () => api('/api/timeline/event', {
  method: 'POST', body: JSON.stringify({ type: 'budget_change', budget_usd: Math.max(1, (state.metrics.budget_cents / 100) * 0.7) }) }));
$('optimize').onclick = () => run('Optimizing shared resources', () => api('/api/timeline/optimize', { method: 'POST' }));

function markOrdered(purchaseId) {
  return run('Recording the supplier purchase', () =>
    api(`/api/timeline/purchases/${encodeURIComponent(purchaseId)}/ordered`, { method: 'POST' }));
}

(async () => {
  try {
    render(await api('/api/timeline/state'));
    if (!state.exists) say('Click "Build best plan from my inventory" to start.');
  } catch (e) { say('Startup error: ' + e.message, 'err'); }
})();
