/* Settings workspace — a large centred sheet with left navigation and a
   contextual right pane. Sections register themselves, so adding Privacy /
   Notifications / Tools later is a one-object change.

   Contract: every control here reads from and writes to the SERVER. There is
   no settings-only client state that the chat path cannot see. */

import {
  $, $$, el, api, state, toast, loadModels, loadCustomState,
  isFree, contextLabel, formatBytes, formatDate, statusInfo, escapeHtml,
  providerByKey, allModels, capabilitiesOf, matchesCapabilities, ALL_CAPABILITIES,
  applyTheme, applySidebar, getApiKey, setApiKey, getServerUrl, setServerUrl, apiUrl,
} from './core.js';
import { openPicker, renderPicker } from './picker.js';
import { applyDefaultToChat } from './chat.js';

/* ── Section registry ───────────────────────────────────────────────────── */

const sections = [];
export function registerSection(section) { sections.push(section); }

/* ── Model section: tab definitions ─────────────────────────────────────── */

let modelTab = 'default';

const MODEL_TABS = [
  { key: 'default', label: 'Default Model' },
  { key: 'models', label: 'Models' },
  { key: 'keys', label: 'API Keys' },
];

/* ── Default Model tab ──────────────────────────────────────────────────── */

function noDefaultCard() {
  return el('div', { class: 'default-card' }, [
    el('div', { class: 'default-card-label', text: 'Provider' }),
    el('div', { class: 'default-card-value', text: 'Not set' }),
    el('div', { class: 'default-card-provider', text: 'No default model chosen — new chats fall back to the server default.' }),
    el('button', {
      class: 'btn btn-primary',
      text: 'Choose a model',
      style: 'margin-top:12px',
      onclick: () => openPicker({
        title: 'Choose default model',
        onSelect: async (entry) => {
          try {
            const res = await api.setDefault(entry.provider, entry.id);
            state.defaultModel = res.default;
            toast(`Default model set to ${entry.name || entry.id}`);
            applyDefaultToChat();
            renderSettings();
          } catch (err) { toast(err.message, 'err'); }
        },
      }),
    }),
  ]);
}

function defaultCard() {
  const { provider, model } = state.defaultModel;
  if (!provider || !model) return noDefaultCard();

  const p = providerByKey(provider);
  const m = p ? (p.models || []).find((x) => x.id === model) : null;

  return el('div', { class: 'default-card' }, [
    el('div', { class: 'default-card-label', text: 'Provider' }),
    el('div', { class: 'default-card-value', text: p ? p.name : provider }),
    el('div', { class: 'default-card-label', style: 'margin-top:14px', text: 'Model' }),
    el('div', { class: 'default-card-value', text: m ? (m.name || m.id) : model }),
    el('div', { class: 'default-card-provider', text: m ? m.id : '' }),
    el('div', { style: 'margin-top:14px' }, [
      el('button', {
        class: 'btn',
        text: 'Change model',
        onclick: () => openPicker({
          title: 'Choose default model',
          onSelect: async (entry) => {
            try {
              const res = await api.setDefault(entry.provider, entry.id);
              state.defaultModel = res.default;
              toast(`Default model set to ${entry.name || entry.id}`);
              applyDefaultToChat();
              renderSettings();
            } catch (err) { toast(err.message, 'err'); }
          },
        }),
      }),
    ]),
  ]);
}

function renderDefaultTab(host) {
  host.innerHTML = '';
  host.appendChild(el('p', {
    style: 'color:var(--text-muted);margin-top:0',
    text: 'New chats start with this model. Search across every configured provider.',
  }));
  host.appendChild(defaultCard());

  host.appendChild(el('div', { style: 'margin-top:8px' }, [
    el('button', {
      class: 'btn',
      text: 'Search all models…',
      onclick: () => openPicker({
        title: 'Choose default model',
        onSelect: async (entry) => {
          try {
            const res = await api.setDefault(entry.provider, entry.id);
            state.defaultModel = res.default;
            toast(`Default model set to ${entry.name || entry.id}`);
            applyDefaultToChat();
            renderSettings();
          } catch (err) { toast(err.message, 'err'); }
        },
      }),
    }),
  ]));

  const recents = allModels().slice(0, 8);
  if (recents.length) {
    host.appendChild(el('h4', { style: 'margin:24px 0 8px', text: 'Quick pick' }));
    const grid = el('div', { style: 'display:flex;flex-wrap:wrap;gap:8px' });
    for (const m of recents) {
      grid.appendChild(el('button', {
        class: 'btn btn-sm',
        title: `${m.providerName} · ${m.id}`,
        text: m.name || m.id,
        onclick: async () => {
          try {
            const res = await api.setDefault(m.provider, m.id);
            state.defaultModel = res.default;
            toast(`Default model set to ${m.name || m.id}`);
            applyDefaultToChat();
            renderSettings();
          } catch (err) { toast(err.message, 'err'); }
        },
      }));
    }
    host.appendChild(grid);
  }
}

/* ── Models tab: provider accordions + add model ────────────────────────── */

const openAccordions = new Set();

