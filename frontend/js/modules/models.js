/* ===========================================================================
   Models Registry, Selection & Provider Capabilities Module
   =========================================================================== */

import { state } from "../state.js";
import { $, $$ } from "../utils/dom.js";
import { api, escapeHtml } from "../utils/api.js";
import { updateComposerEnabled } from "./chat.js";

export async function loadModels() {
  try {
    const data = await api("/api/models");
    const badge = $("#version-badge");
    if (badge) badge.textContent = data.version || "";
    state.activeModel = data.active_profile;
    state.modelGroups = data.groups || [];
    renderProviderTabs(state.modelGroups);
    renderModelGroups(state.modelGroups);
    renderActiveModel();
  } catch (e) {
    console.error("Failed to load models:", e);
  }
}

export function normalizeProvider(provider) {
  if (!provider) return "unknown";
  return provider.replace(/(-all|-free).*$/, "").toLowerCase();
}

export function providerLabel(key) {
  const labels = {
    all: "All",
    ollama: "Ollama",
    omni: "Omni",
    llamacpp: "llama.cpp",
    google: "Google",
    grok: "Grok",
    openrouter: "OpenRouter",
    together: "Together AI",
    cerebras: "Cerebras",
    openai: "OpenAI",
    anthropic: "Anthropic",
    configured: "Configured",
    unknown: "Other",
  };
  return labels[key] || key.replace(/(^|\s)\S/g, (m) => m.toUpperCase());
}

export function renderProviderTabs(groups) {
  const wrap = $("#model-provider-tabs");
  if (!wrap) return;
  const order = ["ollama", "omni", "llamacpp", "google", "grok", "openrouter", "together", "cerebras", "openai", "anthropic", "configured", "unknown"];
  const providers = new Set();
  groups.forEach((g) => providers.add(normalizeProvider(g.provider)));
  const sorted = Array.from(providers).filter((p) => p !== "all").sort((a, b) => {
    const ai = order.indexOf(a) === -1 ? order.length : order.indexOf(a);
    const bi = order.indexOf(b) === -1 ? order.length : order.indexOf(b);
    return ai - bi || a.localeCompare(b);
  });
  if (!sorted.length) {
    wrap.innerHTML = "";
    return;
  }
  if (!state.modelProvider || !sorted.includes(state.modelProvider)) {
    state.modelProvider = sorted[0];
  }
  wrap.innerHTML = "";
  sorted.forEach((provider) => {
    const tab = document.createElement("button");
    tab.type = "button";
    tab.className = `model-provider-tab${state.modelProvider === provider ? " selected" : ""}`;
    tab.textContent = providerLabel(provider);
    tab.dataset.provider = provider;
    tab.addEventListener("click", () => {
      state.modelProvider = provider;
      document.querySelectorAll(".model-provider-tab").forEach((x) => x.classList.toggle("selected", x === tab));
      renderModelGroups();
    });
    wrap.appendChild(tab);
  });
}

export function renderModelGroups(groups) {
  groups = groups || state.modelGroups || [];
  const provider = state.modelProvider;
  const search = String(state.modelSearch || "").trim().toLowerCase();
  groups = groups.filter((g) => {
    if (provider && normalizeProvider(g.provider) !== provider) {
      return false;
    }
    if (!search) {
      return true;
    }
    if (g.dynamic) {
      return true;
    }
    const label = String(g.label || "").toLowerCase();
    if (label.includes(search)) {
      return true;
    }
    return (g.models || []).some((m) => String(m.name || m.id || "").toLowerCase().includes(search));
  });

  const wrap = $("#model-groups");
  if (!wrap) return;
  wrap.innerHTML = "";
  if (!groups.length) {
    const none = document.createElement("div");
    none.className = "status off";
    none.textContent = "No models match the selected provider or search.";
    wrap.appendChild(none);
    return;
  }
  groups.forEach((g) => {
    const section = document.createElement("div");
    const label = document.createElement("div");
    label.className = "model-group-label";
    label.textContent = g.label;
    section.appendChild(label);

    (g.models || []).forEach((m) => {
      const opt = document.createElement("label");
      opt.className = "model-option";
      const checked = state.selectedModelId === m.id ? "checked" : "";
      opt.innerHTML = `
        <input type="radio" name="model" value="${m.id}" ${checked} />
        <span>${m.name}</span>
        <span class="status ${g.requires_key ? (g.key_set ? "ok" : "missing") : "ok"}">
          ${g.requires_key ? (g.key_set ? "available" : "requires API key") : "available"}
        </span>`;
      opt.querySelector("input").addEventListener("change", () => selectModel(m.id));
      section.appendChild(opt);
    });
    if ((g.models || []).length === 0 && !g.dynamic) {
      const none = document.createElement("div");
      none.className = "status off";
      none.style.fontSize = "12px";
      none.textContent = g.requires_key && !g.key_set
        ? "Add API key to enable"
        : "none available";
      section.appendChild(none);
    }
    if (g.dynamic) renderDynamicGroup(section, g);
    wrap.appendChild(section);
  });
}

