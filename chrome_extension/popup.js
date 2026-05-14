const DEFAULT_URL     = 'http://localhost:8081';
const DEFAULT_REFRESH = 2;

let appUrl      = DEFAULT_URL;
let refreshSec  = DEFAULT_REFRESH;
let refreshTimer = null;
let filterText  = '';
let allTraffic  = [];

// ── Init ────────────────────────────────────────────────────────────────────
document.addEventListener('DOMContentLoaded', async () => {
  await loadSettings();
  bindTabs();
  bindActions();
  document.getElementById('link-open-app').href = appUrl;
  checkStatus();
  startAutoRefresh();
});

// ── Settings ────────────────────────────────────────────────────────────────
async function loadSettings() {
  const s = await chrome.storage.local.get(['appUrl', 'proxyPort', 'refreshSec']);
  appUrl    = s.appUrl     || DEFAULT_URL;
  refreshSec = s.refreshSec || DEFAULT_REFRESH;
  document.getElementById('setting-url').value     = appUrl;
  document.getElementById('setting-port').value    = s.proxyPort || 8080;
  document.getElementById('setting-refresh').value = refreshSec;
}

async function saveSettings() {
  appUrl    = document.getElementById('setting-url').value.trim() || DEFAULT_URL;
  const port = parseInt(document.getElementById('setting-port').value) || 8080;
  refreshSec = parseInt(document.getElementById('setting-refresh').value) || DEFAULT_REFRESH;
  await chrome.storage.local.set({ appUrl, proxyPort: port, refreshSec });
  document.getElementById('link-open-app').href = appUrl;
  startAutoRefresh();
  checkStatus();
  notify('Settings saved ✓');
}

// ── Tabs ─────────────────────────────────────────────────────────────────────
function bindTabs() {
  document.querySelectorAll('.tab-btn').forEach(btn => {
    btn.addEventListener('click', () => {
      document.querySelectorAll('.tab-btn').forEach(b => b.classList.remove('active'));
      document.querySelectorAll('.panel').forEach(p => p.classList.remove('active'));
      btn.classList.add('active');
      document.getElementById(`panel-${btn.dataset.tab}`).classList.add('active');
      if (btn.dataset.tab === 'traffic') fetchTraffic();
    });
  });
}

// ── Actions ──────────────────────────────────────────────────────────────────
function bindActions() {
  document.getElementById('btn-refresh').addEventListener('click', fetchTraffic);
  document.getElementById('btn-clear').addEventListener('click', clearTraffic);
  document.getElementById('filter-input').addEventListener('input', e => {
    filterText = e.target.value.toLowerCase();
    renderTraffic();
  });
  document.getElementById('btn-start').addEventListener('click',  () => proxyAction('start'));
  document.getElementById('btn-stop').addEventListener('click',   () => proxyAction('stop'));
  document.getElementById('btn-pause').addEventListener('click',  () => proxyAction('pause'));
  document.getElementById('btn-open-monitor').addEventListener('click',  () => openApp());
  document.getElementById('btn-open-mappings').addEventListener('click', () => openApp());
  document.getElementById('btn-mock-page').addEventListener('click', mockCurrentPage);
  document.getElementById('btn-copy-url').addEventListener('click',  copyCurrentUrl);
  document.getElementById('btn-save-settings').addEventListener('click', saveSettings);
}

// ── API calls ────────────────────────────────────────────────────────────────
async function api(path, method = 'GET', body = null) {
  try {
    const opts = { method, headers: { 'Content-Type': 'application/json' } };
    if (body) opts.body = JSON.stringify(body);
    const res = await fetch(`${appUrl}/api${path}`, opts);
    return await res.json();
  } catch (e) {
    return null;
  }
}

async function checkStatus() {
  const dot  = document.getElementById('status-dot');
  const text = document.getElementById('status-text');
  const data = await api('/status');
  if (data) {
    dot.classList.add('online');
    text.textContent = data.proxy_running ? `Running · ${data.profile || ''}` : 'Idle';
    fetchTraffic();
  } else {
    dot.classList.remove('online');
    text.textContent = 'Offline';
  }
}

async function fetchTraffic() {
  const data = await api('/traffic');
  allTraffic = data?.entries || [];
  renderTraffic();
}

async function clearTraffic() {
  await api('/traffic', 'DELETE');
  allTraffic = [];
  renderTraffic();
}

async function proxyAction(action) {
  await api(`/proxy/${action}`, 'POST');
  setTimeout(checkStatus, 600);
}

// ── Render traffic ───────────────────────────────────────────────────────────
function renderTraffic() {
  const list  = document.getElementById('traffic-list');
  const empty = document.getElementById('empty-msg');
  const filtered = allTraffic.filter(e =>
    !filterText || (e.url || '').toLowerCase().includes(filterText)
  );

  if (!filtered.length) {
    list.innerHTML = '';
    list.appendChild(empty);
    empty.style.display = 'block';
    return;
  }
  empty.style.display = 'none';

  list.innerHTML = filtered.slice(-100).reverse().map(e => {
    const method  = e.method || 'GET';
    const code    = e.code   || '—';
    const codeNum = parseInt(code) || 0;
    const cc = codeNum < 300 ? 'c2xx' : codeNum < 400 ? 'c3xx' : codeNum < 500 ? 'c4xx' : 'c5xx';
    const path = (e.path || e.url || '').replace(/^https?:\/\/[^/]+/, '');
    return `
      <div class="traffic-item" title="${e.url || ''}">
        <span class="method-badge ${method}">${method}</span>
        <span class="code-badge ${cc}">${code}</span>
        <span class="traffic-url">${path}</span>
        ${e.mocked ? '<span class="mock-pill">MOCK</span>' : ''}
        ${e.duration ? `<span class="duration">${e.duration}</span>` : ''}
      </div>`;
  }).join('');

  list.querySelectorAll('.traffic-item').forEach(el => {
    el.addEventListener('click', openApp);
  });
}

// ── Helpers ──────────────────────────────────────────────────────────────────
function openApp() {
  chrome.tabs.create({ url: appUrl });
}

async function mockCurrentPage() {
  const [tab] = await chrome.tabs.query({ active: true, currentWindow: true });
  if (!tab?.url) return;
  try {
    const u = new URL(tab.url);
    const res = await api('/mappings/create_from_url', 'POST', {
      method: 'GET',
      path: u.pathname,
      query: Object.fromEntries(u.searchParams),
      host: u.hostname,
    });
    if
