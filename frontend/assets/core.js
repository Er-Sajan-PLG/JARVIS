/* JARVIS web console — shared state, API client, small utilities.
   One source of truth: `state` mirrors the server. Writes go through `api`
   and then re-read the affected slice, so the UI never invents state. */

export const state = {
  providers: [],        // [{key,name,status,has_key,model_count,models:[...]}]
  modelsLoaded: false,
  modelsLoading: false,
  modelsError: null,
  defaultModel: { provider: '', model: '' },
  apiKeys: {},          // {provider: {configured, source}}
  customModels: [],
  hiddenModels: [],
  theme: 'dark',
  memoryEnabled: true,
  conversations: [],
  currentSessionId: null,
  messages: [],
  selectedModel: { provider: '', id: '', name: '' },
  attachments: [],
  sending: false,
};

/* ── Utilities ──────────────────────────────────────────────────────────── */

export const $ = (sel, root = document) => root.querySelector(sel);
export const $$ = (sel, root = document) => Array.from(root.querySelectorAll(sel));

export function el(tag, attrs = {}, children = []) {
  const node = document.createElement(tag);
  for (const [k, v] of Object.entries(attrs)) {
    if (v === null || v === undefined || v === false) continue;
    if (k === 'class') node.className = v;
    else if (k === 'text') node.textContent = v;
    else if (k === 'html') node.innerHTML = v;
    else if (k.startsWith('on') && typeof v === 'function') node.addEventListener(k.slice(2), v);
    else node.setAttribute(k, v === true ? '' : String(v));
  }
  for (const c of [].concat(children)) {
    if (c === null || c === undefined || c === false) continue;
    node.appendChild(typeof c === 'string' ? document.createTextNode(c) : c);
  }
  return node;
}

export function escapeHtml(s) {
  return String(s ?? '').replace(/[&<>"']/g, (c) => (
    { '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;', "'": '&#39;' }[c]
  ));
}

export function formatBytes(n) {
  if (!n && n !== 0) return '—';
  if (n < 1024) return `${n} B`;
  if (n < 1048576) return `${(n / 1024).toFixed(1)} KB`;
  if (n < 1073741824) return `${(n / 1048576).toFixed(1)} MB`;
  return `${(n / 1073741824).toFixed(2)} GB`;
}

export function formatDate(ts) {
  if (!ts) return '—';
  const d = new Date(ts * 1000);
  const now = new Date();
  const sameDay = d.toDateString() === now.toDateString();
  if (sameDay) return `Today ${d.toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' })}`;
  const diffDays = Math.floor((now - d) / 86400000);
  if (diffDays === 1) return 'Yesterday';
  if (diffDays < 7) return `${diffDays} days ago`;
  return d.toLocaleDateString([], { month: 'short', day: 'numeric', year: 'numeric' });
}

export function isFree(model) {
  // The server decides this: it knows each provider's free tier and free
  // endpoints, which pricing data alone cannot express. Fall back to the
  // pricing heuristic only for entries the server did not annotate.
  if (model && typeof model.free === 'boolean') return model.free;
  const p = model?.pricing || {};
  const prompt = String(p.prompt ?? '');
  const completion = String(p.completion ?? '');
  if (!prompt && !completion) return false;
  return (prompt === '0' || prompt === '0.0') && (completion === '0' || completion === '0.0');
}

/* ── Theme & layout ─────────────────────────────────────────────────────── */

/* These live in core.js (a leaf module) rather than main.js so that any
   module can call them without importing the entry point — importing main.js
   from a module it initialises would be a cycle. */

export function applyTheme(mode) {
  const resolved = mode === 'system'
    ? (window.matchMedia('(prefers-color-scheme: light)').matches ? 'light' : 'dark')
    : mode;
  document.documentElement.dataset.theme = resolved;
  state.theme = resolved;
}

export function applySidebar(show) {
  $('#app').classList.toggle('sidebar-collapsed', !show);
}