export function renderDynamicGroup(section, g) {
  const prov = g.provider.replace("-all", "").replace("-free", "");
  const query = String(state.modelSearch || "").trim();
  const freeOnly = g.free || /\bfree\b/i.test(query);
  const listWrap = document.createElement("div");
  listWrap.className = "dynamic-model-list";
  section.appendChild(listWrap);
  
  if (!state.filters) {
    state.filters = { freeOnly: false, vision: false, reasoning: false, largeContext: false, tools: false };
  }

  const filterWrap = document.createElement("div");
  filterWrap.className = "filter-chips";
  filterWrap.innerHTML = `
    <button class="filter-chip${state.filters.freeOnly ? ' active' : ''}" data-filter="freeOnly">🆓 Free only</button>
    <button class="filter-chip${state.filters.reasoning ? ' active' : ''}" data-filter="reasoning">🧠 Reasoning</button>
    <button class="filter-chip${state.filters.largeContext ? ' active' : ''}" data-filter="largeContext">📏 Large ctx</button>
    <button class="filter-chip${state.filters.tools ? ' active' : ''}" data-filter="tools">🔧 Tools</button>
  `;
  section.insertBefore(filterWrap, listWrap);
  
  filterWrap.querySelectorAll('.filter-chip').forEach(btn => {
    btn.addEventListener('click', () => {
      const f = btn.dataset.filter;
      state.filters[f] = !state.filters[f];
      btn.classList.toggle('active', state.filters[f]);
      refresh(query);
    });
  });
  
  function refresh(q) {
    const trimmed = String(q || "").trim();
    const freeQuery = /\bfree\b/i.test(trimmed);
    const effectiveFree = g.free || freeQuery || state.filters.freeOnly;
    listWrap.innerHTML = "<div class='status off'>Loading models…</div>";
    const freeParam = effectiveFree ? "&free_only=true" : "";
    api(`/api/models/catalog?provider=${prov}&query=${encodeURIComponent(trimmed)}&limit=50${freeParam}`)
      .then((data) => {
        let models = data.models;
        if (state.filters.reasoning) {
          models = models.filter(m => m.id.toLowerCase().includes('reason') || m.id.toLowerCase().includes('o1') || m.id.toLowerCase().includes('r1') || m.id.toLowerCase().includes('qwen') || m.id.toLowerCase().includes('deepseek'));
        }
        if (state.filters.largeContext) {
          models = models.filter(m => (m.context_length || 0) >= 32000);
        }
        if (state.filters.tools) {
          models = models.filter(m => m.id.toLowerCase().includes('function') || m.id.toLowerCase().includes('tool') || m.id.toLowerCase().includes('instruct'));
        }
        
        listWrap.innerHTML = "";
        if (!models.length) { listWrap.innerHTML = "<div class='status off'>No models match.</div>"; return; }
        models.forEach((m) => {
          const opt = document.createElement("label");
          opt.className = "model-option";
          const checked = state.selectedModelId === `dyn:${m.id}` ? "checked" : "";
          const ctx = m.context_length ? " · " + (m.context_length / 1000) + "k ctx" : "";
          const freeTag = (m.pricing && String(m.pricing.prompt) === "0" && String(m.pricing.completion) === "0") ? " · free" : "";
          opt.innerHTML = `<input type="radio" name="model" value="dyn:${m.id}" data-backend="${prov}" data-model="${m.id}" ${checked} /><span>${m.id}</span><span class="status ok">${ctx}${freeTag}</span>`;
          
          const tooltip = document.createElement('div');
          tooltip.className = 'model-info-tooltip';
          tooltip.style.display = 'none';
          tooltip.innerHTML = buildModelTooltip(m, prov);
          opt.appendChild(tooltip);
          
          opt.querySelector("input").addEventListener("change", (ev) => selectDynamicModel(ev.target.dataset.backend, ev.target.dataset.model));
          listWrap.appendChild(opt);
        });
      })
      .catch((e) => { listWrap.innerHTML = `<div class='status missing'>Error: ${escapeHtml(e.message)}</div>`; });
  }
  refresh(query);
}

