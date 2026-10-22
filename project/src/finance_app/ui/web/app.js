/* FIN Terminal — 前端逻辑 */
const $ = (s, el = document) => el.querySelector(s);
const $$ = (s, el = document) => [...el.querySelectorAll(s)];
const state = { overview: null, universe: [], charts: {}, loaded: {}, market: 'US', sector: 'real_estate',
  news: [], newsRegion: 'ALL', newsOnlyAnalyzed: false, newsImpact: null, llmStatus: null, proposal: null };

const api = async (path) => {
  const r = await fetch(path);
  if (!r.ok) throw new Error(`${r.status} ${await r.text()}`);
  return r.json();
};
const post = async (path, body = {}) => {
  const r = await fetch(path, { method: 'POST', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify(body) });
  const data = await r.json().catch(() => ({}));
  if (!r.ok) throw new Error(data.error || `${r.status}`);
  return data;
};
const fmtNum = (v, d = 2) => (v == null || Number.isNaN(v)) ? '—' : Number(v).toLocaleString('en-US', { minimumFractionDigits: d, maximumFractionDigits: d });
const fmtPct = (v, d = 2) => (v == null || Number.isNaN(v)) ? '—' : `${(v * 100).toFixed(d)}%`;
const fmtSigned = (v, d = 2) => (v == null || Number.isNaN(v)) ? '—' : `${v > 0 ? '+' : ''}${(v * 100).toFixed(d)}%`;
const cls = (v) => v == null ? 'flat' : v > 0 ? 'up' : v < 0 ? 'down' : 'flat';
const esc = (s) => String(s ?? '').replace(/[&<>"']/g, c => ({ '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;', "'": '&#39;' }[c]));
// 校验 URL scheme：只允许 http/https，防御 javascript: 伪协议注入（新闻来自外部不可信 RSS）
const safeUrl = (u) => { const url = String(u ?? '').trim(); return /^https?:\/\//i.test(url) ? esc(url) : ''; };

const AXIS = {
  axisLine: { lineStyle: { color: '#263240' } },
  axisLabel: { color: '#6D7C90', fontSize: 10, fontFamily: 'Consolas, monospace' },
  splitLine: { lineStyle: { color: '#151E29' } },
  axisTick: { show: false },
};
const TOOLTIP = {
  backgroundColor: '#0D131A', borderColor: '#2A3A4E', borderWidth: 1,
  textStyle: { color: '#E8EDF4', fontSize: 11 },
  extraCssText: 'box-shadow:0 8px 24px rgba(0,0,0,.4);border-radius:6px;',
};
const GRID = { left: 48, right: 18, top: 26, bottom: 26 };

function chart(id) {
  if (state.charts[id]) return state.charts[id];
  const el = document.getElementById(id);
  if (!el) return null;
  const c = echarts.init(el, null, { renderer: 'canvas' });
  state.charts[id] = c;
  return c;
}
window.addEventListener('resize', () => Object.values(state.charts).forEach(c => c && c.resize()));

/* ---------------- 导航 ---------------- */
function switchPage(page) {
  $$('.nav-item').forEach(b => b.classList.toggle('active', b.dataset.page === page));
  $$('.page').forEach(p => p.classList.toggle('active', p.id === `page-${page}`));
  const titles = {
    overview: ['总览', '全球市场脉搏 · 多市场 / 多板块'],
    markets: ['市场', '美股 · 港股 · A股'],
    sectors: ['板块', '房地产 · 能源 · 科技 · 金融'],
    stock: ['个股', 'K 线 · 指标 · 风险'],
    forecast: ['预测实验室', '严格样本外滚动验证'],
    news: ['新闻事件', '官方源 · 事件系数 · 综合预测'],
    model: ['模型接入', 'LLM · 自主优化 · 前向验证'],
    audit: ['算法审查', '历史检验 · 区间校准 · 开源项目合规'],
    analysts: ['券商观点', '公开报道口径 · 附来源'],
    quality: ['数据质量', '覆盖 · 缺失 · 异常'],
  };
  const [t, s] = titles[page] || ['', ''];
  $('#pageTitle').textContent = t;
  $('#pageSub').textContent = s;
  if (!state.loaded[page]) {
    state.loaded[page] = true;
    try {
      ({ markets: renderMarkets, sectors: renderSectors, stock: initStock, forecast: initForecast,
         news: renderNews, model: renderModel, audit: renderAudit, analysts: renderAnalysts,
         quality: renderQuality }[page] || (() => {}))();
    } catch (exc) {
      // 页面级错误兜底：任一渲染失败显示错误占位，而非空白页面
      console.error(`[switchPage:${page}]`, exc);
      const err = document.querySelector(`#page-${page} .page-error`) || (() => {
        const d = document.createElement('div'); d.className = 'page-error empty-state';
        document.querySelector(`#page-${page}`).prepend(d); return d;
      })();
      err.textContent = `该页面加载失败：${exc.message || exc}。可刷新重试，或查看控制台。`;
      err.style.display = 'block';
    }
  }
  setTimeout(() => Object.values(state.charts).forEach(c => c && c.resize()), 30);
}
$$('.nav-item').forEach(b => b.addEventListener('click', () => switchPage(b.dataset.page)));

/* ---------------- 总览 ---------------- */
async function renderOverview() {
  const d = await api('/api/overview');
  state.overview = d;
  $('#asOf').textContent = d.as_of || '—';
  $('#sideAsOf').textContent = `截至 ${d.as_of || '—'}`;
  $('#sideStatus').textContent = '数据已连接';
  $('#statusDot').className = 'dot ok';
  $('#loading').classList.add('hidden');

  // 指数卡片
  $('#indexCards').innerHTML = d.indices.map(x => `
    <div class="kpi">
      <div class="k-name"><span>${esc(x.name_cn)}</span><em>${esc(x.symbol)}</em></div>
      <div class="k-val">${fmtNum(x.last, 2)}</div>
      <div class="k-sub">
        <span>1月 <b class="${cls(x.ret_1m)}">${fmtSigned(x.ret_1m)}</b></span>
        <span>YTD <b class="${cls(x.ret_ytd)}">${fmtSigned(x.ret_ytd)}</b></span>
        <span>1年 <b class="${cls(x.ret_1y)}">${fmtSigned(x.ret_1y)}</b></span>
      </div>
    </div>`).join('');

  // 板块热力图
  const sectors = d.sectors.filter(x => x.name_cn);
  const tree = sectors.map(x => ({
    name: x.name_cn, value: Math.abs((x.ret_1m || 0) * 100).toFixed(2),
    raw: (x.ret_1m || 0) * 100, sym: x.symbol,
  }));
  const cs = chart('sectorHeat');
  cs.setOption({
    tooltip: { ...TOOLTIP, formatter: p => `${p.name}<br/>1月：${p.data.raw > 0 ? '+' : ''}${p.data.raw.toFixed(2)}%<br/>${p.data.sym}` },
    series: [{
      type: 'treemap', roam: false, nodeClick: false, breadcrumb: { show: false },
      top: 2, left: 2, right: 2, bottom: 2, width: '100%', height: '100%',
      label: { show: true, formatter: p => `${p.name}\n${p.data.raw > 0 ? '+' : ''}${p.data.raw.toFixed(2)}%`, color: '#E8EDF4', fontSize: 11, lineHeight: 17 },
      itemStyle: { borderColor: '#0A0E13', borderWidth: 2, gapWidth: 2, borderRadius: 4 },
      data: tree.map(x => ({
        ...x, value: Math.max(x.value, 4),
        itemStyle: { color: x.raw > 0 ? `rgba(46,212,122,${0.18 + Math.min(Math.abs(x.raw) / 12, .55)})` : x.raw < 0 ? `rgba(255,92,92,${0.18 + Math.min(Math.abs(x.raw) / 12, .55)})` : '#1A2430' },
      })),
    }],
  });

  // 市场宽度
  const b = d.breadth || {};
  $('#breadthBox').innerHTML = ['US', 'HK', 'CN'].map(m => {
    const x = b[m] || {}; const v = x.above_ma50_pct; const v2 = x.above_ma200_pct;
    return `<div class="breadth-card"><div class="b-title"><span>${{ US: '美股', HK: '港股', CN: 'A股' }[m]}</span><span>${x.total || 0} 只</span></div>
      <div class="b-val ${v == null ? 'flat' : v >= .5 ? 'up' : 'down'}">${v == null ? '—' : (v * 100).toFixed(0) + '%'}</div>
      <div class="bar"><i class="${v != null && v < .5 ? 'down' : ''}" style="width:${v == null ? 0 : v * 100}%"></i></div>
      <div class="hint" style="margin-top:5px">MA200：${v2 == null ? '—' : (v2 * 100).toFixed(0) + '%'}</div></div>`;
  }).join('');

  // 相关性
  const c = d.correlation;
  chart('corrHeat').setOption({
    tooltip: { ...TOOLTIP, formatter: p => `${c.symbols[p.data[1]]} × ${c.symbols[p.data[0]]}<br/>相关系数：${p.data[2]}` },
    grid: { left: 76, right: 14, top: 10, bottom: 52 },
    xAxis: { type: 'category', data: c.symbols, ...AXIS, axisLabel: { ...AXIS.axisLabel, rotate: 30 } },
    yAxis: { type: 'category', data: c.symbols, ...AXIS },
    visualMap: { min: -1, max: 1, calculable: false, show: false, inRange: { color: ['#FF5C5C', '#1A2430', '#2ED47A'] } },
    series: [{ type: 'heatmap', data: c.matrix.flatMap((row, i) => row.map((v, j) => [j, i, v])), label: { show: true, fontSize: 9, color: '#C9D4E2', formatter: p => p.data[2]?.toFixed(2) }, itemStyle: { borderColor: '#0A0E13', borderWidth: 1 } }],
  });

  // 指数表
  $('#indexTable').innerHTML = `<thead><tr><th>指数</th><th>最新</th><th>1日</th><th>1月</th><th>3月</th><th>YTD</th><th>1年</th><th>年化波动</th></tr></thead><tbody>${d.indices.map(x => `
    <tr><td class="name">${esc(x.name_cn)}<span class="sym">${esc(x.symbol)}</span></td>
    <td>${fmtNum(x.last)}</td><td class="${cls(x.ret_1w)}">${fmtSigned(x.ret_1w)}</td>
    <td class="${cls(x.ret_1m)}">${fmtSigned(x.ret_1m)}</td><td class="${cls(x.ret_3m)}">${fmtSigned(x.ret_3m)}</td>
    <td class="${cls(x.ret_ytd)}">${fmtSigned(x.ret_ytd)}</td><td class="${cls(x.ret_1y)}">${fmtSigned(x.ret_1y)}</td>
    <td>${fmtPct(x.vol_1y)}</td></tr>`).join('')}</tbody>`;

  // 信号
  $('#signalList').innerHTML = d.signals.length ? d.signals.map(s => `
    <div class="signal"><span class="tag">${esc(s.type)}</span><span class="s-name">${esc(s.name_cn)}<span class="sym">${esc(s.symbol)}</span></span><span class="s-text">${esc(s.text)}</span></div>`).join('') : '<div class="hint">当前无显著技术信号</div>';
}

/* ---------------- 市场 ---------------- */
const MARKET_INDICES = { US: ['^GSPC', '^IXIC', '^DJI', '^RUT'], HK: ['^HSI', '^HSCE', '^HSTECH'], CN: ['000001.SS', '000300.SS', '399001.SZ', '399006.SZ'] };
const MARKET_NAMES = { US: '美股', HK: '港股', CN: 'A股' };

async function renderMarkets() {
  $$('#marketTabs .chip').forEach(b => b.addEventListener('click', () => {
    $$('#marketTabs .chip').forEach(x => x.classList.remove('active')); b.classList.add('active');
    state.market = b.dataset.market; drawMarket();
  }));
  await drawMarket();
}

async function drawMarket() {
  const m = state.market;
  const syms = MARKET_INDICES[m];
  const series = await Promise.all(syms.map(s => api(`/api/series?symbol=${encodeURIComponent(s)}&range=3y`)));
  const dates = series[0]?.dates || [];
  const palette = ['#5B8CFF', '#2ED47A', '#F5B84C', '#C084FC'];
  const lines = series.map((s, i) => {
    const base = s.close?.[0];
    return {
      name: s.info?.name_cn || s.symbol, type: 'line', showSymbol: false, smooth: false,
      lineStyle: { width: 1.6, color: palette[i] }, itemStyle: { color: palette[i] },
      data: (s.close || []).map(v => v == null || !base ? null : +((v / base - 1) * 100).toFixed(2)),
    };
  });
  chart('marketChart').setOption({
    tooltip: { ...TOOLTIP, trigger: 'axis', valueFormatter: v => v == null ? '—' : v.toFixed(2) + '%' },
    legend: { top: 0, right: 0, textStyle: { color: '#8B98AA', fontSize: 10 }, itemWidth: 12, itemHeight: 2 },
    grid: { ...GRID, top: 34 },
    xAxis: { type: 'category', data: dates, ...AXIS, axisLabel: { ...AXIS.axisLabel, hideOverlap: true } },
    yAxis: { type: 'value', ...AXIS, axisLabel: { ...AXIS.axisLabel, formatter: '{value}%' } },
    series: lines,
  }, true);
  $('#marketChartTitle').textContent = `${MARKET_NAMES[m]} 指数归一化`;
  $('#marketChartHint').textContent = '近 3 年 · 起点 = 0%';

  const uni = state.universe.length ? state.universe : (state.universe = await api('/api/universe'));
  const rows = uni.filter(x => x.market === m && !x.symbol.startsWith('^') && x.symbol !== 'DX-Y.NYB' && !x.stale);
  const perfRows = await Promise.all(rows.slice(0, 40).map(async x => {
    const s = await api(`/api/series?symbol=${encodeURIComponent(x.symbol)}&range=3m`);
    const c = s.close || []; const last = c[c.length - 1], first = c[0];
    const r1m = c.length > 21 ? last / c[c.length - 22] - 1 : null;
    const r3m = first ? last / first - 1 : null;
    return { ...x, r1m, r3m, last };
  }));
  perfRows.sort((a, b) => (b.r1m ?? -9) - (a.r1m ?? -9));
  $('#marketTable').innerHTML = `<thead><tr><th>标的</th><th>最新</th><th>1月</th><th>3月</th></tr></thead><tbody>${perfRows.map(x => `
    <tr><td class="name">${esc(x.name_cn)}<span class="sym">${esc(x.symbol)}</span></td><td>${fmtNum(x.last)}</td>
    <td class="${cls(x.r1m)}">${fmtSigned(x.r1m)}</td><td class="${cls(x.r3m)}">${fmtSigned(x.r3m)}</td></tr>`).join('')}</tbody>`;

  const br = state.overview?.breadth?.[m] || {};
  const avg = perfRows.reduce((a, x) => a + (x.r1m || 0), 0) / (perfRows.length || 1);
  $('#marketBreadthHint').textContent = `${perfRows.length} 只 · 平均 1 月 ${fmtSigned(avg)}`;
  $('#marketStats').innerHTML = [
    ['站上 MA50', br.above_ma50_pct == null ? '—' : (br.above_ma50_pct * 100).toFixed(0) + '%'],
    ['站上 MA200', br.above_ma200_pct == null ? '—' : (br.above_ma200_pct * 100).toFixed(0) + '%'],
    ['样本数', br.total ?? '—'],
    ['平均 1 月', fmtSigned(avg)],
    ['领涨', perfRows[0]?.name_cn || '—'],
    ['领跌', perfRows[perfRows.length - 1]?.name_cn || '—'],
  ].map(([k, v]) => `<div class="stat"><div class="s-label">${k}</div><div class="s-val">${esc(v)}</div></div>`).join('');
}

/* ---------------- 板块 ---------------- */
async function renderSectors() {
  $$('#sectorTabs .chip').forEach(b => b.addEventListener('click', () => {
    $$('#sectorTabs .chip').forEach(x => x.classList.remove('active')); b.classList.add('active');
    state.sector = b.dataset.sector; drawSector();
  }));
  await drawSector();
}

async function drawSector() {
  const g = state.sector;
  const d = await api(`/api/sector?group=${g}`);
  const s = await api(`/api/series?symbol=${encodeURIComponent(d.etf)}&range=2y`);
  const etf = d.etf; const perf = d.etf_perf || {};
  $('#sectorTitle').textContent = d.name_cn;
  $('#sectorHint').textContent = `${etf} · 近 2 年` + (d.excluded?.length ? ` · 停更剔除：${d.excluded.map(x => x.name_cn).join('、')}` : '');
  chart('sectorChart').setOption({
    tooltip: { ...TOOLTIP, trigger: 'axis' },
    legend: { top: 0, right: 0, textStyle: { color: '#8B98AA', fontSize: 10 }, itemWidth: 12, itemHeight: 2 },
    grid: { ...GRID, top: 34 },
    xAxis: { type: 'category', data: s.dates, ...AXIS, axisLabel: { ...AXIS.axisLabel, hideOverlap: true } },
    yAxis: { type: 'value', scale: true, ...AXIS },
    series: [
      { name: '收盘', type: 'line', data: s.close, showSymbol: false, lineStyle: { color: '#5B8CFF', width: 1.8 }, itemStyle: { color: '#5B8CFF' }, areaStyle: { color: 'rgba(91,140,255,.08)' } },
      { name: 'MA50', type: 'line', data: s.ma50, showSymbol: false, lineStyle: { color: '#F5B84C', width: 1, type: 'dashed' }, itemStyle: { color: '#F5B84C' } },
    ],
  }, true);

  chart('rsChart').setOption({
    tooltip: { ...TOOLTIP, trigger: 'axis', valueFormatter: v => v == null ? '—' : (v * 100).toFixed(2) + '%' },
    grid: { ...GRID, top: 14, bottom: 22 },
    xAxis: { type: 'category', data: d.rs_dates, ...AXIS, axisLabel: { show: false } },
    yAxis: { type: 'value', ...AXIS, axisLabel: { ...AXIS.axisLabel, formatter: v => (v * 100).toFixed(0) + '%' } },
    series: [{ type: 'line', data: d.relative_strength, showSymbol: false, lineStyle: { color: '#2ED47A', width: 1.6 }, itemStyle: { color: '#2ED47A' }, areaStyle: { color: 'rgba(46,212,122,.08)' } }],
  }, true);

  $('#sectorStats').innerHTML = [
    ['1 月', fmtSigned(perf.ret_1m)], ['3 月', fmtSigned(perf.ret_3m)],
    ['YTD', fmtSigned(perf.ret_ytd)], ['1 年', fmtSigned(perf.ret_1y)],
    ['年化波动', fmtPct(perf.vol_1y)], ['最大回撤', fmtPct(perf.max_dd_1y)],
  ].map(([k, v]) => `<div class="stat"><div class="s-label">${k}</div><div class="s-val ${k.includes('月') || k === 'YTD' || k === '1 年' ? cls(parseFloat(v)) : ''}">${v}</div></div>`).join('');

  $('#sectorTable').innerHTML = `<thead><tr><th>标的</th><th>最新</th><th>1周</th><th>1月</th><th>3月</th><th>YTD</th><th>1年</th><th>RSI</th><th>MA50</th></tr></thead><tbody>${d.members.map(x => `
    <tr><td class="name">${esc(x.name_cn)}<span class="sym">${esc(x.symbol)}</span></td><td>${fmtNum(x.last)}</td>
    <td class="${cls(x.ret_1w)}">${fmtSigned(x.ret_1w)}</td><td class="${cls(x.ret_1m)}">${fmtSigned(x.ret_1m)}</td>
    <td class="${cls(x.ret_3m)}">${fmtSigned(x.ret_3m)}</td><td class="${cls(x.ret_ytd)}">${fmtSigned(x.ret_ytd)}</td>
    <td class="${cls(x.ret_1y)}">${fmtSigned(x.ret_1y)}</td><td>${x.rsi14 == null ? '—' : x.rsi14.toFixed(1)}</td>
    <td>${x.above_ma50 == null ? '—' : x.above_ma50 ? '<span class="up">上方</span>' : '<span class="down">下方</span>'}</td></tr>`).join('')}</tbody>`;
}

/* ---------------- 个股 ---------------- */
async function initStock() {
  const uni = state.universe.length ? state.universe : (state.universe = await api('/api/universe'));
  const sel = $('#stockSelect');
  sel.innerHTML = uni.map(x => `<option value="${esc(x.symbol)}">${esc(x.name_cn)} · ${esc(x.symbol)}${x.stale ? '（停更）' : ''}</option>`).join('');
  const saved = localStorage.getItem('stockSym');
  if (saved && uni.some(x => x.symbol === saved)) sel.value = saved;
  sel.addEventListener('change', () => { localStorage.setItem('stockSym', sel.value); drawStock(); });
  $('#stockRange').addEventListener('change', drawStock);
  await drawStock();
}

async function drawStock() {
  const sym = $('#stockSelect').value;
  const rng = $('#stockRange').value;
  const d = await api(`/api/series?symbol=${encodeURIComponent(sym)}&range=${rng}`);
  if (!d.dates) return;
  $('#stockName').textContent = d.info.name_cn;
  $('#stockMeta').textContent = `${d.info.symbol} · ${d.info.market} · ${d.info.start} — ${d.info.end}`;
  $('#stockAsOf').textContent = d.info.end;

  const k = d.dates.map((x, i) => [d.open[i], d.close[i], d.low[i], d.high[i]]);
  chart('stockChart').setOption({
    tooltip: { ...TOOLTIP, trigger: 'axis', axisPointer: { type: 'cross' } },
    legend: { top: 0, right: 0, textStyle: { color: '#8B98AA', fontSize: 10 }, itemWidth: 12, itemHeight: 2 },
    grid: { left: 52, right: 16, top: 32, bottom: 24 },
    xAxis: { type: 'category', data: d.dates, ...AXIS, axisLabel: { show: false } },
    yAxis: { type: 'value', scale: true, ...AXIS },
    dataZoom: [{ type: 'inside', start: 40, end: 100 }],
    series: [
      { name: 'K线', type: 'candlestick', data: k, itemStyle: { color: '#2ED47A', color0: '#FF5C5C', borderColor: '#2ED47A', borderColor0: '#FF5C5C' } },
      { name: 'MA20', type: 'line', data: d.ma20, showSymbol: false, lineStyle: { width: 1, color: '#5B8CFF' }, itemStyle: { color: '#5B8CFF' } },
      { name: 'MA50', type: 'line', data: d.ma50, showSymbol: false, lineStyle: { width: 1, color: '#F5B84C' }, itemStyle: { color: '#F5B84C' } },
      { name: 'MA200', type: 'line', data: d.ma200, showSymbol: false, lineStyle: { width: 1, color: '#C084FC' }, itemStyle: { color: '#C084FC' } },
      { name: 'BOLL上', type: 'line', data: d.boll_up, showSymbol: false, lineStyle: { width: .8, color: '#3A4A60', type: 'dashed' }, itemStyle: { color: '#3A4A60' } },
      { name: 'BOLL下', type: 'line', data: d.boll_low, showSymbol: false, lineStyle: { width: .8, color: '#3A4A60', type: 'dashed' }, itemStyle: { color: '#3A4A60' } },
    ],
  }, true);

  chart('volumeChart').setOption({
    tooltip: { ...TOOLTIP, trigger: 'axis' },
    grid: { left: 52, right: 16, top: 6, bottom: 18 },
    xAxis: { type: 'category', data: d.dates, ...AXIS, axisLabel: { show: false } },
    yAxis: { type: 'value', ...AXIS, axisLabel: { ...AXIS.axisLabel, formatter: v => v >= 1e8 ? (v / 1e8).toFixed(0) + '亿' : v >= 1e4 ? (v / 1e4).toFixed(0) + '万' : v } },
    series: [{ type: 'bar', data: d.volume, itemStyle: { color: p => d.close[p.dataIndex] >= d.open[p.dataIndex] ? 'rgba(46,212,122,.5)' : 'rgba(255,92,92,.5)' } }],
  }, true);

  const c = d.close; const last = c[c.length - 1];
  const ret = (n) => c.length > n ? last / c[c.length - 1 - n] - 1 : null;
  const rsi = d.rsi14?.[d.rsi14.length - 1];
  const ma50 = d.ma50?.[d.ma50.length - 1]; const ma200 = d.ma200?.[d.ma200.length - 1];
  $('#stockStats').innerHTML = [
    ['最新价', fmtNum(last)], ['1 日', fmtSigned(ret(1))], ['1 月', fmtSigned(ret(21))],
    ['3 月', fmtSigned(ret(63))], ['1 年', fmtSigned(ret(252))], ['RSI14', rsi == null ? '—' : rsi.toFixed(1)],
    ['MA50', ma50 == null ? '—' : (last > ma50 ? '上方' : '下方')], ['MA200', ma200 == null ? '—' : (last > ma200 ? '上方' : '下方')],
    ['年化波动', fmtPct(d.vol20?.[d.vol20.length - 1])], ['当前回撤', fmtPct(d.dd?.[d.dd.length - 1])],
  ].map(([k, v]) => `<div class="row"><span>${k}</span><b class="${k.includes('日') || k.includes('月') || k === '1 年' ? cls(parseFloat(v)) : ''}">${v}</b></div>`).join('');

  const periods = [['1月', ret(21)], ['3月', ret(63)], ['6月', ret(126)], ['1年', ret(252)]];
  chart('stockMomentum').setOption({
    tooltip: { ...TOOLTIP, valueFormatter: v => fmtSigned(v) },
    grid: { ...GRID, top: 12, bottom: 24 },
    xAxis: { type: 'category', data: periods.map(x => x[0]), ...AXIS },
    yAxis: { type: 'value', ...AXIS, axisLabel: { ...AXIS.axisLabel, formatter: v => (v * 100).toFixed(0) + '%' } },
    series: [{ type: 'bar', data: periods.map(x => ({ value: x[1], itemStyle: { color: (x[1] || 0) >= 0 ? '#2ED47A' : '#FF5C5C', borderRadius: [3, 3, 0, 0] } })), barWidth: 26 }],
  }, true);

  chart('indicatorChart').setOption({
    tooltip: { ...TOOLTIP, trigger: 'axis' },
    legend: { top: 0, right: 0, textStyle: { color: '#8B98AA', fontSize: 10 }, itemWidth: 12, itemHeight: 2 },
    grid: [{ left: 52, right: 16, top: 28, height: '38%' }, { left: 52, right: 16, top: '62%', height: '26%' }],
    xAxis: [
      { type: 'category', data: d.dates, ...AXIS, axisLabel: { show: false }, gridIndex: 0 },
      { type: 'category', data: d.dates, ...AXIS, axisLabel: { show: false }, gridIndex: 1 },
    ],
    yAxis: [
      { type: 'value', ...AXIS, min: 0, max: 100, gridIndex: 0 },
      { type: 'value', ...AXIS, gridIndex: 1 },
    ],
    series: [
      { name: 'RSI14', type: 'line', data: d.rsi14, showSymbol: false, xAxisIndex: 0, yAxisIndex: 0, lineStyle: { color: '#F5B84C', width: 1.4 }, itemStyle: { color: '#F5B84C' }, markLine: { silent: true, symbol: 'none', lineStyle: { color: '#3A4A60', type: 'dashed' }, data: [{ yAxis: 70 }, { yAxis: 30 }] } },
      { name: 'MACD', type: 'line', data: d.macd, showSymbol: false, xAxisIndex: 1, yAxisIndex: 1, lineStyle: { color: '#5B8CFF', width: 1.2 }, itemStyle: { color: '#5B8CFF' } },
      { name: 'Signal', type: 'line', data: d.macd_signal, showSymbol: false, xAxisIndex: 1, yAxisIndex: 1, lineStyle: { color: '#C084FC', width: 1 }, itemStyle: { color: '#C084FC' } },
      { name: 'Hist', type: 'bar', data: d.macd_hist, xAxisIndex: 1, yAxisIndex: 1, itemStyle: { color: p => p.data >= 0 ? 'rgba(46,212,122,.55)' : 'rgba(255,92,92,.55)' } },
    ],
  }, true);
}

/* ---------------- 预测 ---------------- */
async function initForecast() {
  const uni = state.universe.length ? state.universe : (state.universe = await api('/api/universe'));
  const fcUni = uni.filter(x => !x.stale);
  $('#fcSymbol').innerHTML = fcUni.map(x => `<option value="${esc(x.symbol)}">${esc(x.name_cn)} · ${esc(x.symbol)}</option>`).join('');
  $('#fcSymbol').value = '^GSPC';
  $('#fcRun').addEventListener('click', runForecast);
  $('#fcSymbol').addEventListener('change', runForecast);
  $('#fcHorizon').addEventListener('change', runForecast);
  $('#fcModel').addEventListener('change', runForecast);
}

async function runForecast() {
  const sym = $('#fcSymbol').value, h = $('#fcHorizon').value, m = $('#fcModel').value;
  const btn = $('#fcRun'); btn.disabled = true; btn.textContent = '计算中…';
  $('#fcEmpty').classList.remove('hidden'); $('#fcEmpty').textContent = '正在做扩展窗口滚动回测与残差检验…';
  $('#fcResult').classList.add('hidden');
  try {
    const d = await api(`/api/forecast?symbol=${encodeURIComponent(sym)}&horizon=${h}&model=${m}`);
    if (d.error) throw new Error(d.error);
    $('#fcEmpty').classList.add('hidden');
    $('#fcResult').classList.remove('hidden');
    const sign = d.point_logret >= 0 ? '+' : '';
    $('#fcKpis').innerHTML = [
      ['当前价', fmtNum(d.last_close), d.last_date],
      ['点预测', fmtNum(d.point_price), `${sign}${(d.point_logret * 100).toFixed(2)}%`],
      ['90% 区间', `${fmtNum(d.q05_price, 0)} – ${fmtNum(d.q95_price, 0)}`, '残差分位数'],
      ['方向准确率', `${(d.dir_acc * 100).toFixed(1)}%`, `始终看多 ${(d.baseline_dir_acc * 100).toFixed(1)}%`],
      ['样本外 MAE', `${(d.mae_logret * 100).toFixed(2)}%`, `基准 ${(d.baseline_mae * 100).toFixed(2)}%`],
      ['Skill vs RW', `${(d.skill_score * 100).toFixed(1)}%`, d.n_folds + ' 折'],
    ].map(([k, v, s]) => `<div class="kpi"><div class="k-name"><span>${k}</span></div><div class="k-val" style="font-size:20px">${v}</div><div class="k-sub">${esc(s)}</div></div>`).join('');

    $('#fcFoldsHint').textContent = `${d.n_folds} 折 · MAPE ${d.mape_price.toFixed(2)}% · DM p=${d.dm_pvalue == null ? '—' : d.dm_pvalue.toFixed(3)}`;
    const dates = d.folds.map(f => f.date);
    chart('fcWalkChart').setOption({
      tooltip: { ...TOOLTIP, trigger: 'axis' },
      legend: { top: 0, right: 0, textStyle: { color: '#8B98AA', fontSize: 10 }, itemWidth: 12, itemHeight: 2 },
      grid: { ...GRID, top: 32 },
      xAxis: { type: 'category', data: dates, ...AXIS, axisLabel: { ...AXIS.axisLabel, hideOverlap: true } },
      yAxis: { type: 'value', scale: true, ...AXIS },
      series: [
        { name: '实际', type: 'line', data: d.folds.map(f => +f.actual_price.toFixed(2)), showSymbol: false, lineStyle: { color: '#E8EDF4', width: 1.4 }, itemStyle: { color: '#E8EDF4' } },
        { name: '预测', type: 'line', data: d.folds.map(f => +f.pred_price.toFixed(2)), showSymbol: false, lineStyle: { color: '#5B8CFF', width: 1.4 }, itemStyle: { color: '#5B8CFF' } },
      ],
    }, true);

    const target = new Date(d.last_date); target.setDate(target.getDate() + d.horizon);
    const tdate = target.toISOString().slice(0, 10);
    const band = d.q95_price - d.q05_price;
    chart('fcFanChart').setOption({
      tooltip: { ...TOOLTIP, trigger: 'axis' },
      grid: { ...GRID, top: 20, bottom: 24 },
      xAxis: { type: 'category', data: [d.last_date, tdate], ...AXIS },
      yAxis: { type: 'value', scale: true, ...AXIS },
      series: [
        { name: 'q05', type: 'line', stack: 'band', data: [d.last_close, d.q05_price], symbol: 'none', lineStyle: { opacity: 0 }, areaStyle: { opacity: 0 }, silent: true },
        { name: 'band', type: 'line', stack: 'band', data: [0, band], symbol: 'none', lineStyle: { opacity: 0 }, areaStyle: { color: 'rgba(91,140,255,.18)' }, silent: true },
        { name: '中位', type: 'line', data: [d.last_close, d.q50_price], symbol: 'circle', symbolSize: 5, lineStyle: { color: '#5B8CFF', width: 2 }, itemStyle: { color: '#5B8CFF' } },
        { name: '点预测', type: 'line', data: [d.last_close, d.point_price], symbol: 'circle', symbolSize: 5, lineStyle: { color: '#2ED47A', width: 1.2, type: 'dashed' }, itemStyle: { color: '#2ED47A' } },
      ],
    }, true);
    const pct = (x) => `${x >= d.last_close ? '+' : ''}${((x / d.last_close - 1) * 100).toFixed(2)}%`;
    $('#fcScenario').textContent = `悲观 ${fmtNum(d.q05_price)} (${pct(d.q05_price)}) · 中位 ${fmtNum(d.q50_price)} (${pct(d.q50_price)}) · 乐观 ${fmtNum(d.q95_price)} (${pct(d.q95_price)})`;
    $('#fcNotes').innerHTML = d.notes.map(n => `<li>${esc(n)}</li>`).join('');
  } catch (e) {
    $('#fcEmpty').classList.remove('hidden');
    $('#fcEmpty').textContent = `计算失败：${e.message}`;
  } finally {
    btn.disabled = false; btn.textContent = '运行滚动回测';
  }
}

/* ---------------- 新闻事件 ---------------- */
const NEWS_REGION_NAMES = { ALL: '全部', US: '美国', HK: '香港', CN: '中国', EU: '欧洲', GLOBAL: '全球' };
const EVENT_NAMES = {
  monetary_policy: '货币政策', fiscal_policy: '财政政策', regulation: '监管', geopolitics: '地缘政治',
  trade: '贸易', tech: '科技', energy: '能源', real_estate: '房地产', labor: '就业',
  earnings: '财报', other: '其他',
};
const fmtTime = (s) => s ? String(s).slice(0, 16).replace('T', ' ') : '—';
let newsBound = false;
let modelBound = false;

async function renderNews() {
  const [d, imp, llm] = await Promise.all([
    api('/api/news?limit=120'), api('/api/news/impact?hours=48'), api('/api/llm/status'),
  ]);
  state.news = d.items || [];
  state.newsImpact = imp;
  state.llmStatus = llm;
  if (!state.universe.length) state.universe = await api('/api/universe');
  const st = d.stats || {};
  const officialPct = st.total ? Math.round((st.official / st.total) * 100) : null;
  $('#newsKpis').innerHTML = [
    ['今日官方新闻', st.today ?? '—', `总 ${st.total ?? 0} 条`],
    ['官方/多边占比', officialPct == null ? '—' : officialPct + '%', `${st.official ?? 0} / ${st.total ?? 0}`],
    ['已分析', `${st.analyzed ?? 0}`, `待处理 ${st.unanalyzed ?? 0}`],
    ['证据权重', (imp.global?.weight ?? 0).toFixed(2), `近 ${imp.lookback_hours ?? 48} 小时`],
    ['分析模式', (state.llmStatus?.configured ? 'LLM' : '规则'), state.llmStatus?.model || '未接入模型'],
    ['最新发布', fmtTime(st.latest), 'UTC'],
  ].map(([k, v, s]) => `<div class="kpi"><div class="k-name"><span>${k}</span></div><div class="k-val" style="font-size:19px">${esc(v)}</div><div class="k-sub">${esc(s)}</div></div>`).join('');
  $('#newsLLMStatus').textContent = llm.configured ? `模型：${llm.model}` : '模型：未配置（规则评分）';
  $('#newsLastSync').textContent = st.latest ? `最新 ${fmtTime(st.latest)}` : '—';
  $('#newsCountHint').textContent = `${state.news.length} / ${st.total ?? '—'} 条 · ${state.news.filter(x => x.analysis).length} 已分析`;
  drawNewsList();
  drawNewsImpact(imp);
  fillNewsSymbols();
  if (!newsBound) {
    newsBound = true;
    $$('#newsFilters [data-news-region]').forEach(b => b.addEventListener('click', () => {
      $$('#newsFilters [data-news-region]').forEach(x => x.classList.remove('active'));
      b.classList.add('active'); state.newsRegion = b.dataset.newsRegion; drawNewsList();
    }));
    $('#newsOnlyAnalyzed').addEventListener('click', () => {
      state.newsOnlyAnalyzed = !state.newsOnlyAnalyzed;
      $('#newsOnlyAnalyzed').classList.toggle('active', state.newsOnlyAnalyzed);
      drawNewsList();
    });
    $('#newsSync').addEventListener('click', syncNews);
    $('#newsAnalyze').addEventListener('click', () => analyzeNews(false));
    $('#newsReanalyze').addEventListener('click', () => analyzeNews(true));
    $('#marketSync').addEventListener('click', syncMarket);
    $('#npRun').addEventListener('click', runNewsPrediction);
  }
}

function drawNewsList() {
  const rows = state.news.filter(x => {
    if (state.newsRegion !== 'ALL') {
      const regions = x.analysis?.regions || [x.region];
      if (!regions.includes(state.newsRegion) && x.region !== state.newsRegion) return false;
    }
    if (state.newsOnlyAnalyzed && !x.analysis) return false;
    return true;
  });
  if (!rows.length) {
    $('#newsList').innerHTML = '<div class="empty-state">没有符合条件的新闻。先同步官方源，或放宽筛选。</div>';
    return;
  }
  rows.sort((a, b) => ((b.analysis?.relevance || 0) - (a.analysis?.relevance || 0)) || String(b.published_at).localeCompare(String(a.published_at)));
  $('#newsList').innerHTML = rows.map(x => {
    const a = x.analysis;
    const dir = a ? (a.direction > 0.05 ? '偏多' : a.direction < -0.05 ? '偏空' : '中性') : '未分析';
    const dirCls = a ? (a.direction > 0.05 ? 'dir-up' : a.direction < -0.05 ? 'dir-down' : 'dir-flat') : 'dir-flat';
    const sectors = (a?.sectors || []).map(s => `<span class="tag2">${esc(s)}</span>`).join('');
    const tier = x.source_tier || 'official';
    return `<article class="news-card">
      <div class="n-top"><div class="n-source"><span class="tag2 tier-${esc(tier)}">${esc(tier)}</span>${esc(x.source_name)}<span>·</span>${fmtTime(x.published_at)}</div>
      <span class="n-num">${x.date_estimated ? '日期估算' : ''}</span></div>
      <div class="n-title"><a href="${safeUrl(x.url)}" target="_blank" rel="noreferrer">${esc(x.title)}</a></div>
      ${x.summary ? `<div class="n-summary">${esc(x.summary)}</div>` : ''}
      <div class="n-meta"><div class="n-tags">
        <span class="tag2 ${dirCls}">${dir}</span>
        ${a ? `<span class="tag2">${esc(EVENT_NAMES[a.event_type] || a.event_type)}</span><span class="tag2">强度 ${(a.magnitude * 100).toFixed(0)}</span><span class="tag2">置信 ${(a.confidence * 100).toFixed(0)}</span><span class="tag2">相关 ${((a.relevance ?? 0) * 100).toFixed(0)}</span>` : '<span class="tag2">待分析</span>'}
        ${sectors}
      </div><span class="n-num">${a ? esc(a.method || '') : ''}</span></div>
    </article>`;
  }).join('');
}

function drawNewsImpact(imp) {
  const regions = imp.regions || {};
  const order = ['US', 'HK', 'CN', 'EU', 'UK', 'GLOBAL'];
  const bar = (label, b) => {
    const s = b?.score || 0; const w = b?.weight || 0;
    const width = Math.min(50, Math.abs(s) * 50);
    const color = s > 0.03 ? 'var(--up)' : s < -0.03 ? 'var(--down)' : 'var(--faint)';
    return `<div class="impact-row" title="score=${s} weight=${w} n=${b?.n || 0}">
      <span class="impact-label">${esc(label)}</span>
      <div class="impact-bar"><i class="impact-fill" style="width:${width}%;margin-left:${s < 0 ? 50 - width : 50}%;background:${color}"></i></div>
      <span class="impact-val">${s > 0 ? '+' : ''}${s.toFixed(2)}</span>
    </div>`;
  };
  const sectors = Object.entries(imp.sectors || {})
    .sort((a, b) => Math.abs((b[1].score || 0) * Math.sqrt(b[1].weight || 0)) - Math.abs((a[1].score || 0) * Math.sqrt(a[1].weight || 0)))
    .slice(0, 8);
  $('#impactHint').textContent = `近 ${imp.lookback_hours || 48} 小时 · ${imp.n || 0} 条独立事件`;
  $('#newsImpact').innerHTML = `<div class="impact-sep">区域</div>` +
    order.map(r => bar(NEWS_REGION_NAMES[r] || r, regions[r])).join('') +
    `<div class="impact-sep">板块（按证据强度）</div>` +
    (sectors.length ? sectors.map(([k, v]) => bar(k, v)).join('') : '<div class="hint">暂无板块映射</div>');
}

function fillNewsSymbols() {
  const sel = $('#npSymbol');
  if (!sel || sel.options.length) return;
  const uni = state.universe.filter(x => !x.stale);
  sel.innerHTML = uni.map(x => `<option value="${esc(x.symbol)}">${esc(x.name_cn)} · ${esc(x.symbol)}</option>`).join('');
  if (uni.some(x => x.symbol === '^GSPC')) sel.value = '^GSPC';
}

async function syncNews() {
  const btn = $('#newsSync');
  btn.disabled = true; btn.textContent = '同步中…';
  try {
    const d = await post('/api/news/sync');
    $('#newsLastSync').textContent = `同步完成：新增 ${d.new ?? 0} 条 · 成功源 ${d.sources_ok ?? 0}/${d.sources ?? 0}`;
    await renderNews();
  } catch (e) {
    $('#newsLastSync').textContent = `同步失败：${e.message}`;
  } finally {
    btn.disabled = false; btn.textContent = '同步官方新闻';
  }
}

async function analyzeNews(reanalyze = false) {
  const btn = reanalyze ? $('#newsReanalyze') : $('#newsAnalyze');
  const label = reanalyze ? '模型重分析' : '分析待处理';
  btn.disabled = true; btn.textContent = '分析中…';
  try {
    const d = await post('/api/news/analyze', { limit: reanalyze ? 8 : 10, use_llm: true, reanalyze });
    $('#newsLLMStatus').textContent = d.llm_configured
      ? `LLM 分析 ${d.llm} 条 · 规则 ${d.rule} 条 · 失败 ${d.failed} 条${d.reanalyze ? ' · 覆盖模式' : ''}`
      : `规则分析 ${d.rule} 条（未配置模型）`;
    await renderNews();
  } catch (e) {
    $('#newsLLMStatus').textContent = `分析失败：${e.message}`;
  } finally {
    btn.disabled = false; btn.textContent = label;
  }
}

async function syncMarket() {
  const btn = $('#marketSync');
  btn.disabled = true; btn.textContent = '行情同步中…';
  $('#marketSyncOut').textContent = '启动中…';
  try {
    await post('/api/market/sync');
    const timer = setInterval(async () => {
      try {
        const d = await api('/api/market/sync/status');
        $('#marketSyncOut').textContent = d.running ? `同步中… 开始于 ${fmtTime(d.started_at)}` : (d.ok ? '同步完成，正在刷新…' : '同步结束，部分步骤失败');
        if (!d.running) {
          clearInterval(timer);
          btn.disabled = false; btn.textContent = '同步行情';
          if (d.ok) setTimeout(() => location.reload(), 900);
        }
      } catch (e) {
        clearInterval(timer);
        btn.disabled = false; btn.textContent = '同步行情';
        $('#marketSyncOut').textContent = `状态读取失败：${e.message}`;
      }
    }, 5000);
  } catch (e) {
    btn.disabled = false; btn.textContent = '同步行情';
    $('#marketSyncOut').textContent = `启动失败：${e.message}`;
  }
}

async function runNewsPrediction() {
  const btn = $('#npRun');
  const sym = $('#npSymbol').value, h = $('#npHorizon').value;
  if (!sym) return;
  btn.disabled = true; btn.textContent = '计算中…';
  $('#npResult').className = 'empty-state';
  $('#npResult').textContent = '正在运行价格滚动回测并聚合官方新闻系数…';
  try {
    const d = await post('/api/news/predict', { symbol: sym, horizon: Number(h), model: 'ensemble' });
    if (d.error) throw new Error(d.error);
    const p = d.price, n = d.news, c = d.combined;
    const px = (lr) => p.last_close == null ? null : p.last_close * Math.exp(lr);
    const pct = (lr) => `${lr >= 0 ? '+' : ''}${(lr * 100).toFixed(2)}%`;
    const dirText = n.score > 0.05 ? '偏多' : n.score < -0.05 ? '偏空' : '中性';
    $('#npResult').className = 'fc-result';
    $('#npResult').innerHTML = `
      <div class="kpi-row">
        <div class="kpi"><div class="k-name"><span>当前价</span><em>${esc(p.last_date)}</em></div><div class="k-val">${fmtNum(p.last_close)}</div><div class="k-sub">价格先验 ${pct(p.point_logret)}</div></div>
        <div class="kpi"><div class="k-name"><span>新闻系数</span></div><div class="k-val ${n.score > 0 ? 'up' : n.score < 0 ? 'down' : ''}">${n.score > 0 ? '+' : ''}${n.score.toFixed(2)}</div><div class="k-sub">${dirText} · ${n.n} 条证据 · ${esc(n.region)}${n.sector ? ' / ' + esc(n.sector) : ''}</div></div>
        <div class="kpi"><div class="k-name"><span>综合预期</span></div><div class="k-val ${c.combined_logret > 0 ? 'up' : c.combined_logret < 0 ? 'down' : ''}">${pct(c.combined_logret)}</div><div class="k-sub">对应 ${fmtNum(px(c.combined_logret))}</div></div>
        <div class="kpi"><div class="k-name"><span>权重</span></div><div class="k-val" style="font-size:20px">${(c.news_weight * 100).toFixed(0)}% / ${(c.price_weight * 100).toFixed(0)}%</div><div class="k-sub">新闻 / 价格 · 置信 ${(c.confidence * 100).toFixed(0)}%</div></div>
      </div>
      <div class="stat-grid compact" style="margin-bottom:12px">
        <div class="stat"><div class="s-label">价格贡献</div><div class="s-val">${pct(c.price_contribution)}</div></div>
        <div class="stat"><div class="s-label">新闻贡献</div><div class="s-val">${pct(c.news_contribution)}</div></div>
        <div class="stat"><div class="s-label">90% 区间</div><div class="s-val" style="font-size:12px">${fmtNum(p.q05, 0)} – ${fmtNum(p.q95, 0)}</div></div>
        <div class="stat"><div class="s-label">价格模型 Skill</div><div class="s-val ${p.skill > 0 ? 'up' : 'down'}">${(p.skill * 100).toFixed(1)}%</div></div>
      </div>
      <div class="panel-subhead">证据链（官方源）</div>
      <div class="news-list" style="max-height:260px">${(n.impact?.top_events || []).slice(0, 5).map(e => `
        <div class="news-card"><div class="n-source">${esc(e.source_name)} · ${fmtTime(e.published_at)}</div>
        <div class="n-title"><a href="${esc(e.url)}" target="_blank" rel="noreferrer">${esc(e.title)}</a></div>
        <div class="n-meta"><span class="tag2 ${e.direction > 0 ? 'dir-up' : e.direction < 0 ? 'dir-down' : 'dir-flat'}">${e.direction > 0 ? '偏多' : e.direction < 0 ? '偏空' : '中性'}</span><span class="n-num">权重 ${e.weight}</span></div></div>`).join('') || '<div class="hint">暂无已分析事件</div>'}</div>
      <div class="panel-subhead">必须阅读</div><ul class="notes">${d.notes.map(x => `<li>${esc(x)}</li>`).join('')}</ul>`;
  } catch (e) {
    $('#npResult').className = 'empty-state';
    $('#npResult').textContent = `生成失败：${e.message}`;
  } finally {
    btn.disabled = false; btn.textContent = '生成综合预测';
  }
}

/* ---------------- 模型接入 ---------------- */
async function renderModel() {
  const [llm, opt, perf, src] = await Promise.all([
    api('/api/llm/status'), api('/api/optimizer/status'), api('/api/news/performance'), api('/api/news/sources'),
  ]);
  state.llmStatus = llm;
  $('#llmBase').value = llm.base_url || '';
  $('#llmModel').value = llm.model || '';
  $('#llmOut').textContent = llm.configured ? `已配置：${llm.model}` : '未配置；新闻分析将使用规则评分';
  const w = opt.weights || {};
  $('#optimizerStatus').innerHTML = [
    ['新闻总权重', (w.news_weight ?? 0).toFixed(3), '边界 0.05–0.35'],
    ['区域学习', Object.keys(w.region_learned || {}).length, JSON.stringify(w.region_learned || {})],
    ['领域学习', Object.keys(w.category_learned || {}).length, JSON.stringify(w.category_learned || {})],
    ['前向样本', perf.n ?? 0, '≥20 才更新'],
    ['变更记录', (opt.history || []).length, '最近 20 条'],
  ].map(([k, v, s]) => `<div class="stat"><div class="s-label">${k}</div><div class="s-val" style="font-size:14px">${esc(v)}</div><div class="hint">${esc(s)}</div></div>`).join('');
  $('#perfHint').textContent = perf.n ? `n=${perf.n} · 最近 ${fmtTime(perf.last)}` : '还没有已实现的前向预测';
  if (!perf.n) {
    $('#newsPerf').innerHTML = `<div class="hint">${esc(perf.note || '先做综合预测，等周期结束后再评估。')}</div>`;
  } else {
    $('#newsPerf').innerHTML = [
      ['综合方向命中', fmtPct(perf.hit_combined), `价格 ${fmtPct(perf.hit_price)}`],
      ['新闻方向命中', fmtPct(perf.hit_news), `Brier ${perf.brier_news?.toFixed(3)}`],
      ['综合 MAE', fmtPct(perf.mae_combined, 2), `价格 ${fmtPct(perf.mae_price, 2)}`],
      ['样本', perf.n, '前向影子'],
    ].map(([k, v, s]) => `<div class="stat"><div class="s-label">${k}</div><div class="s-val">${esc(v)}</div><div class="hint">${esc(s)}</div></div>`).join('');
  }
  const rows = perf.recent || [];
  $('#newsPredTable').innerHTML = rows.length ? `<thead><tr><th>时间</th><th>标的</th><th>周期</th><th>价格先验</th><th>新闻</th><th>综合</th><th>实际</th></tr></thead><tbody>${rows.map(r => `
    <tr><td class="name">${fmtTime(r.created_at)}</td><td>${esc(r.symbol)}</td><td>${r.horizon}日</td>
    <td class="${cls(r.price_logret)}">${fmtSigned(r.price_logret)}</td><td class="${cls(r.news_score)}">${r.news_score?.toFixed(2)}</td>
    <td class="${cls(r.combined_logret)}">${fmtSigned(r.combined_logret)}</td><td>${r.actual_logret == null ? '<span class="hint">待实现</span>' : `<span class="${cls(r.actual_logret)}">${fmtSigned(r.actual_logret)}</span>`}</td></tr>`).join('')}</tbody>` : '';
  $('#sourceHealth').innerHTML = `<thead><tr><th>官方源</th><th>状态</th><th>抓取</th><th>保留</th><th>耗时</th><th>错误</th></tr></thead><tbody>${(src.sources || []).map(s => `
    <tr><td class="name">${esc(s.name)}<span class="sym">${esc(s.source_id)}</span></td><td class="${s.ok ? 'up' : 'down'}">${s.ok ? '正常' : '失败'}</td>
    <td>${s.fetched ?? '—'}</td><td>${s.kept ?? '—'}</td><td>${s.elapsed_ms ?? '—'}ms</td>
    <td style="text-align:left;max-width:360px;white-space:normal"><span class="hint">${esc(s.error || '')}</span></td></tr>`).join('')}</tbody>`;
  if (!modelBound) {
    modelBound = true;
    $('#llmSave').addEventListener('click', async () => {
      try {
        const d = await post('/api/llm/config', { base_url: $('#llmBase').value.trim(), model: $('#llmModel').value.trim(), api_key: $('#llmKey').value });
        $('#llmKey').value = '';
        $('#llmOut').textContent = d.configured ? `已保存：${d.model}` : '已保存，但尚未配置完整';
      } catch (e) { $('#llmOut').textContent = `保存失败：${e.message}`; }
    });
    $('#llmTest').addEventListener('click', async () => {
      $('#llmOut').textContent = '测试中…';
      try {
        const d = await post('/api/llm/test');
        $('#llmOut').textContent = d.ok ? `连接成功 · ${d.latency_ms}ms · ${d.model}` : `失败：${d.error}`;
      } catch (e) { $('#llmOut').textContent = `失败：${e.message}`; }
    });
    $('#optimizerUpdate').addEventListener('click', async () => {
      try {
        const d = await post('/api/optimizer/update');
        $('#optimizerStatus').innerHTML = `<div class="hint">${esc(d.reason)} · 变更 ${(d.changes || []).length} 项</div>` + (d.changes || []).map(c => `<div class="stat"><div class="s-label">${esc(c.target)}</div><div class="s-val">${c.before} → ${c.after}</div><div class="hint">${esc(c.reason)}</div></div>`).join('');
      } catch (e) { $('#optimizerStatus').innerHTML = `<div class="hint">优化失败：${esc(e.message)}</div>`; }
    });
    $('#optimizerPropose').addEventListener('click', async () => {
      try {
        const d = await post('/api/optimizer/propose');
        state.proposal = d.proposal;
        $('#optimizerStatus').innerHTML = `<div class="hint">模型提议：新闻权重 ${d.proposal.news_weight}；区域 ${JSON.stringify(d.proposal.region_learned)}</div><div class="hint">${esc(d.proposal.rationale || '')}</div><button id="applyProposal" class="ghost-btn" style="margin-top:8px">应用提议（仍受边界限制）</button>`;
        $('#applyProposal').addEventListener('click', async () => {
          const r = await post('/api/optimizer/apply', { proposal: state.proposal });
          $('#optimizerStatus').innerHTML = `<div class="hint">已应用；新闻权重 ${r.after.news_weight}</div>`;
        });
      } catch (e) { $('#optimizerStatus').innerHTML = `<div class="hint">提议失败：${esc(e.message)}</div>`; }
    });
  }
}

/* ---------------- 算法审查 ---------------- */
async function renderAudit() {
  const [a, p] = await Promise.all([api('/api/audit'), api('/api/projects')]);
  if (a.error) {
    $('#auditVerdict').innerHTML = `<div class="verdict-card bad"><div class="v-label">审计数据缺失</div><div class="v-value">—</div><div class="v-desc">${esc(a.error)}</div></div>`;
    return;
  }
  const t = a.target || {};
  const histBest = ['ridge','hgb','rf','ensemble','logit','hgb_clf','ensemble_clf']
    .map(k => ({ k, ...(a.historical_1949?.models?.[k] || {}) }))
    .filter(x => x.dir_acc != null || x.accuracy != null)
    .sort((x, y) => (y.dir_acc ?? y.accuracy) - (x.dir_acc ?? x.accuracy))[0] || {};
  const modern = a.model_comparison_modern || {};
  const modernBest = Object.entries(modern).map(([k, v]) => ({ k, ...(v.overall || {}) }))
    .filter(x => x.dir_acc != null).sort((x, y) => y.dir_acc - x.dir_acc)[0] || {};
  const annual = a.annual_regression?.overall || {};
  const cov = t.interval_coverage_987;
  const covT = t.interval_coverage_987_targeted;
  const it = a.interval_targeted || {};
  const bestConf = a.best_confidence_slice || {};
  const rare = a.rare_events || {};
  const checks = a.leakage_checks || [];
  const pass = checks.filter(c => c.ok).length;
  const pct = (v, d = 1) => v == null || Number.isNaN(v) ? '—' : `${(v * 100).toFixed(d)}%`;

  $('#auditVerdict').innerHTML = `
    <div class="verdict-card bad">
      <div class="v-label">方向准确率目标 98.7% · 真实样本外</div>
      <div class="v-value down">不可达</div>
      <div class="v-desc">1949 留出最好 <b>${pct(histBest.dir_acc ?? histBest.accuracy)}</b>（${esc(histBest.k || '—')}，始终看多 ${pct(histBest.baseline_long)}）；1950–2026 年度 <b>${pct(annual.dir_acc)}</b>（始终看多 ${pct(annual.baseline_long)}）；2000–2026 现代最好 <b>${pct(modernBest.dir_acc)}</b>（${esc(modernBest.k || '—')}）。任何宣称 98.7% 的回测，先查未来函数与目标定义。</div>
    </div>
    <div class="verdict-card ${covT != null && covT >= 0.987 ? 'ok' : ''}">
      <div class="v-label">区间覆盖率 98.7% · 覆盖率定向校准</div>
      <div class="v-value ${covT != null && covT >= 0.987 ? 'up' : 'warn'}">${pct(covT ?? cov)}</div>
      <div class="v-desc">名义 98.7% 分位实测 ${pct(cov)}；用校准段+调参段选宽度倍数 <b>${it.multiplier ?? '—'}×</b>，留出段覆盖率 <b>${pct(it.coverage_eval)}</b>，宽度 ${pct(it.width_logret, 1)} 对数收益。覆盖率高只代表区间够宽，不代表方向准。</div>
    </div>`;

  $('#auditKpis').innerHTML = [
    ['1949 最佳方向', pct(histBest.dir_acc ?? histBest.accuracy), esc(histBest.k || '—')],
    ['1950–2026 年度', pct(annual.dir_acc), `始终看多 ${pct(annual.baseline_long)}`],
    ['2000–2026 现代', pct(modernBest.dir_acc), esc(modernBest.k || '—')],
    ['高置信切片', pct(bestConf.accuracy), `覆盖 ${pct(bestConf.coverage)} · 阈值 ${bestConf.threshold ?? '—'}`],
    ['3σ 尾部占比', pct(rare.h1?.tail_share, 2), `${rare.h1?.tail_count ?? '—'} / ${rare.h1?.n ?? '—'} 日`],
    ['泄漏检查', `${pass}/${checks.length}`, pass === checks.length ? '全部通过' : '存在未通过项'],
  ].map(([k, v, s]) => `<div class="kpi"><div class="k-name"><span>${k}</span></div><div class="k-val" style="font-size:22px">${v}</div><div class="k-sub">${esc(s)}</div></div>`).join('');

  // 1949
  const hm = a.historical_1949?.models || {};
  $('#audit1949').innerHTML = `<thead><tr><th>模型</th><th>类型</th><th>方向准确率</th><th>始终看多</th><th>AUC</th><th>MCC</th><th>Skill</th><th>样本</th></tr></thead><tbody>${Object.entries(hm).map(([k, v]) => {
    const acc = v.dir_acc ?? v.accuracy;
    return `<tr><td class="name">${esc(k)}</td><td>${v.type === 'classification' ? '分类' : '回归'}</td>
      <td class="${(acc ?? 0) > (v.baseline_long ?? 0) ? 'up' : 'down'}">${pct(acc)}</td>
      <td>${pct(v.baseline_long)}</td><td>${v.auc == null ? '—' : v.auc.toFixed(3)}</td>
      <td>${v.mcc == null ? '—' : v.mcc.toFixed(3)}</td><td>${v.skill == null ? '—' : pct(v.skill)}</td><td>${v.n ?? '—'}</td></tr>`;
  }).join('')}</tbody>`;

  // 年度滚动
  const byDecade = a.annual_regression?.by_decade || {};
  $('#auditWalk').innerHTML = `<thead><tr><th>十年</th><th>样本</th><th>方向准确率</th><th>始终看多</th><th>MAE</th></tr></thead><tbody>${Object.entries(byDecade).map(([k, v]) =>
    `<tr><td class="name">${esc(k)}s</td><td>${v.n ?? '—'}</td><td class="${(v.dir_acc ?? 0) > (v.baseline_long ?? 0) ? 'up' : 'down'}">${pct(v.dir_acc)}</td><td>${pct(v.baseline_long)}</td><td>${pct(v.mae, 2)}</td></tr>`).join('')}</tbody>`;

  // 区间
  const levels = a.interval_calibration?.levels || {};
  const levelRows = Object.entries(levels).map(([k, v]) => {
    const ok = Math.abs((v.empirical ?? 0) - (v.nominal ?? 0)) <= 0.02;
    return `<tr><td class="name">${pct(v.nominal)}</td><td class="${ok ? 'up' : 'warn'}">${pct(v.empirical)}</td><td>${pct(v.width_logret, 2)}</td><td><span class="badge ${ok ? 'ok' : 'warn'}">${ok ? '校准良好' : '偏差'}</span></td></tr>`;
  });
  if (a.interval_targeted) {
    const okT = (a.interval_targeted.coverage_eval ?? 0) >= 0.987;
    levelRows.push(`<tr><td class="name">98.7% 定向</td><td class="${okT ? 'up' : 'warn'}">${pct(a.interval_targeted.coverage_eval)}</td><td>${pct(a.interval_targeted.width_logret, 2)}</td><td><span class="badge ${okT ? 'ok' : 'warn'}">${okT ? '达到' : '未达到'}</span></td></tr>`);
  }
  $('#auditInterval').innerHTML = `<thead><tr><th>名义</th><th>实测</th><th>宽度</th><th>判定</th></tr></thead><tbody>${levelRows.join('')}</tbody>`;

  // 置信度
  const conf = a.confidence_curve || [];
  $('#auditConfidence').innerHTML = `<thead><tr><th>置信阈值</th><th>覆盖率</th><th>准确率</th><th>样本</th></tr></thead><tbody>${conf.map(c =>
    `<tr><td class="name">${c.threshold}</td><td>${pct(c.coverage)}</td><td class="${(c.accuracy ?? 0) > 0.5 ? 'up' : 'down'}">${pct(c.accuracy)}</td><td>${c.n ?? '—'}</td></tr>`).join('')}</tbody>`;

  // 现代模型
  $('#auditModels').innerHTML = `<thead><tr><th>模型</th><th>方向准确率</th><th>始终看多</th><th>Skill</th><th>MAE</th><th>DM p</th></tr></thead><tbody>${Object.entries(modern).map(([k, v]) => {
    const o = v.overall || {};
    return `<tr><td class="name">${esc(k)}</td><td class="${(o.dir_acc ?? 0) > (o.baseline_long ?? 0) ? 'up' : 'down'}">${pct(o.dir_acc)}</td><td>${pct(o.baseline_long)}</td><td class="${(o.skill ?? 0) > 0 ? 'up' : 'down'}">${pct(o.skill)}</td><td>${pct(o.mae, 2)}</td><td>${o.dm_p == null ? '—' : o.dm_p.toFixed(3)}</td></tr>`;
  }).join('')}</tbody>`;

  // 区域
  const reg = a.regional || {};
  $('#auditRegional').innerHTML = `<thead><tr><th>标的</th><th>区域</th><th>价格特征</th><th>跨资产</th><th>差值</th></tr></thead><tbody>${Object.entries(reg).map(([sym, v]) => {
    const pa = v.modes?.price?.overall?.dir_acc;
    const ca = v.modes?.context?.overall?.dir_acc;
    const d = (pa != null && ca != null) ? ca - pa : null;
    return `<tr><td class="name">${esc(v.name_cn || sym)}<span class="sym">${esc(sym)}</span></td><td>${esc(v.region || '')}</td><td>${pct(pa)}</td><td>${pct(ca)}</td><td class="${d == null ? '' : d > 0 ? 'up' : 'down'}">${d == null ? '—' : `${d > 0 ? '+' : ''}${(d * 100).toFixed(1)}pp`}</td></tr>`;
  }).join('')}</tbody>`;

  // 稀有事件
  const st = a.strategy_eval || {};
  $('#auditStrategy').innerHTML = [
    ['年化收益', pct(st.ann_return), `买入持有 ${pct(st.buy_hold_ann)}`],
    ['Sharpe', st.sharpe == null ? '—' : st.sharpe.toFixed(2), `波动 ${pct(st.ann_vol)}`],
    ['最大回撤', pct(st.max_drawdown), `暴露 ${pct(st.exposure)}`],
    ['年换手', st.turnover_per_year == null ? '—' : st.turnover_per_year.toFixed(1), `成本拖累 ${pct(st.cost_drag_ann, 2)}`],
    ['方向命中率', pct(st.hit_rate), `${st.n_periods ?? '—'} 期`],
    ['成本假设', `${st.cost_bps ?? '—'} bp`, '单边'],
  ].map(([k, v, s]) => `<div class="stat"><div class="s-label">${k}</div><div class="s-val">${v}</div><div class="hint">${esc(s)}</div></div>`).join('');

  const te = rare.tail_eval || {};
  $('#auditRare').innerHTML = [
    ['3σ 尾部（1日）', pct(rare.h1?.tail_share, 2), `${rare.h1?.tail_count ?? '—'} / ${rare.h1?.n ?? '—'}`],
    ['尾部平均波动', pct(rare.h1?.tail_mean_abs, 2), `常规 ${pct(rare.h1?.normal_mean_abs, 2)}`],
    ['尾部 MAE（5日）', pct(te.tail_mae, 2), `常规 ${pct(te.normal_mae, 2)}`],
    ['尾部方向准确率', pct(te.tail_dir_acc), `常规 ${pct(te.normal_dir_acc)}`],
  ].map(([k, v, s]) => `<div class="stat"><div class="s-label">${k}</div><div class="s-val">${v}</div><div class="hint">${esc(s)}</div></div>`).join('');

  const rw = a.rare_weight_experiment?.['2000_2026_ridge'] || {};
  $('#auditWeights').innerHTML = `<thead><tr><th>权重模式</th><th>方向准确率</th><th>Skill</th><th>MAE</th></tr></thead><tbody>${Object.entries(rw).map(([k, v]) =>
    `<tr><td class="name">${k === 'none' ? '不降权' : k === 'rare' ? '尾部降权' : '指数降权'}</td><td class="${(v.dir_acc ?? 0) > (v.baseline_long ?? 0) ? 'up' : 'down'}">${pct(v.dir_acc)}</td><td class="${(v.skill ?? 0) > 0 ? 'up' : 'down'}">${pct(v.skill)}</td><td>${pct(v.mae, 2)}</td></tr>`).join('')}</tbody>`;

  // 泄漏
  $('#auditLeakage').innerHTML = checks.map(c => `<li>${c.ok ? '<span class="badge ok">通过</span>' : '<span class="badge bad">未通过</span>'} ${esc(c.name)}：${esc(c.detail)}</li>`).join('') || '<li>暂无检查项</li>';

  // 项目
  const projects = p.projects || [];
  $('#auditProjects').innerHTML = `<thead><tr><th>项目</th><th>类别</th><th>Star</th><th>协议</th><th>维护</th><th>可靠性</th><th>我们是否采用</th><th>主要风险</th></tr></thead><tbody>${projects.map(x =>
    `<tr><td class="name" data-label="项目">${esc(x.name)}<span class="sym">${esc(x.repo)}</span></td>
    <td data-label="类别">${esc(x.category)}</td><td data-label="Star">${esc(x.stars)}</td>
    <td data-label="协议">${esc(x.license)}</td><td data-label="维护">${esc(x.maintenance)}</td>
    <td data-label="可靠性">${esc(x.reliability)}</td><td data-label="采用">${esc(x.adopted)}</td>
    <td data-label="风险">${esc(x.risk)}</td></tr>`).join('')}</tbody>`;
  $('#auditCompliance').innerHTML = (p.compliance || []).map(x => `<li>${esc(x)}</li>`).join('');
}

/* ---------------- 券商观点 ---------------- */
let analystData = null;
async function renderAnalysts() {
  if (!analystData) analystData = await api('/api/analysts');
  const views = analystData.views || [];
  const draw = (filter = 'all') => {
    const rows = views.filter(v => filter === 'all' || v.market === filter || (v.tags || []).includes(filter));
    $('#analystGrid').innerHTML = rows.length ? rows.map(v => `
      <div class="analyst-card">
        <div class="a-top"><div><div class="a-firm">${esc(v.firm)}</div><div class="hint">${esc(v.analyst || '')}</div></div><span class="a-region">${esc(v.market || '')} · ${esc(v.sector || '')}</span></div>
        <div class="a-target">${esc(v.target || '')}</div>
        <div class="a-view">${esc(v.view)}</div>
        <div class="a-meta"><span>${esc(v.date || '')}</span><a href="${esc(v.source || '#')}" target="_blank" rel="noreferrer">${esc(v.source_title || '来源')}</a></div>
      </div>`).join('') : '<div class="empty-state">该分类暂无收录</div>';
  };
  $$('#analystFilters .chip').forEach(b => b.addEventListener('click', () => {
    $$('#analystFilters .chip').forEach(x => x.classList.remove('active')); b.classList.add('active'); draw(b.dataset.filter);
  }));
  draw();
  if (analystData.meta?.note) $('.disclaimer').textContent = analystData.meta.note;
}

/* ---------------- 数据质量 ---------------- */
async function renderQuality() {
  const d = await api('/api/quality');
  const per = d.per_symbol || {};
  const ok = Object.values(per).filter(x => x.status === 'ok');
  $('#qualityKpis').innerHTML = [
    ['正常标的', d.symbols_ok ?? '—'], ['降级标的', d.symbols_degraded ?? 0], ['失败标的', d.symbols_failed ?? '—'],
    ['总行数', (d.rows_total ?? 0).toLocaleString()], ['最早日期', d.date_min || '—'], ['最新日期', d.date_max || '—'],
  ].map(([k, v]) => `<div class="kpi"><div class="k-name"><span>${k}</span></div><div class="k-val" style="font-size:19px">${esc(v)}</div></div>`).join('');
  $('#qualityTable').innerHTML = `<thead><tr><th>标的</th><th>状态</th><th>行数</th><th>起始</th><th>结束</th><th>缺失收盘</th><th>最大单日波动</th><th>标记</th></tr></thead><tbody>${Object.entries(per).sort((a, b) => (a[1].status === 'ok' ? 0 : 1) - (b[1].status === 'ok' ? 0 : 1)).map(([sym, x]) => {
    const st = x.status === 'ok' ? ['正常', 'up'] : x.status === 'degraded' ? ['降级', 'warn'] : ['失败', 'down'];
    return `<tr><td class="name">${esc(x.name_cn || sym)}<span class="sym">${esc(sym)}</span></td><td class="${st[1]}">${st[0]}</td>
    <td>${x.rows ?? '—'}</td><td>${x.start || '—'}</td><td>${x.end || '—'}</td><td>${x.null_close ?? '—'}</td>
    <td>${x.max_abs_daily_return == null ? '—' : (x.max_abs_daily_return * 100).toFixed(1) + '%'}</td>
    <td style="text-align:left"><span class="hint">${(x.flags || []).join(', ')}</span></td></tr>`;
  }).join('')}</tbody>`;
}

/* ---------------- 搜索 ---------------- */
$('#globalSearch').addEventListener('keydown', async (e) => {
  if (e.key !== 'Enter') return;
  const q = e.target.value.trim().toLowerCase();
  if (!q) return;
  const uni = state.universe.length ? state.universe : (state.universe = await api('/api/universe'));
  const hit = uni.find(x => x.symbol.toLowerCase() === q || x.name_cn.includes(q) || x.name_en.toLowerCase().includes(q));
  if (!hit) { e.target.value = ''; e.target.placeholder = '未找到，重试'; return; }
  if (!state.loaded.stock) { state.loaded.stock = true; await initStock(); }
  $('#stockSelect').value = hit.symbol;
  localStorage.setItem('stockSym', hit.symbol);
  switchPage('stock');
  await drawStock();
  e.target.value = '';
});

/* ---------------- 启动 ---------------- */
(async function boot() {
  try {
    await renderOverview();
    const uni = await api('/api/universe');
    state.universe = uni;
    $('#symbolList').innerHTML = uni.map(x => `<option value="${esc(x.symbol)}">${esc(x.name_cn)}</option>`).join('');
  } catch (e) {
    $('#loading').innerHTML = `<span style="border-top-color:#FF5C5C"></span>加载失败：${esc(e.message)}`;
  }
})();