export function contextLabel(model) {
  const n = model?.context_length;
  if (!n) return '';
  if (n >= 1000000) return `${Math.round(n / 1000000)}M ctx`;
  if (n >= 1000) return `${Math.round(n / 1000)}K ctx`;
  return `${n} ctx`;
}

/* ── Model capabilities ─────────────────────────────────────────────────────
   Tags let you narrow the picker by what a model can actually do. They come
   from two places, in order of trust:

   1. `model.capabilities` — an explicit list the server or a custom-model
      definition provided. Authoritative; used as-is.
   2. Inference from the model id/name/modalities, because most providers'
      /models payloads carry no capability metadata at all.

   Inferred tags are a best-effort label, not a guarantee — a model is only
   tagged vision when its id/modalities actually say so. */

export const ALL_CAPABILITIES = [
  { key: 'text', label: 'Text', icon: '📝' },
  { key: 'vision', label: 'Vision', icon: '👁' },
  { key: 'reasoning', label: 'Reasoning', icon: '🧠' },
  { key: 'code', label: 'Code', icon: '💻' },
  { key: 'tools', label: 'Tools', icon: '🔧' },
  { key: 'image-gen', label: 'Image gen', icon: '🎨' },
  { key: 'audio', label: 'Audio', icon: '🔊' },
];

// Substrings that reliably indicate a capability. Kept deliberately tight: a
// false Vision badge is worse than a missing one.
const CAPABILITY_HINTS = {
  vision: ['vision', 'vl-', '-vl', 'vlm', 'multimodal', 'llava', 'pixtral',
           'gemini-1.5', 'gemini-2', 'gemini-3', 'gpt-4o', 'gpt-4.1', 'gpt-5',
           'claude-3', 'claude-4', 'claude-sonnet', 'claude-opus', 'claude-haiku',
           'qwen-vl', 'qwen2-vl', 'qwen2.5-vl', 'internvl', 'florence', 'moondream'],
  reasoning: ['reason', 'thinking', 'think', 'o1', 'o3', 'o4-mini', 'r1',
              'deepseek-reasoner', 'qwq', 'magistral', 'nemotron', 'gpt-oss'],
  code: ['code', 'coder', 'codestral', 'starcoder', 'deepseek-coder', 'swe',
         'devstral', 'codellama', 'sonnet', 'opus'],
  tools: ['function', 'tool', 'agentic', 'gpt-4', 'gpt-5', 'claude', 'gemini', 'qwen'],
  'image-gen': ['dall-e', 'image', 'flux', 'stable-diffusion', 'sdxl', 'imagen', 'imagegen'],
  audio: ['whisper', 'audio', 'speech', 'tts', 'voice', 'parakeet'],
};

// Text is the default: anything that returns chat completions is a text model
// unless it is purely an image/audio/embedding endpoint.
const NON_TEXT_HINTS = ['embed', 'embedding', 'rerank', 'bge-', 'gte-', 'e5-'];

export function capabilitiesOf(model) {
  if (!model) return new Set();

  // 1. Explicit declaration wins outright.
  if (Array.isArray(model.capabilities) && model.capabilities.length) {
    return new Set(model.capabilities.map((c) => String(c).toLowerCase()));
  }

  // 2. Infer from everything textual the payload gave us.
  const modalities = Array.isArray(model.modalities)
    ? model.modalities.join(' ')
    : String(model.modalities || model.input_modalities || model.architecture || '');
  const hay = `${model.id || ''} ${model.name || ''} ${model.description || ''} ${modalities}`.toLowerCase();

  const caps = new Set();
  for (const [cap, needles] of Object.entries(CAPABILITY_HINTS)) {
    if (needles.some((n) => hay.includes(n))) caps.add(cap);
  }

  // Modalities are an explicit statement about input types.
  if (/image/.test(modalities.toLowerCase())) caps.add('vision');
  if (/audio|speech/.test(modalities.toLowerCase())) caps.add('audio');

  const looksNonText = NON_TEXT_HINTS.some((n) => hay.includes(n));
  if (!looksNonText) caps.add('text');
  else caps.delete('text');

  return caps;
}