export function selectDynamicModel(backend, modelId, silent) {
  state.selectedModelId = `dyn:${modelId}`;
  $$('.model-option input').forEach((i) => { i.closest(".model-option").classList.toggle("selected", i.value === `dyn:${modelId}`); });
  api("/api/models/select", { method: "POST", body: JSON.stringify({ model_id: "dyn", backend, model: modelId }) })
    .then((res) => { state.activeModel = res.active || res.name || modelId; renderActiveModel(); updateComposerEnabled(); })
    .catch((e) => { if (!silent) alert("Could not select model: " + e.message); state.selectedModelId = null; });
}

export function buildModelTooltip(model, provider) {
  const ctx = model.context_length ? `${(model.context_length / 1000).toFixed(0)}k tokens` : 'Unknown';
  const maxOut = model.max_output_tokens ? `${(model.max_output_tokens / 1000).toFixed(0)}k tokens` : 'Unknown';
  const pricing = model.pricing || {};
  const isFree = String(pricing.prompt) === '0' && String(pricing.completion) === '0';
  const promptCost = pricing.prompt ? `$${Number(pricing.prompt).toFixed(6)}/1M` : 'N/A';
  const completionCost = pricing.completion ? `$${Number(pricing.completion).toFixed(6)}/1M` : 'N/A';
  
  const badges = [];
  if (isFree) badges.push('<span class="mi-badge free">Free</span>');
  if (model.id.toLowerCase().includes('reason') || model.id.toLowerCase().includes('o1') || model.id.toLowerCase().includes('r1')) {
    badges.push('<span class="mi-badge reasoning">Reasoning</span>');
  }
  if (model.id.toLowerCase().includes('instruct') || model.id.toLowerCase().includes('function') || model.id.toLowerCase().includes('tool')) {
    badges.push('<span class="mi-badge tools">Tools</span>');
  }
  
  return `
    <div class="mi-row"><span class="mi-label">Provider</span><span class="mi-value">${providerLabel(provider)}</span></div>
    <div class="mi-row"><span class="mi-label">Model ID</span><span class="mi-value">${escapeHtml(model.id)}</span></div>
    <div class="mi-row"><span class="mi-label">Context Window</span><span class="mi-value">${ctx}</span></div>
    <div class="mi-row"><span class="mi-label">Max Output</span><span class="mi-value">${maxOut}</span></div>
    <div class="mi-row"><span class="mi-label">Input Cost</span><span class="mi-value">${promptCost}</span></div>
    <div class="mi-row"><span class="mi-label">Output Cost</span><span class="mi-value">${completionCost}</span></div>
    <div class="mi-badges">${badges.join(' ')}</div>
  `;
}

export async function selectModel(modelId) {
  state.selectedModelId = modelId;
  $$('.model-option input').forEach((i) => {
    i.closest(".model-option").classList.toggle("selected", i.value === modelId);
  });
  try {
    const res = await api("/api/models/select", {
      method: "POST",
      body: JSON.stringify({ model_id: modelId }),
    });
    state.activeModel = res.active || res.name || modelId;
    renderActiveModel();
    updateComposerEnabled();
  } catch (e) {
    alert("Could not select model: " + e.message);
    state.selectedModelId = null;
  }
}

export function renderActiveModel() {
  const el = $("#active-model");
  if (!el) return;
  if (state.activeModel) {
    el.textContent = "model: " + state.activeModel;
    el.style.color = "var(--ok)";
  } else {
    el.textContent = "no model selected";
    el.style.color = "var(--text-dim)";
  }
}