function providerAccordion(p) {
  const si = statusInfo(p.status);
  const isOpen = openAccordions.has(p.key);
  const acc = el('div', { class: `acc${isOpen ? ' open' : ''}` });

  const head = el('div', {
    class: 'acc-head',
    role: 'button',
    tabindex: '0',
    'aria-expanded': isOpen ? 'true' : 'false',
    onclick: () => {
      if (openAccordions.has(p.key)) openAccordions.delete(p.key);
      else openAccordions.add(p.key);
      renderModelsTab($('#settingsTabPanel'));
    },
    onkeydown: (e) => {
      if (e.key === 'Enter' || e.key === ' ') {
        e.preventDefault();
        if (openAccordions.has(p.key)) openAccordions.delete(p.key);
        else openAccordions.add(p.key);
        renderModelsTab($('#settingsTabPanel'));
      }
    },
  }, [
    el('span', { class: 'acc-caret', text: '▶' }),
    el('span', { class: `dot ${si.dot}`, title: si.label }),
    el('span', { class: 'acc-name', text: p.name }),
    p.is_custom ? el('span', { class: 'badge badge-custom', text: 'Custom' }) : null,
    el('span', { class: 'acc-count', text: `${p.model_count} models` }),
  ]);
  acc.appendChild(head);

  if (p.status !== 'available') {
    acc.appendChild(el('div', { class: 'acc-error' }, [
      el('strong', { text: si.label }),
      el('div', {
        style: 'margin-top:4px',
        text: p.status === 'no_key'
          ? `Add an API key for ${p.name} in the API Keys tab.`
          : p.status === 'error'
            ? `${p.name} rejected the request. Check the API key, then Refresh.`
            : `${p.name} is not reachable right now.`,
      }),
      el('div', { style: 'margin-top:8px;display:flex;gap:8px' }, [
        el('button', {
          class: 'btn btn-sm',
          text: 'Refresh',
          onclick: async () => {
            await loadModels(true);
            renderSettings();
          },
        }),
        p.is_custom ? el('button', {
          class: 'btn btn-sm btn-danger',
          text: 'Remove provider',
          onclick: () => removeCustomProvider(p),
        }) : null,
      ]),
    ]));
    return acc;
  }

  const body = el('div', { class: 'acc-body' });
  if (!(p.models || []).length) {
    body.appendChild(el('div', { class: 'state', text: 'No models reported by this provider.' }));
  } else {
    for (const m of p.models.slice(0, 500)) {
      const isDefault = state.defaultModel.provider === p.key && state.defaultModel.model === m.id;
      body.appendChild(el('div', { class: 'model-row' }, [
        el('div', { class: 'model-row-main' }, [
          el('div', { class: 'model-row-name', text: m.name || m.id }),
          el('div', {
            class: 'model-row-meta',
            text: [m.id, contextLabel(m), m.description].filter(Boolean).join(' · '),
          }),
        ]),
        el('div', { class: 'model-row-actions' }, [
          ...ALL_CAPABILITIES
            .filter((c) => capabilitiesOf(m).has(c.key) && c.key !== 'text')
            .map((c) => el('span', {
              class: `badge badge-cap badge-cap-${c.key}`,
              title: `${c.label} capable`,
              text: `${c.icon} ${c.label}`,
            })),
          isFree(m)
            ? el('span', { class: 'badge badge-free', text: 'Free' })
            : el('span', { class: 'badge badge-paid', text: 'Paid' }),
          m.is_custom ? el('span', { class: 'badge badge-custom', text: 'Custom' }) : null,
          isDefault ? el('span', { class: 'mark-default', text: '✓ Default' }) : null,
          el('button', {
            class: 'btn btn-sm btn-ghost',
            text: 'Set default',
            onclick: async () => {
              try {
                const res = await api.setDefault(p.key, m.id);
                state.defaultModel = res.default;
                toast(`Default set to ${m.name || m.id}`);
                applyDefaultToChat();
                renderSettings();
              } catch (err) { toast(err.message, 'err'); }
            },
          }),
          el('button', {
            class: 'btn btn-sm btn-ghost',
            title: 'Hide from the catalogue',
            text: 'Hide',
            onclick: async () => {
              try {
                await api.hideModel(p.key, m.id);
                await refreshCatalogue();
                toast('Model hidden');
              } catch (err) { toast(err.message, 'err'); }
            },
          }),
          m.is_custom ? el('button', {
            class: 'btn btn-sm btn-danger',
            text: 'Remove',
            onclick: async () => {
              try {
                await api.deleteCustomModel(p.key, m.id);
                await refreshCatalogue();
                toast('Model removed');
              } catch (err) { toast(err.message, 'err'); }
            },
          }) : null,
        ]),
      ]));
    }
  }
  acc.appendChild(body);
  return acc;
}

async function removeCustomProvider(p) {
  if (!confirm(`Remove the custom provider "${p.name}" and its models?`)) return;
  try {
    await api.deleteCustomProvider(p.key);
    await refreshCatalogue();
    toast(`Removed ${p.name}`);
  } catch (err) { toast(err.message, 'err'); }
}

function renderModelsTab(host) {
  if (!host) return;
  host.innerHTML = '';

  const bar = el('div', { class: 'files-toolbar' }, [
    el('input', {
      class: 'input',
      id: 'modelsSearchInput',
      placeholder: 'Search models…',
      value: modelsSearch,
      oninput: (e) => {
        modelsSearch = e.target.value;
        renderModelsTab(host);
        $('#modelsSearchInput')?.focus();
      },
    }),
    el('button', {
      class: 'btn',
      text: 'Refresh',
      onclick: async (ev) => {
        ev.currentTarget.disabled = true;
        ev.currentTarget.textContent = 'Refreshing…';
        await refreshCatalogue(true);
        toast('Catalogue refreshed');
      },
    }),
    el('button', {
      class: 'btn',
      text: modelsFreeOnly ? '★ Free only' : '☆ Free only',
      title: 'Show only models you can call without paying',
      onclick: () => {
        modelsFreeOnly = !modelsFreeOnly;
        renderModelsTab(host);
      },
    }),
    el('button', {
      class: 'btn btn-primary',
      text: '+ Add model',
      onclick: () => openAddModelDialog(),
    }),
    el('button', {
      class: 'btn',
      text: '+ Add provider',
      onclick: () => openProviderDialog(),
    }),
  ]);
  host.appendChild(bar);

  // Capability + context filters. Capabilities are OR-ed for display but
  // AND-ed when filtering: selecting Vision and Tools means both are required.
  const filters = el('div', { class: 'filter-bar' }, [
    el('span', { class: 'filter-label', text: 'Capability' }),
    el('div', { class: 'cap-picker' },
      ALL_CAPABILITIES.map((c) => el('button', {
        class: `cap-chip${modelsCaps.has(c.key) ? ' active' : ''}`,
        text: `${c.icon} ${c.label}`,
        title: `Require ${c.label} support`,
        onclick: () => {
          if (modelsCaps.has(c.key)) modelsCaps.delete(c.key);
          else modelsCaps.add(c.key);
          renderModelsTab(host);
        },
      }))),
    el('span', { class: 'filter-label', text: 'Min context' }),
    el('input', {
      class: 'input input-sm',
      id: 'modelsMinCtx',
      type: 'number',
      min: '0',
      step: '1000',
      placeholder: 'tokens',
      value: modelsMinCtx ? String(modelsMinCtx) : '',
      oninput: (e) => {
        modelsMinCtx = Math.max(0, Number(e.target.value) || 0);
        const pos = e.target.selectionStart;
        renderModelsTab(host);
        const next = $('#modelsMinCtx');
        next?.focus();
        if (pos != null) next?.setSelectionRange(pos, pos);
      },
    }),
    (modelsCaps.size || modelsMinCtx)
      ? el('button', {
        class: 'btn btn-sm',
        text: 'Clear filters',
        onclick: () => {
          modelsCaps.clear();
          modelsMinCtx = 0;
          renderModelsTab(host);
        },
      })
      : null,
  ].filter(Boolean));
  host.appendChild(filters);

  if (state.modelsLoading && !state.providers.length) {
    for (let i = 0; i < 5; i++) host.appendChild(el('div', { class: 'skeleton' }));
    return;
  }
  if (state.modelsError) {
    host.appendChild(el('div', { class: 'state' }, [
      el('div', { class: 'state-title', text: 'Unable to load model catalogue' }),
      el('div', { text: state.modelsError }),
      el('button', {
        class: 'btn', text: 'Retry',
        onclick: async () => { await refreshCatalogue(true); },
      }),
    ]));
    return;
  }

  const q = modelsSearch.trim().toLowerCase();

  const narrowed = (m) => {
    if (modelsFreeOnly && !m.free) return false;
    if (modelsCaps.size && !matchesCapabilities(m, modelsCaps)) return false;
    if (modelsMinCtx && (m.context_length || 0) < modelsMinCtx) return false;
    if (q && !(m.id.toLowerCase().includes(q) || (m.name || '').toLowerCase().includes(q))) {
      return false;
    }
    return true;
  };
  const anyFilter = Boolean(q) || modelsFreeOnly || modelsCaps.size > 0 || modelsMinCtx > 0;

  // A provider stays visible when its name matches; otherwise it is narrowed
  // to the models that match the active filters.
  const visible = state.providers
    .map((p) => {
      const hitProvider = q && (p.name.toLowerCase().includes(q) || p.key.toLowerCase().includes(q));
      const models = (p.models || []).filter(narrowed);
      if (!hitProvider && !models.length) return null;
      if (hitProvider && !anyFilter) return { ...p, model_count: models.length };
      if (hitProvider && !models.length) return null;
      return { ...p, models, model_count: models.length };
    })
    .filter(Boolean);

  if (!visible.length) {
    const why = modelsFreeOnly
      ? 'No free models matched. Turn off “Free only”, widen the search, or add a provider with a free tier.'
      : modelsCaps.size
        ? `No models matched every selected capability (${[...modelsCaps].join(', ')}). Remove one to widen the results.`
        : modelsMinCtx
          ? `No models report a context window of ${modelsMinCtx.toLocaleString()}+ tokens. Lower the minimum, or add a custom model with its context length.`
          : 'Clear the search, or add a custom provider with “+ Add provider”.';
    host.appendChild(el('div', { class: 'state' }, [
      el('div', { class: 'state-title', text: 'No models match' }),
      el('div', { text: why }),
    ]));
    return;
  }

  const connected = visible.filter((p) => p.status === 'available');
  const others = visible.filter((p) => p.status !== 'available');

  if (connected.length) {
    host.appendChild(el('div', { class: 'conv-group-label', style: 'padding-left:0', text: 'Connected' }));
    connected.forEach((p) => host.appendChild(providerAccordion(p)));
  }
  if (others.length) {
    host.appendChild(el('div', { class: 'conv-group-label', style: 'padding-left:0', text: 'Needs attention' }));
    others.forEach((p) => host.appendChild(providerAccordion(p)));
  }
}