export function matchesCapabilities(model, wanted) {
  if (!wanted || !wanted.size) return true;
  const have = capabilitiesOf(model);
  for (const c of wanted) if (have.has(c)) return true;
  return false;
}

const STATUS_COPY = {
  available: { dot: 'dot-ok', label: 'Available' },
  unavailable: { dot: 'dot-off', label: 'Unavailable' },
  no_key: { dot: 'dot-warn', label: 'No API key' },
  error: { dot: 'dot-err', label: 'Failed to fetch' },
  no_models: { dot: 'dot-warn', label: 'No models' },
};

export function statusInfo(status) {
  return STATUS_COPY[status] || { dot: 'dot-off', label: status || 'Unknown' };
}

/* ── Toasts ─────────────────────────────────────────────────────────────── */

export function toast(message, kind = 'ok') {
  const host = $('#toasts');
  if (!host) return;
  const node = el('div', { class: `toast toast-${kind}`, role: 'status', text: message });
  host.appendChild(node);
  setTimeout(() => {
    node.style.opacity = '0';
    setTimeout(() => node.remove(), 200);
  }, kind === 'err' ? 6000 : 2800);
}

/* ── API client ─────────────────────────────────────────────────────────── */

// Agentic providers (the local AGY CLI in particular) take 30-45s for a
// one-word reply, so chat gets a generous ceiling. Without a timeout at all,
// a hung provider is indistinguishable from a slow one and the reply never
// arrives. `onProgress` lets a caller show elapsed time for long waits.
export const CHAT_TIMEOUT_MS = 180000;

// The console API enforces JARVIS_API_KEY. A browser cannot read the server's
// environment, so the operator's key is captured once (see the Settings entry)
// and replayed on every request. localStorage is per-origin and the origin is
// the tailnet host, so the key never leaves a device the operator unlocked.
const API_KEY_STORAGE = 'jarvis.apiKey';

export function getApiKey() {
  try { return localStorage.getItem(API_KEY_STORAGE) || ''; } catch { return ''; }
}

export function setApiKey(key) {
  try {
    if (key) localStorage.setItem(API_KEY_STORAGE, key);
    else localStorage.removeItem(API_KEY_STORAGE);
  } catch { /* private mode: the session still works while the tab lives */ }
}

export function hasApiKey() {
  return Boolean(getApiKey());
}

// ── Server base (APK mode) ─────────────────────────────────────────────
// The web console and the PWA call the same origin they were served from, so
// relative `/api/...` paths just work. Inside the Capacitor APK the WebView
// origin is `capacitor://localhost`, which has no backend — the operator sets
// the JARVIS server URL once (Settings → Access) and every API path is
// resolved against it. Empty means same-origin (web/PWA behaviour).
const SERVER_URL_STORAGE = 'jarvis.serverUrl';

export function getServerUrl() {
  try { return (localStorage.getItem(SERVER_URL_STORAGE) || '').replace(/\/+$/, ''); } catch { return ''; }
}

export function setServerUrl(url) {
  try {
    const clean = (url || '').trim().replace(/\/+$/, '');
    if (clean) localStorage.setItem(SERVER_URL_STORAGE, clean);
    else localStorage.removeItem(SERVER_URL_STORAGE);
  } catch { /* private mode: same-origin requests still work while the tab lives */ }
}

export function apiUrl(path) {
  const base = getServerUrl();
  if (!base || !path.startsWith('/api')) return path;
  return base + path;
}

/* ── Self-healing server resolution ─────────────────────────────────────
   A hardcoded server URL dies the moment DHCP reassigns the host or the
   phone switches networks. Instead the app probes candidates and latches
   onto the first one answering /api/v1/health:
     1. the stored URL (explicit operator choice wins),
     2. baked candidates from server-candidates.json (tailnet name, LAN IP
        snapshot at build time — same-origin fetch, never blocked),
     3. same-origin (web/PWA: the page IS the server).
   The winner is persisted, so the next boot tries it first. Total silence
   on failure is what made every outage look like "nothing happens", so the
   probe result is always reported back to the caller. */
