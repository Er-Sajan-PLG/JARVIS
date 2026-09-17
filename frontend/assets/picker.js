/* Searchable model picker — reused by the chat composer and Settings.
   Supports provider grouping, search across provider+model, free/paid,
   capability tags and a minimum context window, and "set as default"
   without leaving the dialog. */

import {
  $, el, api, state, toast, loadModels, isFree, contextLabel, statusInfo,
  escapeHtml, capabilitiesOf, matchesCapabilities, ALL_CAPABILITIES,
} from './core.js';

let pickerState = {
  query: '',
  tier: 'all',        // all | free | paid
  caps: new Set(),    // capability keys; empty means no capability filter
  minCtx: 0,          // minimum context length in tokens; 0 means any
  collapsed: new Set(),
  onSelect: null,
};

function matches(entry, query) {
  if (!query) return true;
  const q = query.toLowerCase();
  return (
    entry.id.toLowerCase().includes(q) ||
    (entry.name || '').toLowerCase().includes(q) ||
    (entry.providerName || '').toLowerCase().includes(q) ||
    (entry.provider || '').toLowerCase().includes(q) ||
    (entry.description || '').toLowerCase().includes(q)
  );
}

function modelRow(entry) {
  const free = isFree(entry);
  const isCurrent =
    state.selectedModel.provider === entry.provider && state.selectedModel.id === entry.id;
  const isDefault =
    state.defaultModel.provider === entry.provider && state.defaultModel.model === entry.id;

  const metaParts = [entry.providerName, contextLabel(entry), entry.description]
    .filter(Boolean)
    .join(' · ');

  // Capability tags, shown as compact badges so a row states what the model
  // can do rather than only what it costs.
  const caps = capabilitiesOf(entry);
  const capBadges = ALL_CAPABILITIES
    .filter((c) => caps.has(c.key) && c.key !== 'text')
    .map((c) => el('span', {
      class: `badge badge-cap badge-cap-${c.key}`,
      title: `${c.label} capable`,
      text: `${c.icon} ${c.label}`,
    }));

  const actions = [];
  if (isDefault) {
    actions.push(el('span', { class: 'mark-default', title: 'Default model', text: '✓ Default' }));
  } else {
    actions.push(
      el('button', {
        class: 'btn btn-sm btn-ghost',
        title: 'Set as default',
        text: 'Set default',
        onclick: async (ev) => {
          ev.stopPropagation();
          try {
            const res = await api.setDefault(entry.provider, entry.id);
            state.defaultModel = res.default;
            toast(`Default model set to ${entry.name || entry.id}`);
            render();
          } catch (err) {
            toast(err.message, 'err');
          }
        },
      })
    );
  }

  return el('div', {
    class: `model-row${isCurrent ? ' selected' : ''}`,
    role: 'button',
    tabindex: '0',
    onclick: () => choose(entry),
    onkeydown: (e) => {
      if (e.key === 'Enter' || e.key === ' ') { e.preventDefault(); choose(entry); }
    },
  }, [
    el('div', { class: 'model-row-main' }, [
      el('div', { class: 'model-row-name', text: entry.name || entry.id }),
      el('div', { class: 'model-row-meta', text: metaParts }),
    ]),
    el('div', { class: 'model-row-actions' }, [
      ...capBadges,
      free
        ? el('span', { class: 'badge badge-free', text: 'Free' })
        : el('span', { class: 'badge badge-paid', text: 'Paid' }),
      entry.is_custom ? el('span', { class: 'badge badge-custom', text: 'Custom' }) : null,
      ...actions,
    ]),
  ]);
}

function choose(entry) {
  if (typeof pickerState.onSelect === 'function') pickerState.onSelect(entry);
  closePicker();
}

function providerBlock(provider) {
  const filtered = (provider.models || []).filter((m) => {
    const entry = { ...m, provider: provider.key, providerName: provider.name };
    if (!matches(entry, pickerState.query)) return false;
    if (pickerState.tier === 'free' && !isFree(m)) return false;
    if (pickerState.tier === 'paid' && isFree(m)) return false;
    if (!matchesCapabilities(entry, pickerState.caps)) return false;
    if (pickerState.minCtx && (m.context_length || 0) < pickerState.minCtx) return false;
    return true;
  });

  if (!filtered.length) return null;

  // While narrowing, always expand so hits are visible.
  const forceOpen = Boolean(pickerState.query) || pickerState.tier !== 'all'
    || pickerState.caps.size > 0 || Boolean(pickerState.minCtx);
  const collapsed = !forceOpen && pickerState.collapsed.has(provider.key);
  const si = statusInfo(provider.status);

  const block = el('div', { class: `provider-block${collapsed ? ' collapsed' : ''}` }, [
    el('div', {
      class: 'provider-block-head',
      role: 'button',
      tabindex: '0',
      onclick: () => {
        if (pickerState.collapsed.has(provider.key)) pickerState.collapsed.delete(provider.key);
        else pickerState.collapsed.add(provider.key);
        render();
      },
      onkeydown: (e) => {
        if (e.key === 'Enter' || e.key === ' ') {
          e.preventDefault();
          if (pickerState.collapsed.has(provider.key)) pickerState.collapsed.delete(provider.key);
          else pickerState.collapsed.add(provider.key);
          render();
        }
      },
    }, [
      el('span', { class: 'provider-caret', text: '▼' }),
      el('span', { class: `dot ${si.dot}`, title: si.label }),
      el('span', { class: 'provider-block-name', text: provider.name }),
      el('span', { class: 'provider-block-count', text: `${filtered.length} models` }),
    ]),
    el('div', { class: 'provider-block-items' },
      filtered.slice(0, 400).map((m) => modelRow({ ...m, provider: provider.key, providerName: provider.name }))
    ),
  ]);
  return block;
}