let modelsSearch = '';
let modelsFreeOnly = false;
const modelsCaps = new Set();
let modelsMinCtx = 0;

/* ── Add model dialog ───────────────────────────────────────────────────── */

// Capabilities ticked for the model being added. Empty means "let the app
// infer from the id", which is the common case.
const pendingModelCaps = new Set();

function buildAddModelCaps() {
  const host = $('#addModelCaps');
  if (!host) return;
  host.innerHTML = '';
  for (const c of ALL_CAPABILITIES) {
    host.appendChild(el('button', {
      type: 'button',
      class: `cap-chip${pendingModelCaps.has(c.key) ? ' active' : ''}`,
      'data-cap': c.key,
      text: `${c.icon} ${c.label}`,
      onclick: (ev) => {
        const chip = ev.currentTarget;
        if (pendingModelCaps.has(c.key)) pendingModelCaps.delete(c.key);
        else pendingModelCaps.add(c.key);
        chip.classList.toggle('active', pendingModelCaps.has(c.key));
      },
    }));
  }
}

function openAddModelDialog(presetProvider = '') {
  const backdrop = $('#addModelModal');
  if (!backdrop) return;
  const form = $('#addModelForm');
  form.reset();
  pendingModelCaps.clear();
  buildAddModelCaps();

  // Provider dropdown: every catalogue provider plus custom ones, plus an
  // escape hatch that opens the full provider form.
  const select = $('#addModelProvider');
  select.innerHTML = '';
  const opts = state.providers.map((p) => ({
    key: p.key,
    name: p.is_custom ? `${p.name}  (custom)` : p.name,
  }));
  for (const o of opts) {
    select.appendChild(el('option', { value: o.key, text: o.name, selected: o.key === presetProvider }));
  }
  select.appendChild(el('option', { value: '__new__', text: '＋ Add a new provider…' }));

  // Switching to "new provider" hands off to the provider dialog instead of
  // trying to attach a model to a provider that does not exist yet.
  select.onchange = () => {
    if (select.value === '__new__') {
      backdrop.classList.remove('open');
      openProviderDialog();
      select.value = presetProvider || (opts[0] && opts[0].key) || '';
    }
  };

  const hint = $('#addModelProviderHint');
  if (hint) {
    hint.textContent = opts.length
      ? 'Any provider in the catalogue, including your custom ones.'
      : 'No providers loaded yet — add one first.';
  }
  $('#addModelError').textContent = '';
  backdrop.classList.add('open');
  setTimeout(() => $('#addModelId')?.focus(), 40);
}

async function submitAddModel(ev) {
  ev.preventDefault();
  const provider = $('#addModelProvider').value;
  const id = $('#addModelId').value.trim();
  const name = $('#addModelName').value.trim();
  const ctx = parseInt($('#addModelContext').value, 10);
  const errBox = $('#addModelError');

  if (!provider || !id) {
    errBox.textContent = 'Provider and model ID are required.';
    return;
  }
  if (provider === '__new__') {
    errBox.textContent = 'Choose a provider, or create one with the form that just opened.';
    return;
  }
  try {
    await api.addCustomModel({
      provider,
      id,
      name: name || id,
      context_length: Number.isFinite(ctx) && ctx > 0 ? ctx : 0,
      capabilities: [...pendingModelCaps],
    });
    $('#addModelModal').classList.remove('open');
    await refreshCatalogue();
    toast(`Added ${name || id}`);
  } catch (err) {
    errBox.textContent = err.message;
  }
}

/* ── Add custom provider dialog ─────────────────────────────────────────── */

// Models discovered/entered for the provider currently being edited. Kept out
// of the DOM so re-rendering the chips never loses an entry.
let pendingProviderModels = [];

// Capabilities ticked for manually added models in the provider dialog.
const pendingProviderCaps = new Set();