export function startOCRHealthPoll(intervalMs = 15000) {
  updateOCRHealthUI();
  setInterval(updateOCRHealthUI, intervalMs);
  const el = $('#ocr-health');
  if (el) el.addEventListener('click', updateOCRHealthUI);
  
  const omniBtn = $('#activate-omni');
  if (omniBtn) omniBtn.addEventListener('click', async () => {
    try {
      await api('/api/models/select', { method: 'POST', body: JSON.stringify({ model_id: 'omni' }) });
      await loadModels();
      updateComposerEnabled();
      alert('Omni router activated');
    } catch (e) { alert('Could not activate Omni: ' + e.message); }
  });
}

export async function updateOCRHealthUI() {
  const el = $('#ocr-health');
  if (!el) return;
  
  const [remote, local] = await Promise.all([
    fetch('/api/ocr/remote_health').then(r => r.ok ? r.json() : { ok: false, error: `status ${r.status}` }).catch(e => ({ ok: false, error: e.message })),
    fetch('/api/ocr/local_health').then(r => r.ok ? r.json() : { ok: false, available: false }).catch(e => ({ ok: false, available: false, error: e.message }))
  ]);
  
  if (remote.ok) {
    el.style.color = 'var(--ok)';
    el.title = `Remote OCR: ok (${remote.status_code || ''})`;
    el.textContent = '●';
    el.dataset.source = 'remote';
  } else if (local.ok && local.available) {
    el.style.color = 'var(--accent)';
    el.title = `Local OCR: ${local.engine || 'tesseract'} (${local.languages?.length || 0} langs)`;
    el.textContent = '●';
    el.dataset.source = 'local';
  } else {
    el.style.color = 'var(--danger)';
    el.title = `OCR unavailable: ${remote.error || 'remote down'} / ${local.error || 'local not configured'}`;
    el.textContent = '○';
    el.dataset.source = 'none';
  }
}

export function loadDevState() {
  const unlocked = localStorage.getItem('jarvis_dev') === '1';
  state.devMode = !!unlocked;
}

export function showDevUnlock() {
  const pw = prompt('Enter developer password to unlock dev features:');
  if (!pw) return;
  if (pw === 'password') {
    state.devMode = true;
    state.devPassword = pw;
    localStorage.setItem('jarvis_dev', '1');
    alert('Developer mode unlocked');
  } else {
    alert('Incorrect password');
  }
}

export async function renderCapabilitiesMatrix() {
  const wrap = $("#capabilities-matrix");
  if (!wrap) return;
  wrap.innerHTML = "<div class='status off'>Loading capabilities matrix…</div>";
  try {
    const data = await api("/api/models/capabilities");
    const providers = data.providers || [];
    if (!providers.length) {
      wrap.innerHTML = "<div class='status off'>No capabilities matrix available.</div>";
      return;
    }
    let html = `
      <table>
        <thead>
          <tr>
            <th>Provider</th>
            <th>Type</th>
            <th>Vision</th>
            <th>Reasoning</th>
            <th>Function Calling</th>
            <th>Live Catalog</th>
            <th>Free Models</th>
          </tr>
        </thead>
        <tbody>`;
    providers.forEach((p) => {
      const vis = p.vision ? '<span class="cap-yes">✓</span>' : '<span class="cap-no">✕</span>';
      const reas = p.reasoning ? '<span class="cap-yes">✓</span>' : '<span class="cap-no">✕</span>';
      const fc = p.function_calling ? '<span class="cap-yes">✓</span>' : '<span class="cap-no">✕</span>';
      const cat = p.live_catalog ? '<span class="cap-yes">✓</span>' : '<span class="cap-no">✕</span>';
      const free = p.has_free_tier ? '<span class="cap-yes">✓</span>' : '<span class="cap-no">✕</span>';
      html += `
        <tr>
          <td><strong>${escapeHtml(p.name)}</strong></td>
          <td>${escapeHtml(p.type)}</td>
          <td>${vis}</td>
          <td>${reas}</td>
          <td>${fc}</td>
          <td>${cat}</td>
          <td>${free}</td>
        </tr>`;
    });
    html += `</tbody></table>`;
    wrap.innerHTML = html;
  } catch (e) {
    wrap.innerHTML = `<div class='status err'>Failed to load matrix: ${escapeHtml(e.message)}</div>`;
  }
}