function render() {
  const body = $('#pickerBody');
  const countEl = $('#pickerCount');
  if (!body) return;

  const usable = state.providers.filter((p) => p.status === 'available' && (p.models || []).length);
  const blocks = usable.map(providerBlock).filter(Boolean);

  body.innerHTML = '';
  const total = blocks.reduce((n, b) => n + b.querySelectorAll('.model-row').length, 0);
  if (countEl) countEl.textContent = `${total} match${total === 1 ? '' : 'es'}`;

  if (state.modelsLoading && !state.providers.length) {
    for (let i = 0; i < 6; i++) body.appendChild(el('div', { class: 'skeleton' }));
    return;
  }
  if (state.modelsError) {
    body.appendChild(el('div', { class: 'state' }, [
      el('div', { class: 'state-title', text: 'Could not load models' }),
      el('div', { text: state.modelsError }),
      el('button', {
        class: 'btn', text: 'Retry',
        onclick: async () => { await loadModels(true); render(); },
      }),
    ]));
    return;
  }
  if (!total) {
    body.appendChild(el('div', { class: 'state' }, [
      el('div', { class: 'state-title', text: 'No models match' }),
      el('div', { text: 'Try a different search, or check API keys in Settings → Model → API Keys.' }),
    ]));
    return;
  }
  blocks.forEach((b) => body.appendChild(b));
}

/* ── Capability filter chips ────────────────────────────────────────────── */

function buildCapFilters() {
  const host = $('#pickerCaps');
  if (!host || host.dataset.built === '1') return;
  host.innerHTML = '';
  for (const c of ALL_CAPABILITIES) {
    host.appendChild(el('button', {
      type: 'button',
      class: 'cap-chip',
      'data-cap': c.key,
      title: `Show only ${c.label} models`,
      text: `${c.icon} ${c.label}`,
      onclick: () => {
        if (pickerState.caps.has(c.key)) pickerState.caps.delete(c.key);
        else pickerState.caps.add(c.key);
        syncCapButtons();
        render();
      },
    }));
  }
  host.dataset.built = '1';
}

function syncCapButtons() {
  document.querySelectorAll('#pickerCaps .cap-chip').forEach((b) => {
    b.classList.toggle('active', pickerState.caps.has(b.dataset.cap));
  });
}

export function openPicker({ onSelect, title = 'Select a model' } = {}) {
  pickerState.onSelect = onSelect || null;
  pickerState.query = '';
  pickerState.tier = 'all';
  pickerState.caps.clear();
  pickerState.minCtx = 0;

  const backdrop = $('#pickerModal');
  if (!backdrop) return;
  $('#pickerTitle').textContent = title;
  const search = $('#pickerSearch');
  if (search) search.value = '';
  const ctx = $('#pickerCtx');
  if (ctx) ctx.value = '0';
  document.querySelectorAll('#pickerTier button').forEach((b) =>
    b.classList.toggle('active', b.dataset.tier === 'all'));
  syncCapButtons();
  render();
  backdrop.classList.add('open');
  setTimeout(() => search?.focus(), 40);

  if (!state.modelsLoaded && !state.modelsLoading) {
    loadModels().then(() => { render(); syncDefault(); });
  }
  syncDefault();
}

async function syncDefault() {
  try {
    const d = await api.getDefault();
    state.defaultModel = d.default || { provider: '', model: '' };
    render();
  } catch { /* keep prior */ }
}

export function closePicker() {
  $('#pickerModal')?.classList.remove('open');
  pickerState.onSelect = null;
}

export function initPicker() {
  $('#pickerClose')?.addEventListener('click', closePicker);
  $('#pickerModal')?.addEventListener('click', (e) => {
    if (e.target.id === 'pickerModal') closePicker();
  });

  const search = $('#pickerSearch');
  if (search) {
    let t = null;
    search.addEventListener('input', () => {
      clearTimeout(t);
      t = setTimeout(() => { pickerState.query = search.value.trim(); render(); }, 90);
    });
  }

  document.querySelectorAll('#pickerTier button').forEach((btn) => {
    btn.addEventListener('click', () => {
      pickerState.tier = btn.dataset.tier;
      document.querySelectorAll('#pickerTier button').forEach((b) => b.classList.toggle('active', b === btn));
      render();
    });
  });

  // Context-window floor.
  $('#pickerCtx')?.addEventListener('change', (e) => {
    pickerState.minCtx = Number(e.target.value) || 0;
    render();
  });

  $('#pickerClearFilters')?.addEventListener('click', () => {
    pickerState.tier = 'all';
    pickerState.caps.clear();
    pickerState.minCtx = 0;
    pickerState.query = '';
    const s = $('#pickerSearch');
    if (s) s.value = '';
    const c = $('#pickerCtx');
    if (c) c.value = '0';
    document.querySelectorAll('#pickerTier button').forEach((b) =>
      b.classList.toggle('active', b.dataset.tier === 'all'));
    syncCapButtons();
    render();
  });

  buildCapFilters();

  $('#pickerRefresh')?.addEventListener('click', async (ev) => {
    const btn = ev.currentTarget;
    btn.disabled = true;
    try {
      await loadModels(true);
      toast('Model catalogue refreshed');
    } catch (err) {
      toast(err.message, 'err');
    } finally {
      btn.disabled = false;
      render();
    }
  });
}

export { render as renderPicker, providerBlock, modelRow, matches };