function buildProviderCaps() {
  const host = $('#providerCaps');
  if (!host || !ALL_CAPABILITIES) return;
  host.innerHTML = '';
  for (const c of ALL_CAPABILITIES) {
    const chip = el('button', {
      type: 'button',
      class: `cap-chip${pendingProviderCaps.has(c.key) ? ' active' : ''}`,
      title: c.label,
      onclick: () => {
        if (pendingProviderCaps.has(c.key)) pendingProviderCaps.delete(c.key);
        else pendingProviderCaps.add(c.key);
        chip.classList.toggle('active', pendingProviderCaps.has(c.key));
      },
    }, [el('span', { text: `${c.icon} ${c.label}` })]);
    host.appendChild(chip);
  }
}

function openProviderDialog() {
  const backdrop = $('#providerModal');
  if (!backdrop) return;
  $('#providerForm')?.reset();
  pendingProviderModels = [];
  pendingProviderCaps.clear();
  $('#providerContext').value = '';
  buildProviderCaps();
  drawPendingModels();
  const status = $('#providerFetchStatus');
  if (status) status.textContent = '';
  $('#providerError').textContent = '';
  backdrop.classList.add('open');
  setTimeout(() => $('#providerName')?.focus(), 40);
}

function closeProviderDialog() {
  $('#providerModal')?.classList.remove('open');
}

function drawPendingModels() {
  const host = $('#providerModelList');
  if (!host) return;
  host.innerHTML = '';
  if (!pendingProviderModels.length) {
    host.appendChild(el('span', {
      class: 'hint', style: 'padding:0',
      text: 'No models yet — fetch or add them manually.',
    }));
    return;
  }
  for (const id of pendingProviderModels) {
    host.appendChild(el('button', {
      type: 'button',
      class: 'chip chip-removable',
      title: 'Click to remove',
      onclick: () => {
        pendingProviderModels = pendingProviderModels.filter((m) => m !== id);
        drawPendingModels();
      },
    }, [el('span', { text: id }), el('span', { class: 'chip-x', text: '✕' })]));
  }
}

async function fetchProviderModels() {
  const baseUrl = $('#providerBaseUrl').value.trim();
  const apiKey = $('#providerKey').value.trim();
  const status = $('#providerFetchStatus');
  const errBox = $('#providerError');
  errBox.textContent = '';
  if (!baseUrl) {
    errBox.textContent = 'Enter the base URL first.';
    return;
  }
  status.textContent = 'Fetching…';
  try {
    const res = await api.fetchProviderModels(baseUrl, apiKey);
    const found = (res.models || []).map((m) => (typeof m === 'string' ? m : m.id)).filter(Boolean);
    if (!found.length) {
      status.textContent = 'No models returned by that endpoint.';
      return;
    }
    for (const id of found) {
      if (!pendingProviderModels.includes(id)) pendingProviderModels.push(id);
    }
    drawPendingModels();
    status.textContent = `Found ${found.length} model${found.length === 1 ? '' : 's'}.`;
  } catch (err) {
    status.textContent = '';
    errBox.textContent = `Could not fetch models: ${err.message}`;
  }
}

async function submitProvider(ev) {
  ev.preventDefault();
  const name = $('#providerName').value.trim();
  const baseUrl = $('#providerBaseUrl').value.trim();
  const apiKey = $('#providerKey').value.trim();
  const errBox = $('#providerError');
  errBox.textContent = '';

  if (!name || !baseUrl) {
    errBox.textContent = 'Provider name and base URL are required.';
    return;
  }
  const ctxRaw = $('#providerContext').value.trim();
  const contextLength = ctxRaw ? Number(ctxRaw) : 0;
  if (ctxRaw && (!Number.isFinite(contextLength) || contextLength < 0)) {
    errBox.textContent = 'Max context length must be a non-negative number.';
    return;
  }
  try {
    await api.addProvider({
      name,
      base_url: baseUrl,
      api_key: apiKey,
      context_length: contextLength,
      capabilities: [...pendingProviderCaps],
      models: pendingProviderModels.map((id) => ({ id, name: id })),
    });
    closeProviderDialog();
    await refreshCatalogue();
    toast(`Added provider ${name}`);
  } catch (err) {
    errBox.textContent = err.message;
  }
}

/* ── API Keys tab ───────────────────────────────────────────────────────── */

const KEY_PROVIDERS = [
  ['openrouter', 'OpenRouter'], ['nvidia', 'NVIDIA NIM'], ['google', 'Google AI Studio'],
  ['groq', 'Groq'], ['github', 'GitHub Models'], ['mistral', 'Mistral AI'],
  ['cohere', 'Cohere'], ['huggingface', 'Hugging Face'], ['cloudflare', 'Cloudflare Workers AI'],
  ['zhipu', 'Zhipu AI (GLM)'], ['openai', 'OpenAI'], ['anthropic', 'Anthropic'],
  ['together', 'Together AI'], ['cerebras', 'Cerebras'], ['singularity', 'Singularity'],
];

function keyRow(provider, label) {
  const info = state.apiKeys[provider] || { configured: false, source: null };
  const envOnly = info.configured && info.source === 'env';

  const statusText = info.configured
    ? (envOnly ? 'Connected (from environment)' : 'Connected (stored)')
    : 'Not configured';

  // The real value never reaches the browser, so there is nothing to reveal.
  // A configured key therefore shows its status, not a fake masked string.
  const row = el('div', { class: 'key-row' });
  row.appendChild(el('div', { class: 'key-row-head' }, [
    el('span', { class: `dot ${info.configured ? 'dot-ok' : 'dot-off'}`, title: statusText }),
    el('span', { class: 'key-row-name', text: label }),
    el('span', { class: 'badge', text: statusText }),
  ]));

  // Editor is built on demand so switching between view and edit is a plain
  // re-render of just this row.
  const controls = el('div', { class: 'key-row-controls' });
  row.appendChild(controls);

  function drawView() {
    controls.innerHTML = '';
    if (info.configured) {
      controls.appendChild(el('div', {
        class: 'key-value-masked',
        text: '••••••••••••••••••••',
        title: 'The stored value is never sent to the browser.',
      }));
    }
    controls.appendChild(el('button', {
      class: 'btn btn-sm',
      type: 'button',
      text: info.configured ? 'Replace key' : 'Add key',
      onclick: drawEdit,
    }));
    if (info.configured && !envOnly) {
      controls.appendChild(el('button', {
        class: 'btn btn-sm btn-danger',
        type: 'button',
        text: 'Remove',
        onclick: async () => {
          if (!confirm(`Remove the stored ${label} key?`)) return;
          try {
            await api.deleteApiKey(provider);
            toast(`${label} key removed`);
            await loadKeys();
            renderKeysTab($('#settingsTabPanel'));
          } catch (err) { toast(err.message, 'err'); }
        },
      }));
    }
    if (envOnly) {
      controls.appendChild(el('span', {
        class: 'hint', style: 'padding:0',
        text: 'Set in the server environment; override it by storing a key here.',
      }));
    }
  }

  function drawEdit() {
    controls.innerHTML = '';
    const input = el('input', {
      class: 'input',
      type: 'password',
      placeholder: info.configured ? 'Paste the new key' : 'sk-…',
      'aria-label': `${label} API key`,
      autocomplete: 'off',
    });
    const toggle = el('button', {
      class: 'btn btn-sm',
      type: 'button',
      text: 'Show',
      onclick: (ev) => {
        const hidden = input.type === 'password';
        input.type = hidden ? 'text' : 'password';
        ev.currentTarget.textContent = hidden ? 'Hide' : 'Show';
      },
    });
    const save = el('button', {
      class: 'btn btn-sm btn-primary',
      type: 'button',
      text: 'Save',
      onclick: async () => {
        const value = input.value.trim();
        if (!value) {
          toast('Enter the key value first', 'err');
          input.focus();
          return;
        }
        save.disabled = true;
        save.textContent = 'Saving…';
        try {
          await api.saveApiKey(provider, value);
          toast(`${label} key saved`);
          await loadKeys();
          renderKeysTab($('#settingsTabPanel'));
        } catch (err) {
          toast(err.message, 'err');
          save.disabled = false;
          save.textContent = 'Save';
        }
      },
    });
    input.addEventListener('keydown', (e) => {
      if (e.key === 'Enter') { e.preventDefault(); save.click(); }
      if (e.key === 'Escape') { e.preventDefault(); drawView(); }
    });

    controls.appendChild(input);
    controls.appendChild(toggle);
    controls.appendChild(save);
    controls.appendChild(el('button', {
      class: 'btn btn-sm',
      type: 'button',
      text: 'Cancel',
      onclick: drawView,
    }));
    setTimeout(() => input.focus(), 30);
  }

  drawView();
  return row;
}

