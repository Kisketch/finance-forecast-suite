/* FinPredict — 前端逻辑 */
const $ = (s, el = document) => el.querySelector(s);
const state = { symbol: '000001.SS', interval: '1d', charts: {}, aiTpl: 'trend_analysis', lastForecast: null, lastBacktest: null };
const toast = (msg, type = '') => { const t = $('#toast'); t.textContent = msg; t.className = 'toast show ' + type; setTimeout(() => t.classList.remove('show'), 3000); };
// fetch 带超时（30s），避免网络慢时界面卡死
const fetchWithTimeout = async (url, opts = {}, ms = 30000) => {
  const ctrl = new AbortController();
  const timer = setTimeout(() => ctrl.abort(), ms);
  try { return await fetch(url, { ...opts, signal: ctrl.signal }); }
  finally { clearTimeout(timer); }
};
const api = async (p, ms = 30000) => {
  const r = await fetchWithTimeout(p, {}, ms);
  const d = await r.json().catch(() => ({}));
  if (!r.ok && d.error) throw new Error(d.error);
  return d;
};
const post = async (p, b = {}, ms = 120000) => {
  const r = await fetchWithTimeout(p, { method: 'POST', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify(b) }, ms);
  const d = await r.json().catch(() => ({}));
  if (!r.ok && d.error) throw new Error(d.error);
  return d;
};
const fmt = (v, d = 2) => (v == null || Number.isNaN(v)) ? '—' : Number(v).toLocaleString('en-US', { minimumFractionDigits: d, maximumFractionDigits: d });
const pct = (v, d = 2) => (v == null || Number.isNaN(v)) ? '—' : `${(v * 100).toFixed(d)}%`;
const cls = (v) => v > 0 ? 'up' : v < 0 ? 'down' : 'flat';
const esc = (s) => String(s ?? '').replace(/[&<>"']/g, c => ({ '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;', "'": '&#39;' }[c]));
const AXIS = { axisLine: { lineStyle: { color: '#243140' } }, axisLabel: { color: '#6D7E90', fontSize: 10 }, splitLine: { lineStyle: { color: '#1A2530' } }, axisTick: { show: false } };
const TIP = { backgroundColor: '#161E27', borderColor: '#3A4A5C', textStyle: { color: '#E8EDF4', fontSize: 11 } };
function chart(id) { if (state.charts[id]) return state.charts[id]; const el = document.getElementById(id); if (!el) return null; const c = echarts.init(el); state.charts[id] = c; return c; }
window.addEventListener('resize', () => Object.values(state.charts).forEach(c => c && c.resize()));

/* 导航 */
function switchPage(page) {
  $$('.nav-item').forEach(b => b.classList.toggle('active', b.dataset.page === page));
  $$('.page').forEach(p => p.classList.toggle('active', p.id === `page-${page}`));
  const titles = { quote: ['实时行情', '多周期 K 线 · 实时联网'], forecast: ['趋势预判', '多时间维度 · 置信区间'], backtest: ['回测检验', '历史验证 · 模型修正'], ai: ['AI 助手', '内置提示词 · 一键分析'] };
  const [t, s] = titles[page]; $('#pageTitle').textContent = t; $('#pageSub').textContent = s;
  setTimeout(() => Object.values(state.charts).forEach(c => c && c.resize()), 30);
  if (page === 'forecast') loadForecast();
  if (page === 'backtest') loadBacktest();
  if (page === 'ai') loadAITemplates();
}
$$('.nav-item').forEach(b => b.addEventListener('click', () => switchPage(b.dataset.page)));

/* 标的/周期切换 */
$('#refreshBtn').addEventListener('click', () => { state.symbol = $('#symbolInput').value.trim() || '000001.SS'; state.interval = $('#intervalSelect').value; refreshAll(); });
$('#symbolInput').addEventListener('change', () => { state.symbol = $('#symbolInput').value.trim() || '000001.SS'; refreshAll(); });
$('#intervalSelect').addEventListener('change', () => { state.interval = $('#intervalSelect').value; refreshAll(); });

async function loadSymbols() {
  try { const d = await api('/api/symbols'); const dl = $('#symList'); dl.innerHTML = d.symbols.map(s => `<option value="${s}">`).join(''); } catch (e) { /* 忽略 */ }
}

/* 实时行情 */
const skeleton = (n = 4) => Array(n).fill(0).map(() => '<div class="kpi skeleton"><div class="k-label">—</div><div class="k-val">—</div></div>').join('');
function showRetry(containerSel, msg, retryFn) {
  const el = $(containerSel);
  if (!el) return;
  el.innerHTML = `<div class="retry-box"><div class="retry-msg">${esc(msg)}</div><button class="btn primary retry-btn">重试</button></div>`;
  el.querySelector('.retry-btn').addEventListener('click', retryFn);
}
async function loadQuote() {
  $('#sideStatus').textContent = '拉取中…'; $('#statusDot').className = 'dot busy';
  $('#quoteKpis').innerHTML = skeleton(4);  // 骨架占位，避免空白卡顿感
  try {
    const d = await api(`/api/quote?symbol=${encodeURIComponent(state.symbol)}&interval=${state.interval}`);
    if (d.error) throw new Error(d.error);
    drawKpis(d); drawKline(d); drawRsi(d); drawVol(d);
    $('#quoteRange').textContent = `${d.interval_label} · ${d.rows} 根 · 截止 ${d.as_of}`;
    $('#sideStatus').textContent = '数据已连接'; $('#statusDot').className = 'dot ok';
    state.lastQuote = d;
  } catch (e) {
    const msg = e.name === 'AbortError' ? '数据获取超时（网络较慢或 Yahoo 限流），请重试' : (e.message || '获取失败');
    showRetry('#quoteKpis', msg, loadQuote);
    $('#sideStatus').textContent = '获取失败'; $('#statusDot').className = 'dot err';
    toast(msg, 'err');
  }
}
function drawKpis(d) {
  const last = d.last_close; const closes = d.close || []; const prev = closes.length > 1 ? closes[closes.length - 2] : last;
  const chg = last && prev ? (last - prev) / prev : null;
  const rsi = d.rsi14 ? d.rsi14[d.rsi14.length - 1] : null;
  const vol = d.volume ? d.volume[d.volume.length - 1] : null;
  $('#quoteKpis').innerHTML = [
    kpi('最新价', fmt(last, 2), `${pct(chg)}`, cls(chg)),
    kpi('区间', d.interval_label, `${fmt(d3(d, 'low'), 2)} ~ ${fmt(d3(d, 'high'), 2)}`, ''),
    kpi('RSI14', rsi == null ? '—' : fmt(rsi, 1), rsi > 70 ? '超买' : rsi < 30 ? '超卖' : '', cls(50 - rsi)),
    kpi('成交量', fmt(vol, 0), d.info?.name || state.symbol, ''),
  ].join('');
}
const kpi = (l, v, s, c) => `<div class="kpi"><div class="k-label">${l}</div><div class="k-val ${c || ''}">${v}</div><div class="k-sub ${c || ''}">${s || ''}</div></div>`;
const d3 = (d, k) => { const a = d[k]; return a && a.length ? Math.min(...a.filter(x => x != null)) : null; };

function drawKline(d) {
  const c = chart('klineChart'); if (!c) return;
  const dates = d.dates, n = dates.length, slice = (a, k = 600) => a.slice(-k);
  const ohlc = d.close.map((cl, i) => [d.open[i], d.close[i], d.low[i], d.high[i]]).slice(-600);
  c.setOption({
    backgroundColor: 'transparent', tooltip: { ...TIP, trigger: 'axis' },
    legend: { data: ['K线', 'MA5', 'MA20', 'MA60'], textStyle: { color: '#8B9BB0' }, top: 0 },
    grid: { left: 50, right: 16, top: 30, bottom: 50 },
    xAxis: { type: 'category', data: slice(dates), ...AXIS, scale: true },
    yAxis: { scale: true, ...AXIS },
    dataZoom: [{ type: 'inside', start: 70 }, { type: 'slider', bottom: 8, height: 18 }],
    series: [
      { name: 'K线', type: 'candlestick', data: ohlc, itemStyle: { color: '#F23645', color0: '#00C08A', borderColor: '#F23645', borderColor0: '#00C08A' } },
      { name: 'MA5', type: 'line', data: slice(d.ma5), smooth: true, symbol: 'none', lineStyle: { width: 1, color: '#F5A623' } },
      { name: 'MA20', type: 'line', data: slice(d.ma20), smooth: true, symbol: 'none', lineStyle: { width: 1, color: '#3B82F6' } },
      { name: 'MA60', type: 'line', data: slice(d.ma60), smooth: true, symbol: 'none', lineStyle: { width: 1, color: '#8B9BB0' } },
    ],
  }, true);
}
function drawRsi(d) {
  const c = chart('rsiChart'); if (!c) return;
  const dates = (d.dates || []).slice(-600);
  c.setOption({
    backgroundColor: 'transparent', tooltip: { ...TIP, trigger: 'axis' },
    grid: { left: 40, right: 16, top: 16, bottom: 24 },
    xAxis: { type: 'category', data: dates, ...AXIS },
    yAxis: { ...AXIS, min: 0, max: 100 },
    series: [
      { name: 'RSI', type: 'line', data: (d.rsi14 || []).slice(-600), symbol: 'none', smooth: true, lineStyle: { width: 1.5, color: '#F5A623' } },
      { name: 'MACD', type: 'bar', data: (d.macd_hist || []).slice(-600), itemStyle: { color: '#F23645' } },
    ],
  }, true);
}
function drawVol(d) {
  const c = chart('volChart'); if (!c) return;
  const dates = (d.dates || []).slice(-600);
  c.setOption({
    backgroundColor: 'transparent', tooltip: { ...TIP, trigger: 'axis' },
    grid: { left: 50, right: 16, top: 16, bottom: 24 },
    xAxis: { type: 'category', data: dates, ...AXIS },
    yAxis: { ...AXIS },
    series: [{ type: 'bar', data: (d.volume || []).slice(-600), itemStyle: { color: '#243140' } }],
  }, true);
}

/* 趋势预判 */
async function loadForecast() {
  $('#forecastKpis').innerHTML = '<div class="page-loading"><div class="boot-spinner" style="width:20px;height:20px"></div>预判计算中（含模型训练，约 20-30 秒）…</div>';
  try {
    const d = await api(`/api/forecast?symbol=${encodeURIComponent(state.symbol)}&interval=${state.interval}`, 90000);
    if (d.error) throw new Error(d.error);
    state.lastForecast = d; drawForecast(d);
  } catch (e) {
    const msg = e.name === 'AbortError' ? '预判超时，请重试或换标的' : (e.message || '预判失败');
    showRetry('#forecastKpis', msg, loadForecast); toast(msg, 'err');
  }
}
function drawForecast(d) {
  const bt = d.backtest || {};
  const dir = d.direction === 'up' ? '看涨' : d.direction === 'down' ? '看跌' : '震荡';
  $('#fcHorizon').textContent = `${d.horizon} 根 ${d.interval} 周期`;
  $('#forecastKpis').innerHTML = [
    kpi('预判方向', dir, `${fmt(d.point_logret * 100, 3)}%`, d.direction === 'up' ? 'up' : d.direction === 'down' ? 'down' : 'flat'),
    kpi('中位价', fmt(d.q50_price, 2), `${fmt(d.last_close, 2)} → ${fmt(d.q50_price, 2)}`, ''),
    kpi('95%区间', `±${fmt(d.interval_width_pct / 2, 1)}%`, `${fmt(d.q05_price, 1)} ~ ${fmt(d.q95_price, 1)}`, ''),
    kpi('回测方向准确率', pct(bt.dir_acc), `基准始终看多 ${pct(bt.baseline_dir_acc)}`, cls(bt.dir_acc - bt.baseline_dir_acc)),
  ].join('');
  // 预测曲线：历史末段 + 预测点 + 置信扇形
  const q = state.lastQuote; if (!q) return;
  const dates = (q.dates || []).slice(-120); const closes = (q.close || []).slice(-120);
  const extDates = [...dates, '+1'];
  const extClose = [...closes, d.q50_price];
  const up = [...closes.map((_, i) => null), d.q95_price];
  const lo = [...closes.map((_, i) => null), d.q05_price];
  const c = chart('forecastChart'); if (!c) return;
  c.setOption({
    backgroundColor: 'transparent', tooltip: { ...TIP, trigger: 'axis' },
    legend: { data: ['历史收盘', '预判中位', '95%区间'], textStyle: { color: '#8B9BB0' }, top: 0 },
    grid: { left: 50, right: 16, top: 30, bottom: 30 },
    xAxis: { type: 'category', data: extDates, ...AXIS },
    yAxis: { scale: true, ...AXIS },
    series: [
      { name: '历史收盘', type: 'line', data: extClose, symbol: ['none'], symbolSize: (v, p) => p.dataIndex === extClose.length - 1 ? 10 : 0, itemStyle: { color: '#3B82F6' }, lineStyle: { width: 2 } },
      { name: '预判中位', type: 'line', data: [...closes.map(() => null), d.q50_price], symbol: ['circle'], symbolSize: 10, itemStyle: { color: '#F5A623' }, lineStyle: { width: 0 } },
      { name: '95%区间', type: 'custom', data: up.map((v, i) => [lo[i], up[i]]), renderItem: (p, e) => { const s = p.coord(e.data[0] ? [e.dataIndex, e.data[0]] : [e.dataIndex, 0]); } },
    ],
  }, true);
  $('#fcNotes').innerHTML = (d.notes || []).map(n => `<li>${n}</li>`).join('');
}

/* 回测 */
async function loadBacktest() {
  $('#btKpis').innerHTML = '<div class="page-loading"><div class="boot-spinner" style="width:20px;height:20px"></div>回测计算中（walk-forward 滚动验证，约 1-3 分钟）…</div>';
  try {
    const d = await api(`/api/backtest?symbol=${encodeURIComponent(state.symbol)}&interval=${state.interval}`, 240000);
    if (d.error) throw new Error(d.error);
    state.lastBacktest = d; drawBacktest(d);
  } catch (e) {
    const msg = e.name === 'AbortError' ? '回测超时（数据量大），请稍后重试' : (e.message || '回测失败');
    showRetry('#btKpis', msg, loadBacktest); toast(msg, 'err');
  }
}
function drawBacktest(d) {
  const skillCls = d.skill > 0 ? 'up' : 'down';
  $('#btKpis').innerHTML = [
    kpi('样本数', d.n_folds, `${d.model} · ${d.interval}`, ''),
    kpi('方向准确率', pct(d.dir_acc), `基准 ${pct(d.baseline_dir_acc)}`, cls(d.dir_acc - d.baseline_dir_acc)),
    kpi('MAE', fmt(d.mae, 5), `随机游走 ${fmt(d.baseline_mae, 5)}`, cls(d.skill)),
    kpi('Skill', pct(d.skill), d.skill > 0 ? '跑赢基准' : '跑输基准', skillCls),
    kpi('策略年化', d.strategy_ann == null ? '—' : pct(d.strategy_ann), `买入持有 ${d.buy_hold_ann == null ? '—' : pct(d.buy_hold_ann)}`, cls(d.strategy_ann - d.buy_hold_ann)),
    kpi('最大回撤', d.max_drawdown == null ? '—' : pct(d.max_drawdown), '', 'down'),
  ].join('');
  const folds = d.folds || [];
  const dates = folds.map(f => f.date);
  const c1 = chart('btPredChart'); if (c1) c1.setOption({
    backgroundColor: 'transparent', tooltip: { ...TIP, trigger: 'axis' },
    legend: { data: ['预测', '实际'], textStyle: { color: '#8B9BB0' }, top: 0 },
    grid: { left: 45, right: 16, top: 30, bottom: 30 }, xAxis: { type: 'category', data: dates, ...AXIS }, yAxis: { ...AXIS },
    series: [{ name: '预测', type: 'line', data: folds.map(f => f.pred_logret), symbol: 'none', lineStyle: { width: 1, color: '#3B82F6' } },
             { name: '实际', type: 'line', data: folds.map(f => f.actual_logret), symbol: 'none', lineStyle: { width: 1, color: '#F5A623' } }],
  }, true);
  // 累计净值
  let eq = 1, bh = 1; const eqArr = [], bhArr = [];
  folds.forEach(f => { bh *= Math.exp(f.actual_logret); eq *= (f.pred_logret > 0 ? Math.exp(f.actual_logret) : 1); eqArr.push(eq); bhArr.push(bh); });
  const c2 = chart('btEquityChart'); if (c2) c2.setOption({
    backgroundColor: 'transparent', tooltip: { ...TIP, trigger: 'axis' },
    legend: { data: ['策略', '买入持有'], textStyle: { color: '#8B9BB0' }, top: 0 },
    grid: { left: 45, right: 16, top: 30, bottom: 30 }, xAxis: { type: 'category', data: dates, ...AXIS }, yAxis: { ...AXIS },
    series: [{ name: '策略', type: 'line', data: eqArr, symbol: 'none', lineStyle: { width: 1.5, color: '#3B82F6' } },
             { name: '买入持有', type: 'line', data: bhArr, symbol: 'none', lineStyle: { width: 1.5, color: '#F5A623' } }],
  }, true);
  // 残差分布
  const resid = folds.map(f => f.actual_logret - f.pred_logret);
  const c3 = chart('btResidChart'); if (c3) c3.setOption({
    backgroundColor: 'transparent', tooltip: { ...TIP }, grid: { left: 40, right: 16, top: 16, bottom: 24 },
    xAxis: { type: 'value', ...AXIS }, yAxis: { ...AXIS },
    series: [{ type: 'histogram', data: resid, barWidth: '90%', itemStyle: { color: '#243140' } }],
  }, true);
}

/* AI 助手 */
async function loadAIStatus() {
  try {
    const d = await api('/api/ai/status'); $('#aiStatus').textContent = d.configured ? '已配置' : '未配置';
    $('#aiBase').value = d.base_url || ''; $('#aiModel').value = d.model || ''; $('#aiKey').value = ''; $('#aiTemp').value = 0.3;
    $('#aiHint').textContent = d.configured ? `已连接 ${d.host} · ${d.model}` : '支持 Ollama / LM Studio / vLLM / DeepSeek / OpenAI / 通义千问等任意 OpenAI 兼容端点。';
  } catch (e) { /* 忽略 */ }
}
async function loadAITemplates() {
  if (state._tplLoaded) return; state._tplLoaded = true;
  try {
    const d = await api('/api/ai/templates');
    $('#aiTemplates').innerHTML = d.templates.map(t => `<div class="tpl-item ${t.id === state.aiTpl ? 'active' : ''}" data-id="${t.id}"><b>${t.name}</b><span>${t.desc}</span></div>`).join('');
    $$('#aiTemplates .tpl-item').forEach(el => el.addEventListener('click', () => {
      $$('#aiTemplates .tpl-item').forEach(x => x.classList.remove('active'));
      el.classList.add('active'); state.aiTpl = el.dataset.id;
      $('#aiTplHint').textContent = `已选：${el.querySelector('b').textContent}`;
    }));
    $('#aiTplHint').textContent = `已选：${d.templates[0].name}`;
  } catch (e) { /* 忽略 */ }
}
function buildAIContext() {
  const q = state.lastQuote, f = state.lastForecast, b = state.lastBacktest;
  const ctx = { symbol: state.symbol, interval: state.interval };
  if (q) {
    ctx.last_close = q.last_close; ctx.ma5 = last(q.ma5); ctx.ma20 = last(q.ma20); ctx.ma60 = last(q.ma60);
    ctx.rsi14 = last(q.rsi14); ctx.macd_hist = last(q.macd_hist); ctx.boll_up = last(q.boll_up); ctx.boll_low = last(q.boll_low);
    const closes = q.close || []; const n = Math.min(10, closes.length); ctx.recent_pct = n > 1 ? ((closes[closes.length - 1] - closes[closes.length - n]) / closes[closes.length - n] * 100).toFixed(2) : '0';
    ctx.recent_klines = JSON.stringify(closes.slice(-10));
    ctx.vol_z = last(q.vol_z); ctx.drawdown = 0; ctx.atr14 = 0;
  }
  if (f) { ctx.direction = f.direction; ctx.point_logret = f.point_logret; ctx.q05_price = f.q05_price; ctx.q95_price = f.q95_price; ctx.interval_width_pct = f.interval_width_pct; }
  const bt = f?.backtest || b; if (bt) { ctx.dir_acc = (bt.dir_acc * 100).toFixed(1); ctx.mae = bt.mae; ctx.skill = bt.skill; ctx.baseline_dir = (bt.baseline_dir_acc * 100).toFixed(1); }
  if (b) { ctx.n_folds = b.n_folds; ctx.strategy_ann = b.strategy_ann; ctx.buy_hold_ann = b.buy_hold_ann; ctx.max_dd = b.max_drawdown; ctx.rmse = b.rmse; ctx.horizon = b.horizon; }
  return ctx;
}
const last = a => (a && a.length) ? a[a.length - 1] : null;
$('#aiSave').addEventListener('click', async () => {
  try { await post('/api/ai/config', { base_url: $('#aiBase').value, model: $('#aiModel').value, api_key: $('#aiKey').value, temperature: parseFloat($('#aiTemp').value) || 0.3 }); toast('配置已保存', 'ok'); loadAIStatus(); } catch (e) { toast(e.message, 'err'); }
});
$('#aiTest').addEventListener('click', async () => {
  $('#aiOutput').textContent = '测试中…'; try { const r = await post('/api/ai/test', {}); $('#aiOutput').textContent = r.ok ? `✓ 连接成功 · ${r.model} · ${r.latency_ms}ms` : `✗ ${r.error}`; toast(r.ok ? '连接成功' : '连接失败', r.ok ? 'ok' : 'err'); } catch (e) { toast(e.message, 'err'); }
});
$('#aiRun').addEventListener('click', async () => {
  const ctx = buildAIContext(); $('#aiOutput').textContent = `调用 AI（模板：${state.aiTpl}）…`;
  $('#sideStatus').textContent = 'AI 分析中…'; $('#statusDot').className = 'dot busy';
  try {
    const r = await post('/api/ai/chat', { template: state.aiTpl, context: ctx });
    if (r.error) { $('#aiOutput').textContent = `✗ ${r.error}`; toast(r.error, 'err'); }
    else { $('#aiOutput').textContent = r.content || '(空)'; if (r.latency_ms) $('#aiLatency').textContent = `${r.latency_ms}ms`; toast('AI 分析完成', 'ok'); }
  } catch (e) { $('#aiOutput').textContent = `✗ ${e.message}`; toast(e.message, 'err'); }
  finally { $('#sideStatus').textContent = '就绪'; $('#statusDot').className = 'dot ok'; }
});
// 委员会多智能体分析（借鉴 TradingAgents 多角色 + ai-hedge-fund 多风格）
$('#aiCommittee').addEventListener('click', async () => {
  const ctx = buildAIContext();
  $('#aiOutput').textContent = '委员会分析中（5 角色：技术/基本面/风险/交易员/投资经理，约 30-60 秒）…';
  $('#aiCommittee').disabled = true; $('#sideStatus').textContent = '委员会分析中…'; $('#statusDot').className = 'dot busy';
  try {
    const r = await post('/api/ai/committee', { context: ctx });
    if (r.error) { $('#aiOutput').textContent = `✗ ${r.error}`; toast(r.error, 'err'); }
    else {
      let out = '═══ 多智能体委员会分析 ═══\n\n';
      (r.roles || []).forEach(role => {
        out += `【${role.name}】\n${role.view}\n\n`;
      });
      out += `═══ 投资经理综合决策 ═══\n${r.manager}\n`;
      $('#aiOutput').textContent = out; toast('委员会分析完成', 'ok');
    }
  } catch (e) { $('#aiOutput').textContent = `✗ ${e.message}`; toast(e.message, 'err'); }
  finally { $('#aiCommittee').disabled = false; $('#sideStatus').textContent = '就绪'; $('#statusDot').className = 'dot ok'; }
});

async function refreshAll() { await loadQuote(); /* forecast/backtest 按需加载 */ }

/* 启动 */
(async function init() {
  // 显示全屏 loading，避免数据加载期间白屏卡顿
  const boot = document.createElement('div');
  boot.id = 'bootLoading'; boot.className = 'boot-loading';
  boot.innerHTML = '<div class="boot-spinner"></div><div class="boot-text">正在获取实时行情…</div>';
  document.body.appendChild(boot);
  try {
    await loadSymbols();
    await loadQuote();
    toast('FinPredict 已就绪 · 实时联网', 'ok');
  } catch (e) {
    /* loadQuote 内部已处理错误，此处不重复 */
  } finally {
    boot.remove();
  }
})();