async function probeHealth(base, timeoutMs = 2500) {
  const url = base ? base + '/api/v1/health' : '/api/v1/health';
  const controller = new AbortController();
  const timer = setTimeout(() => controller.abort(), timeoutMs);
  try {
    const res = await fetch(url, { signal: controller.signal });
    if (!res.ok) return false;
    const data = await res.json().catch(() => null);
    return !!(data && data.status === 'healthy');
  } catch {
    return false;
  } finally {
    clearTimeout(timer);
  }
}

async function bakedCandidates() {
  // Relative path: <origin>/static/... on web, capacitor://localhost/static
  // in the APK (the file is bundled). Same file both places.
  try {
    const res = await fetch('static/server-candidates.json', { cache: 'no-store' });
    if (!res.ok) return [];
    const data = await res.json().catch(() => null);
    return Array.isArray(data) ? data.filter((u) => typeof u === 'string') : [];
  } catch {
    return [];
  }
}

export async function ensureServer() {
  const tried = [];
  const stored = getServerUrl();
  // Same-origin first: instant on web/PWA, fails fast in the APK (nothing
  // listens on the WebView origin). Then the stored URL, then baked
  // fallbacks (tailnet name, LAN snapshot).
  const candidates = [''];
  if (stored) candidates.push(stored);
  for (const c of await bakedCandidates()) {
    if (!candidates.includes(c)) candidates.push(c);
  }

  for (const base of candidates) {
    tried.push(base || '(this origin)');
    if (await probeHealth(base)) {
      if (base) {
        setServerUrl(base);
      } else {
        // Same-origin wins: drop any stale stored URL so a dead tunnel
        // address can never shadow the working origin.
        try {
          localStorage.removeItem(SERVER_URL_STORAGE);
        } catch {
          /* ignore */
        }
      }
      return { ok: true, base, tried };
    }
  }
  return { ok: false, base: stored, tried };
}

async function request(path, options = {}) {
  const { timeoutMs = 30000, onProgress, ...init } = options;
  const controller = new AbortController();
  const timer = timeoutMs ? setTimeout(() => controller.abort(), timeoutMs) : null;
  const started = Date.now();
  const ticker = onProgress
    ? setInterval(() => onProgress(Date.now() - started), 1000)
    : null;

  const key = getApiKey();
  const headers = { 'Content-Type': 'application/json', ...(init.headers || {}) };
  if (key) headers.Authorization = `Bearer ${key}`;

  try {
    const res = await fetch(apiUrl(path), {
      ...init,
      headers,
      signal: controller.signal,
    });
    const text = await res.text();
    let data = null;
    try { data = text ? JSON.parse(text) : null; } catch { data = { raw: text }; }
    if (!res.ok) {
      // A 401 with no stored key is a setup problem, not a failure -- say so,
      // instead of showing the raw "Unauthorized" to someone who has not yet
      // been told a key is needed.
      if (res.status === 401) {
        throw new Error(
          key
            ? 'JARVIS rejected that API key. Re-enter it in Settings → Access.'
            : 'JARVIS requires an API key. Add it in Settings → Access.'
        );
      }
      const detail = data?.detail || data?.error || `HTTP ${res.status}`;
      throw new Error(typeof detail === 'string' ? detail : JSON.stringify(detail));
    }
    return data;
  } catch (err) {
    if (err.name === 'AbortError') {
      const secs = Math.round((Date.now() - started) / 1000);
      throw new Error(
        `No response after ${secs}s. The provider may be slow or unreachable — try another model.`
      );
    }
    throw err;
  } finally {
    if (timer) clearTimeout(timer);
    if (ticker) clearInterval(ticker);
  }
}