async function loadKeys() {
  try {
    const res = await api.getApiKeys();
    state.apiKeys = res.keys || {};
  } catch { /* non-fatal */ }
}

function renderKeysTab(host) {
  if (!host) return;
  host.innerHTML = '';
  host.appendChild(el('p', {
    style: 'color:var(--text-muted);margin-top:0',
    text: 'Credentials used by provider connections. Values are stored server-side and never sent back to the browser.',
  }));
  host.appendChild(el('p', {
    style: 'color:var(--text-muted);margin-top:0;font-size:12.5px',
    text: 'A key already present in the server environment shows as connected and cannot be removed from here.',
  }));
  for (const [key, label] of KEY_PROVIDERS) {
    host.appendChild(keyRow(key, label));
  }
}

/* ── Memory section ─────────────────────────────────────────────────────── */

let memoryCache = [];

async function loadMemories(q = '') {
  const res = await api.memories(q);
  memoryCache = res.memories || [];
  return memoryCache;
}

async function renderMemorySection(host) {
  host.innerHTML = '';
  host.appendChild(el('div', { class: 'settings-section-head' }, [
    el('h3', { text: 'Memory' }),
    el('p', { text: 'What JARVIS remembers between conversations.' }),
  ]));

  const panel = el('div', { class: 'tab-panel' });

  const toggle = el('input', { type: 'checkbox', checked: state.memoryEnabled, id: 'memEnabled' });
  toggle.addEventListener('change', () => {
    state.memoryEnabled = toggle.checked;
    localStorage.setItem('jarvis.memoryEnabled', String(toggle.checked));
    toast(`Memory ${toggle.checked ? 'enabled' : 'disabled'}`);
  });

  panel.appendChild(el('div', { class: 'default-card' }, [
    el('label', { style: 'display:flex;align-items:center;gap:10px;cursor:pointer' }, [
      toggle,
      el('div', {}, [
        el('div', { style: 'font-weight:600', text: 'Memory enabled' }),
        el('div', {
          style: 'font-size:12.5px;color:var(--text-muted)',
          text: 'When on, relevant memories are added to each request and new facts are stored.',
        }),
      ]),
    ]),
  ]));

  const toolbar = el('div', { class: 'files-toolbar' }, [
    el('input', {
      class: 'input', id: 'memSearch', placeholder: 'Search memories…',
      oninput: (e) => { clearTimeout(toolbar._t); toolbar._t = setTimeout(() => draw(e.target.value), 200); },
    }),
    el('button', {
      class: 'btn', text: 'Refresh',
      onclick: () => draw($('#memSearch')?.value || ''),
    }),
  ]);
  panel.appendChild(toolbar);

  const list = el('div', { id: 'memList' });
  panel.appendChild(list);
  host.appendChild(panel);

  async function draw(q = '') {
    list.innerHTML = '';
    for (let i = 0; i < 4; i++) list.appendChild(el('div', { class: 'skeleton' }));
    try {
      const mems = await loadMemories(q);
      list.innerHTML = '';
      if (!mems.length) {
        list.appendChild(el('div', { class: 'state' }, [
          el('div', { class: 'state-title', text: 'No memories yet' }),
          el('div', { text: 'Memories appear here as you chat.' }),
        ]));
        return;
      }
      for (const m of mems) {
        list.appendChild(el('div', { class: 'mem-row' }, [
          el('div', { class: 'mem-value' }, [
            el('div', { text: m.value }),
            el('div', {
              class: 'mem-meta',
              text: [m.category, formatDate(m.created_at ? Date.parse(m.created_at) / 1000 : null)]
                .filter(Boolean).join(' · '),
            }),
          ]),
          el('button', {
            class: 'btn btn-sm btn-danger', text: 'Delete',
            onclick: async () => {
              if (!confirm('Delete this memory?')) return;
              try {
                await api.deleteMemory(m.id);
                toast('Memory deleted');
                draw(q);
              } catch (err) { toast(err.message, 'err'); }
            },
          }),
        ]));
      }
    } catch (err) {
      list.innerHTML = '';
      list.appendChild(el('div', { class: 'state' }, [
        el('div', { class: 'state-title', text: 'Could not load memories' }),
        el('div', { text: err.message }),
        el('button', { class: 'btn', text: 'Retry', onclick: () => draw(q) }),
      ]));
    }
  }

  draw();
}

/* ── UI section ─────────────────────────────────────────────────────────── */

