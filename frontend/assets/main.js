/* JARVIS web console — entry point. Boots state, wires modules, restores
   persisted preferences (theme, density) before first paint. */

import {
  $, state, api, loadModels, loadCustomState, toast, applyTheme, applySidebar,
} from './core.js';
import { initChat, renderConversations, renderMessages, renderModelTrigger, applyDefaultToChat, newConversation } from './chat.js';
import { initSettings, openSettings } from './settings.js';
import { initPicker } from './picker.js';
import { initVoice } from './voice.js';
import { ensureServer, getServerUrl } from './core.js';

// Re-exported so the module's public surface is unchanged; the definitions
// live in core.js to keep it importable without pulling in the entry point.
export { applyTheme, applySidebar };

/* ── Theme ──────────────────────────────────────────────────────────────── */

/* ── Keyboard: Escape closes the topmost surface ────────────────────────── */

function closeTopmost() {
  const order = ['#addModelModal', '#filePreviewModal', '#pickerModal', '#settingsModal'];
  for (const sel of order) {
    const node = $(sel);
    if (node?.classList.contains('open')) {
      node.classList.remove('open');
      return true;
    }
  }
  return false;
}

/* ── Focus trap for open dialogs ────────────────────────────────────────── */

function trapFocus(container, e) {
  const focusable = container.querySelectorAll(
    'button:not([disabled]), [href], input:not([disabled]), select, textarea, [tabindex]:not([tabindex="-1"])'
  );
  if (!focusable.length) return;
  const first = focusable[0];
  const last = focusable[focusable.length - 1];
  if (e.shiftKey && document.activeElement === first) {
    e.preventDefault();
    last.focus();
  } else if (!e.shiftKey && document.activeElement === last) {
    e.preventDefault();
    first.focus();
  }
}

/* ── Boot ───────────────────────────────────────────────────────────────── */

async function boot() {
  // APK detection (Capacitor WebView has no http(s) page origin... except
  // ours is https://localhost): mark the body so CSS can clear the system
  // status bar and gesture bar, which the WebView draws under.
  if (
    location.protocol === 'capacitor:' ||
    (location.protocol === 'https:' && location.hostname === 'localhost')
  ) {
    document.body.classList.add('apk');
  }

  applyTheme(localStorage.getItem('jarvis.theme') || 'dark');
  document.documentElement.dataset.density = localStorage.getItem('jarvis.density') || 'comfortable';
  applySidebar(localStorage.getItem('jarvis.sidebar') !== 'collapsed');

  state.memoryEnabled = localStorage.getItem('jarvis.memoryEnabled') !== 'false';

  window.matchMedia('(prefers-color-scheme: light)').addEventListener('change', () => {
    if ((localStorage.getItem('jarvis.theme') || 'dark') === 'system') applyTheme('system');
  });

  initChat();
  initSettings();
  initPicker();
  initVoice();

  // Resolve the server before anything needs it: probe the stored URL then
  // baked fallbacks, latch onto whatever answers. A loud banner beats the
  // silent "nothing happens" failure that hid every past outage.
  try {
    const found = await ensureServer();
    renderConnBanner(found);
  } catch {
    renderConnBanner({ ok: false, base: getServerUrl(), tried: [] });
  }

  renderConversations();
  renderMessages();
  renderModelTrigger();

  // Load catalogue + default, then point the chat at the default model.
  try {
    const [dfltRes] = await Promise.all([
      api.getDefault(),
      loadModels(),
      loadCustomState(),
    ]);
    // The endpoint returns {default: {provider, model}} — unwrap it, otherwise
    // state.defaultModel would be the envelope and every read would be empty.
    const dflt = dfltRes?.default;
    state.defaultModel = dflt && dflt.provider
      ? { provider: dflt.provider, model: dflt.model || '' }
      : { provider: '', model: '' };
  } catch (err) {
    toast(`Could not load model catalogue: ${err.message}`, 'err');
  }
  applyDefaultToChat();

  document.addEventListener('keydown', (e) => {
    if (e.key === 'Escape' && closeTopmost()) e.stopPropagation();
    if (e.key === 'Tab') {
      const open = ['#settingsModal', '#pickerModal', '#addModelModal', '#filePreviewModal']
        .map((s) => $(s))
        .find((n) => n?.classList.contains('open'));
      if (open) trapFocus(open, e);
    }
    // Ctrl/Cmd+K opens the model picker.
    if ((e.metaKey || e.ctrlKey) && e.key.toLowerCase() === 'k') {
      e.preventDefault();
      $('#modelTrigger')?.click();
    }
    // Ctrl/Cmd+, opens settings.
    if ((e.metaKey || e.ctrlKey) && e.key === ',') {
      e.preventDefault();
      openSettings();
    }
  });

  // Keep the catalogue fresh when the tab regains focus (cached for 10 min).
  let lastRefresh = Date.now();
  document.addEventListener('visibilitychange', async () => {
    if (document.visibilityState === 'visible' && Date.now() - lastRefresh > 600000) {
      lastRefresh = Date.now();
      await loadModels(true);
      renderModelTrigger();
    }
  });

  // Retry from the banner (and re-check silently when coming back online).
  document.addEventListener('click', async (e) => {
    if (e.target?.id === 'connRetry') {
      const banner = $('#connBanner');
      if (banner) banner.textContent = 'Retrying…';
      renderConnBanner(await ensureServer().catch(() => ({ ok: false, tried: [] })));
      try { await loadModels(true); renderModelTrigger(); } catch { /* banner says it */ }
    }
  });
  window.addEventListener('online', async () => {
    renderConnBanner(await ensureServer().catch(() => ({ ok: false, tried: [] })));
  });
}

function renderConnBanner(found) {
  const banner = $('#connBanner');
  if (!banner) return;
  if (found.ok) {
    banner.hidden = true;
    return;
  }
  const tried = (found.tried || []).join(', ') || 'nothing reachable';
  banner.hidden = false;
  banner.innerHTML = '';
  const msg = document.createElement('span');
  msg.textContent = `Offline — tried ${tried}. Check Wi-Fi/Tailscale or set the server in Settings → Access. `;
  const btn = document.createElement('button');
  btn.id = 'connRetry';
  btn.className = 'btn btn-sm';
  btn.textContent = 'Retry';
  banner.append(msg, btn);
}

boot();