export const api = {
  models: (refresh = false) => request(`/api/models${refresh ? '?refresh=true' : ''}`),

  getDefault: () => request('/api/settings/default'),
  setDefault: (provider, model) =>
    request('/api/settings/default', { method: 'POST', body: JSON.stringify({ provider, model }) }),

  listCustomProviders: () => request('/api/settings/providers'),
  addCustomProvider: (payload) =>
    request('/api/settings/providers', { method: 'POST', body: JSON.stringify(payload) }),
  addProvider: (payload) =>
    request('/api/settings/providers', { method: 'POST', body: JSON.stringify(payload) }),
  deleteCustomProvider: (key) =>
    request(`/api/settings/providers/${encodeURIComponent(key)}`, { method: 'DELETE' }),
  fetchProviderModels: (baseUrl, apiKey = '') =>
    request('/api/settings/providers/fetch-models', {
      method: 'POST',
      body: JSON.stringify({ base_url: baseUrl, api_key: apiKey }),
    }),

  listCustomModels: () => request('/api/settings/models'),
  addCustomModel: (payload) =>
    request('/api/settings/models', { method: 'POST', body: JSON.stringify(payload) }),
  deleteCustomModel: (provider, id) =>
    request(`/api/settings/models/${encodeURIComponent(provider)}/${encodeURIComponent(id)}`, { method: 'DELETE' }),
  hideModel: (provider, id) =>
    request('/api/settings/models/hide', { method: 'POST', body: JSON.stringify({ provider, id }) }),

  getApiKeys: () => request('/api/settings/api-keys'),
  saveApiKey: (provider, key) =>
    request('/api/settings/api-keys', { method: 'POST', body: JSON.stringify({ provider, key }) }),
  deleteApiKey: (provider) =>
    request(`/api/settings/api-keys/${encodeURIComponent(provider)}`, { method: 'DELETE' }),

  chat: (payload, opts = {}) =>
    request('/api/chat', {
      method: 'POST',
      body: JSON.stringify(payload),
      timeoutMs: CHAT_TIMEOUT_MS,
      ...opts,
    }),

  files: (q = '', kind = '') => {
    const p = new URLSearchParams();
    if (q) p.set('q', q);
    if (kind) p.set('kind', kind);
    const qs = p.toString();
    return request(`/api/files${qs ? `?${qs}` : ''}`);
  },
  fileDetail: (id) => request(`/api/files/${encodeURIComponent(id)}`),
  deleteFile: (id) => request(`/api/files/${encodeURIComponent(id)}`, { method: 'DELETE' }),

  memories: (q = '') => request(`/api/memory${q ? `?q=${encodeURIComponent(q)}` : ''}`),
  deleteMemory: (id) => request(`/api/memory/${encodeURIComponent(id)}`, { method: 'DELETE' }),

  deleteConversation: (sid) =>
    request(`/api/conversations/${encodeURIComponent(sid)}`, { method: 'DELETE' }),
};

/* ── Model slice loader (shared by chat selector + settings) ────────────── */

export async function loadModels(refresh = false) {
  state.modelsLoading = true;
  state.modelsError = null;
  try {
    const data = await api.models(refresh);
    state.providers = data.providers || [];
    state.modelsLoaded = true;
  } catch (err) {
    state.modelsError = err.message;
    state.providers = [];
  } finally {
    state.modelsLoading = false;
  }
  return state.providers;
}

export async function loadCustomState() {
  try {
    const [custom, keys] = await Promise.all([api.listCustomModels(), api.getApiKeys()]);
    state.customModels = custom.models || [];
    state.hiddenModels = custom.hidden || [];
    state.apiKeys = keys.keys || {};
  } catch { /* non-fatal: catalogue still renders */ }
}

/* Flatten every provider's models into picker-friendly rows. */
export function allModels({ includeUnavailable = false } = {}) {
  const out = [];
  for (const p of state.providers) {
    if (!includeUnavailable && p.status !== 'available') continue;
    for (const m of p.models || []) {
      out.push({ ...m, provider: p.key, providerName: p.name });
    }
  }
  return out;
}

export function providerByKey(key) {
  return state.providers.find((p) => p.key === key) || null;
}

export function findModel(providerKey, modelId) {
  const p = providerByKey(providerKey);
  if (!p) return null;
  return (p.models || []).find((m) => m.id === modelId) || null;
}