function renderUiSection(host) {
  host.innerHTML = '';
  host.appendChild(el('div', { class: 'settings-section-head' }, [
    el('h3', { text: 'UI' }),
    el('p', { text: 'Appearance and layout preferences. Saved in this browser.' }),
  ]));

  const panel = el('div', { class: 'tab-panel' });

  panel.appendChild(el('div', { class: 'default-card' }, [
    el('div', { class: 'default-card-label', text: 'Theme' }),
    el('div', { class: 'seg', style: 'margin-top:8px;display:inline-flex' },
      ['dark', 'light', 'system'].map((mode) =>
        el('button', {
          class: (localStorage.getItem('jarvis.theme') || 'dark') === mode ? 'active' : '',
          text: mode[0].toUpperCase() + mode.slice(1),
          onclick: (ev) => {
            localStorage.setItem('jarvis.theme', mode);
            applyTheme(mode);
            $$('#uiThemeSeg button').forEach((b) => b.classList.toggle('active', b === ev.currentTarget));
          },
          id: mode === 'dark' ? 'uiThemeSegFirst' : null,
        })
      )
    ),
    el('div', { class: 'default-card-provider', style: 'margin-top:10px', text: 'System follows your operating system setting.' }),
  ]));
  panel.querySelector('.seg').id = 'uiThemeSeg';

  const densityKey = 'jarvis.density';
  panel.appendChild(el('div', { class: 'default-card' }, [
    el('div', { class: 'default-card-label', text: 'Message density' }),
    el('div', { class: 'seg', id: 'uiDensitySeg', style: 'margin-top:8px;display:inline-flex' },
      ['comfortable', 'compact'].map((d) =>
        el('button', {
          class: (localStorage.getItem(densityKey) || 'comfortable') === d ? 'active' : '',
          text: d[0].toUpperCase() + d.slice(1),
          onclick: (ev) => {
            localStorage.setItem(densityKey, d);
            document.documentElement.dataset.density = d;
            $$('#uiDensitySeg button').forEach((b) => b.classList.toggle('active', b === ev.currentTarget));
          },
        })
      )
    ),
  ]));

  panel.appendChild(el('div', { class: 'default-card' }, [
    el('label', { style: 'display:flex;align-items:center;gap:10px;cursor:pointer' }, [
      el('input', {
        type: 'checkbox',
        checked: localStorage.getItem('jarvis.sidebar') !== 'collapsed',
        onchange: (ev) => {
          const collapsed = !ev.target.checked;
          localStorage.setItem('jarvis.sidebar', collapsed ? 'collapsed' : 'open');
          applySidebar(!collapsed);
        },
      }),
      el('div', {}, [
        el('div', { style: 'font-weight:600', text: 'Show sidebar' }),
        el('div', { style: 'font-size:12.5px;color:var(--text-muted)', text: 'Conversation list on the left.' }),
      ]),
    ]),
  ]));

  host.appendChild(panel);
}

/* ── Files section ──────────────────────────────────────────────────────── */

let filesCache = [];
let filesSort = { key: 'modified', dir: -1 };
let filesKind = '';

async function renderFilesSection(host) {
  host.innerHTML = '';
  host.appendChild(el('div', { class: 'settings-section-head' }, [
    el('h3', { text: 'Files' }),
    el('p', { text: 'Files you have uploaded. These are available for attachment in chat.' }),
  ]));

  const panel = el('div', { class: 'tab-panel' });

  const toolbar = el('div', { class: 'files-toolbar' }, [
    el('input', {
      class: 'input', id: 'filesSearch', placeholder: 'Search files…',
      oninput: () => draw(),
    }),
    el('select', {
      class: 'input', id: 'filesKindFilter', style: 'max-width:150px',
      onchange: (e) => { filesKind = e.target.value; draw(); },
    }, [
      el('option', { value: '', text: 'All types' }),
      el('option', { value: 'pdf', text: 'PDF' }),
      el('option', { value: 'text', text: 'Text / Code' }),
      el('option', { value: 'spreadsheet', text: 'Spreadsheet' }),
      el('option', { value: 'image', text: 'Image' }),
      el('option', { value: 'other', text: 'Other' }),
    ]),
    el('button', { class: 'btn', text: 'Refresh', onclick: () => draw(true) }),
  ]);
  panel.appendChild(toolbar);

  const host2 = el('div', { id: 'filesList' });
  panel.appendChild(host2);
  host.appendChild(panel);

  async function draw(force = false) {
    host2.innerHTML = '';
    for (let i = 0; i < 5; i++) host2.appendChild(el('div', { class: 'skeleton' }));
    const q = $('#filesSearch')?.value || '';
    try {
      const res = await api.files(q, filesKind);
      filesCache = res.files || [];
      renderTable();
    } catch (err) {
      host2.innerHTML = '';
      host2.appendChild(el('div', { class: 'state' }, [
        el('div', { class: 'state-title', text: 'Could not load files' }),
        el('div', { text: err.message }),
        el('button', { class: 'btn', text: 'Retry', onclick: () => draw() }),
      ]));
    }
  }

  function renderTable() {
    host2.innerHTML = '';
    if (!filesCache.length) {
      host2.appendChild(el('div', { class: 'state' }, [
        el('div', { class: 'state-title', text: 'No files' }),
        el('div', { text: 'Upload a file from the chat composer and it will appear here.' }),
      ]));
      return;
    }

    const rows = [...filesCache].sort((a, b) => {
      const { key, dir } = filesSort;
      const av = a[key], bv = b[key];
      if (typeof av === 'string') return String(av).localeCompare(String(bv)) * dir;
      return ((av ?? 0) - (bv ?? 0)) * dir;
    });

    const table = el('table', { class: 'file-table' });
    const headRow = el('tr');
    for (const [key, label] of [['filename', 'Name'], ['kind', 'Type'], ['size', 'Size'], ['modified', 'Date']]) {
      headRow.appendChild(el('th', {
        text: label,
        onclick: () => {
          if (filesSort.key === key) filesSort.dir *= -1;
          else filesSort = { key, dir: key === 'filename' ? 1 : -1 };
          renderTable();
        },
      }));
    }
    headRow.appendChild(el('th', { text: '', style: 'text-align:right' }));
    table.appendChild(el('thead', {}, [headRow]));

    const tbody = el('tbody');
    for (const f of rows) {
      const icon = { pdf: '📕', text: '📄', spreadsheet: '📊', image: '🖼', other: '📦' }[f.kind] || '📦';
      tbody.appendChild(el('tr', {}, [
        el('td', {}, [el('div', { class: 'file-name' }, [
          el('span', { text: icon }),
          el('span', { title: f.filename, text: f.filename }),
        ])]),
        el('td', { text: f.kind }),
        el('td', { text: formatBytes(f.size) }),
        el('td', { text: formatDate(f.modified) }),
        el('td', {}, [el('div', { class: 'file-actions' }, [
          el('button', {
            class: 'btn btn-sm', text: 'Preview',
            onclick: () => previewFile(f),
          }),
          el('a', {
            class: 'btn btn-sm', text: 'Download',
            href: `/api/files/${encodeURIComponent(f.id)}/download`,
            download: f.filename,
          }),
          el('button', {
            class: 'btn btn-sm btn-danger', text: 'Delete',
            onclick: async () => {
              if (!confirm(`Delete ${f.filename}?`)) return;
              try {
                await api.deleteFile(f.id);
                toast('File deleted');
                draw();
              } catch (err) { toast(err.message, 'err'); }
            },
          }),
        ])]),
      ]));
    }
    table.appendChild(tbody);
    host2.appendChild(table);
  }

  draw();
}

async function previewFile(f) {
  const backdrop = $('#filePreviewModal');
  const body = $('#filePreviewBody');
  const title = $('#filePreviewTitle');
  if (!backdrop) return;
  title.textContent = f.filename;
  body.innerHTML = '<div class="skeleton"></div><div class="skeleton"></div>';
  backdrop.classList.add('open');

  try {
    const detail = await api.fileDetail(f.id);
    body.innerHTML = '';
    body.appendChild(el('div', { class: 'default-card' }, [
      el('div', { style: 'display:flex;gap:24px;flex-wrap:wrap;font-size:12.5px;color:var(--text-secondary)' }, [
        el('div', {}, [el('div', { class: 'default-card-label', text: 'Size' }), el('div', { text: formatBytes(detail.size) })]),
        el('div', {}, [el('div', { class: 'default-card-label', text: 'Type' }), el('div', { text: detail.kind })]),
        el('div', {}, [el('div', { class: 'default-card-label', text: 'Uploaded' }), el('div', { text: formatDate(detail.modified) })]),
        el('div', {}, [el('div', { class: 'default-card-label', text: 'Status' }), el('div', { text: detail.extractable ? '✓ Extractable' : 'Metadata only' })]),
      ]),
    ]));

    if (detail.preview && detail.preview.trim()) {
      body.appendChild(el('div', { class: 'default-card-label', style: 'margin:16px 0 6px', text: 'Extracted text' }));
      body.appendChild(el('pre', {
        style: 'max-height:320px;overflow:auto;background:var(--bg-input);border:1px solid var(--border-subtle);padding:12px;border-radius:9px;font-size:12px;white-space:pre-wrap',
        text: detail.preview.slice(0, 8000),
      }));
    } else {
      body.appendChild(el('div', { class: 'state', text: 'No text could be extracted from this file. Metadata shown above.' }));
    }
  } catch (err) {
    body.innerHTML = '';
    body.appendChild(el('div', { class: 'state' }, [
      el('div', { class: 'state-title', text: 'Preview unavailable' }),
      el('div', { text: err.message }),
    ]));
  }
}

/* ── Section definitions ────────────────────────────────────────────────── */

registerSection({
  key: 'model',
  label: 'Model',
  icon: '🧠',
  render: (host) => {
    host.innerHTML = '';
    host.appendChild(el('div', { class: 'settings-section-head' }, [
      el('h3', { text: 'Model' }),
      el('p', { text: 'Default model, provider connections and credentials.' }),
    ]));
    host.appendChild(el('div', { class: 'tabs', role: 'tablist' },
      MODEL_TABS.map((t) =>
        el('button', {
          class: `tab${modelTab === t.key ? ' active' : ''}`,
          role: 'tab',
          'aria-selected': modelTab === t.key ? 'true' : 'false',
          text: t.label,
          onclick: () => { modelTab = t.key; renderSettings(); },
        })
      )
    ));
    const panel = el('div', { class: 'tab-panel', id: 'settingsTabPanel' });
    host.appendChild(panel);
    if (modelTab === 'default') renderDefaultTab(panel);
    else if (modelTab === 'models') renderModelsTab(panel);
    else { renderKeysTab(panel); loadKeys().then(() => renderKeysTab(panel)); }
  },
});

registerSection({ key: 'memory', label: 'Memory', icon: '🧷', render: renderMemorySection });
registerSection({ key: 'ui', label: 'UI', icon: '🎨', render: renderUiSection });
registerSection({ key: 'files', label: 'Files', icon: '📁', render: renderFilesSection });
registerSection({ key: 'access', label: 'Access', icon: '🔑', render: renderAccessSection });

/* ── Access section ─────────────────────────────────────────────────────── */

/* The console API requires JARVIS_API_KEY once one is configured on the server.
   A browser cannot read the server's environment, so the operator enters the
   key here and it is stored per-origin. */
async function renderAccessSection(host) {
  host.innerHTML = '';
  host.appendChild(el('div', { class: 'settings-section-head' }, [
    el('h3', { text: 'Access' }),
    el('p', { text: 'The API key this device uses to reach JARVIS.' }),
  ]));

  const panel = el('div', { class: 'tab-panel' });
  const stored = getApiKey();

  const input = el('input', {
    type: 'password',
    id: 'consoleApiKey',
    placeholder: 'Paste the JARVIS_API_KEY from the server .env',
    value: stored,
    autocomplete: 'off',
    spellcheck: 'false',
    style: 'width:100%;padding:10px 12px;border-radius:8px;border:1px solid var(--border);background:var(--surface-2);color:var(--text);font-family:ui-monospace,monospace;font-size:13px',
  });

  const status = el('div', {
    text: stored ? 'A key is stored on this device.' : 'No key stored on this device.',
    style: 'margin-top:8px;font-size:13px;color:var(--text-muted)',
  });

  const save = el('button', { class: 'btn btn-primary', text: 'Save key' });
  const clear = el('button', { class: 'btn', text: 'Forget key', style: 'margin-left:8px' });

  async function verify(key) {
    // Ask the server directly rather than trusting the stored value: a wrong
    // key is the single most likely reason the console looks broken.
    try {
      const res = await fetch(apiUrl('/api/models'), {
        headers: key ? { Authorization: `Bearer ${key}` } : {},
      });
      return res.status !== 401;
    } catch {
      return false;
    }
  }

  save.addEventListener('click', async () => {
    const key = input.value.trim();
    setApiKey(key);
    status.textContent = 'Checking…';
    const ok = await verify(key);
    status.textContent = ok
      ? 'Key accepted. This device can reach JARVIS.'
      : 'Server rejected that key. Check JARVIS_API_KEY on the host.';
    status.style.color = ok ? 'var(--ok, #4ade80)' : 'var(--err, #f87171)';
    toast(ok ? 'Access key saved' : 'Key rejected', ok ? 'ok' : 'err');
  });

  clear.addEventListener('click', () => {
    setApiKey('');
    input.value = '';
    status.textContent = 'Key removed from this device.';
    status.style.color = 'var(--text-muted)';
    toast('Access key forgotten');
  });

  panel.appendChild(el('div', { class: 'default-card' }, [
    el('div', { class: 'default-card-label', text: 'Console API key' }),
    el('div', { class: 'default-card-provider', text: 'Required when JARVIS_API_KEY is set on the server. Stored only in this browser.' }),
    el('div', { style: 'margin-top:12px' }, [input]),
    status,
    el('div', { style: 'margin-top:12px' }, [save, clear]),
  ]));

  // Server URL — only needed inside the Android APK, where the WebView origin
  // (capacitor://localhost) has no backend. The web console and the PWA leave
  // this empty and keep calling the origin they were served from.
  const serverInput = el('input', {
    type: 'url',
    id: 'consoleServerUrl',
    placeholder: 'e.g. http://rebel.tail4ed6b0.ts.net:8000 (APK only)',
    value: getServerUrl(),
    autocomplete: 'off',
    spellcheck: 'false',
    style: 'width:100%;padding:10px 12px;border-radius:8px;border:1px solid var(--border);background:var(--surface-2);color:var(--text);font-family:ui-monospace,monospace;font-size:13px',
  });
  const serverStatus = el('div', {
    text: getServerUrl() ? `API calls go to ${getServerUrl()}.` : 'Empty: API calls go to this origin (web / PWA).',
    style: 'margin-top:8px;font-size:13px;color:var(--text-muted)',
  });
  const serverSave = el('button', { class: 'btn btn-primary', text: 'Save server URL' });
  serverSave.addEventListener('click', async () => {
    const url = serverInput.value.trim();
    if (url && !/^https?:\/\//i.test(url)) {
      serverStatus.textContent = 'URL must start with http:// or https://';
      serverStatus.style.color = 'var(--err, #f87171)';
      return;
    }
    setServerUrl(url);
    const base = getServerUrl();
    serverStatus.textContent = base ? `API calls go to ${base}.` : 'Empty: API calls go to this origin (web / PWA).';
    serverStatus.style.color = 'var(--text-muted)';
    toast(base ? 'Server URL saved' : 'Server URL cleared');
    // Re-verify the key against the (possibly new) target so a wrong URL
    // surfaces here instead of as empty panels later.
    status.textContent = 'Checking…';
    const ok = await verify(getApiKey());
    status.textContent = ok ? 'Key accepted. This device can reach JARVIS.' : 'Cannot reach JARVIS with the stored key at this URL.';
    status.style.color = ok ? 'var(--ok, #4ade80)' : 'var(--err, #f87171)';
  });
  panel.appendChild(el('div', { class: 'default-card' }, [
    el('div', { class: 'default-card-label', text: 'Server URL' }),
    el('div', { class: 'default-card-provider', text: 'Android APK only. The Tailscale URL of the host. Leave empty on web / PWA.' }),
    el('div', { style: 'margin-top:12px' }, [serverInput]),
    serverStatus,
    el('div', { style: 'margin-top:12px' }, [serverSave]),
  ]));

  host.appendChild(panel);

  // Report the current state on open, so a device that has never been set up
  // does not silently show an empty console.
  const ok = await verify(stored);
  if (!ok) {
    status.textContent = stored
      ? 'The stored key was rejected. Re-enter it.'
      : 'No key stored. JARVIS will refuse requests until one is added.';
    status.style.color = 'var(--err, #f87171)';
  } else if (stored) {
    status.style.color = 'var(--ok, #4ade80)';
  }
}

/* ── Shell ──────────────────────────────────────────────────────────────── */

let activeSection = 'model';

export function renderSettings() {
  const nav = $('#settingsNav');
  const host = $('#settingsContent');
  if (!nav || !host) return;

  nav.innerHTML = '';
  for (const s of sections) {
    nav.appendChild(el('button', {
      class: `settings-nav-item${activeSection === s.key ? ' active' : ''}`,
      'aria-current': activeSection === s.key ? 'page' : null,
      onclick: () => { activeSection = s.key; renderSettings(); },
    }, [
      el('span', { class: 'settings-nav-icon', text: s.icon }),
      el('span', { text: s.label }),
    ]));
  }

  host.innerHTML = '';
  const s = sections.find((x) => x.key === activeSection);
  if (s) s.render(host);
}

export function openSettings(startSection) {
  if (startSection) activeSection = startSection;
  const backdrop = $('#settingsModal');
  if (!backdrop) return;
  backdrop.classList.add('open');
  renderSettings();
  if (!state.modelsLoaded && !state.modelsLoading) {
    loadModels().then(() => {
      if (activeSection === 'model') renderSettings();
    });
  }
  if (!state.modelsLoaded) {
    api.getDefault().then((d) => { state.defaultModel = d.default || state.defaultModel; renderSettings(); }).catch(() => {});
  }
  setTimeout(() => $('#settingsClose')?.focus(), 40);
}

export function closeSettings() {
  $('#settingsModal')?.classList.remove('open');
}

export async function refreshCatalogue(force = false) {
  await loadModels(force);
  await loadCustomState();
  renderSettings();
}

/* ── Wiring ─────────────────────────────────────────────────────────────── */

export function initSettings() {
  $('#settingsClose')?.addEventListener('click', closeSettings);
  $('#settingsModal')?.addEventListener('click', (e) => {
    if (e.target.id === 'settingsModal') closeSettings();
  });
  $('#addModelCancel')?.addEventListener('click', () => $('#addModelModal')?.classList.remove('open'));
  $('#addModelCancelBtn')?.addEventListener('click', () => $('#addModelModal')?.classList.remove('open'));
  $('#addModelForm')?.addEventListener('submit', submitAddModel);
  $('#addModelModal')?.addEventListener('click', (e) => {
    if (e.target.id === 'addModelModal') e.target.classList.remove('open');
  });

  // Custom provider dialog
  $('#providerCancel')?.addEventListener('click', closeProviderDialog);
  $('#providerCancelBtn')?.addEventListener('click', closeProviderDialog);
  $('#providerForm')?.addEventListener('submit', submitProvider);
  $('#providerFetch')?.addEventListener('click', fetchProviderModels);
  $('#providerAddManual')?.addEventListener('click', () => {
    const input = $('#providerManualModel');
    const id = input.value.trim();
    if (!id) return;
    if (!pendingProviderModels.includes(id)) pendingProviderModels.push(id);
    input.value = '';
    drawPendingModels();
  });
  $('#providerManualModel')?.addEventListener('keydown', (e) => {
    if (e.key === 'Enter') {
      e.preventDefault();
      $('#providerAddManual')?.click();
    }
  });
  $('#providerModal')?.addEventListener('click', (e) => {
    if (e.target.id === 'providerModal') closeProviderDialog();
  });
  $('#filePreviewClose')?.addEventListener('click', () => $('#filePreviewModal')?.classList.remove('open'));
  $('#filePreviewModal')?.addEventListener('click', (e) => {
    if (e.target.id === 'filePreviewModal') e.target.classList.remove('open');
  });
}

export { openAddModelDialog, previewFile };