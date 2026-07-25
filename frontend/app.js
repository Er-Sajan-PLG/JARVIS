// JARVIS Web UI — frontend controller (vanilla JS, no build step).

const $ = (sel) => document.querySelector(sel);
const $$ = (sel) => Array.from(document.querySelectorAll(sel));

const state = {
  conversationId: null,
  activeModel: null,
  streaming: false,
  attachments: [], // { name, size }
  selectedModelId: null,
  devMode: false,
  devPassword: null,
  modelProvider: null,
  modelSearch: '',
  modelGroups: [],
  // Phase 5 filters
  filters: {
    freeOnly: false,
    vision: false,
    reasoning: false,
    largeContext: false,
    tools: false,
  },
  // Model info tooltip state
  modelTooltip: null,
  // Attachments Library
  lib: {
    currentFolder: "",   // slash path; "" = root
    tree: null,
    files: [],
  },
};

// ---------------------------------------------------------------------------
// Boot
// ---------------------------------------------------------------------------
async function boot() {
  await loadModels();
  await loadConversations();
  bindEvents();
  await ensureConversation();
  startOCRHealthPoll();
  updateComposerEnabled();
  loadDevState();
}

// ---------------------------------------------------------------------------
// API helpers
// ---------------------------------------------------------------------------
function getSecurityHeaders() {
  const headers = {};
  const keys = {
    'GOOGLE_API_KEY': 'google',
    'XAI_API_KEY': 'grok',
    'OPENROUTER_API_KEY': 'openrouter',
    'OPENAI_API_KEY': 'openai',
    'ANTHROPIC_API_KEY': 'anthropic',
    'GROQ_API_KEY': 'groq',
    'MISTRAL_API_KEY': 'mistral',
    'TOGETHER_API_KEY': 'together',
    'HUGGINGFACE_API_KEY': 'huggingface',
    'CEREBRAS_API_KEY': 'cerebras',
    'SAMBANOVA_API_KEY': 'sambanova',
    'NVIDIA_API_KEY': 'nvidia'
  };
  for (const [envVar, storageKey] of Object.entries(keys)) {
    const val = localStorage.getItem(`jarvis_key_${storageKey}`);
    if (val) {
      headers[`X-API-Key-${envVar}`] = val;
    }
  }
  return headers;
}

async function api(path, opts = {}) {
  const securityHeaders = getSecurityHeaders();
  const headers = { 
    "Content-Type": "application/json",
    ...securityHeaders,
    ...(opts.headers || {})
  };
  const res = await fetch(path, {
    ...opts,
    headers,
  });
  if (!res.ok) {
    let msg = `Request failed (${res.status})`;
    try { msg = (await res.json()).detail || msg; } catch (_) {}
    throw new Error(msg);
  }
  return res.json();
}

// ---------------------------------------------------------------------------
// Models
// ---------------------------------------------------------------------------
async function loadModels() {
  try {
    const data = await api("/api/models");
    $("#version-badge").textContent = data.version || "";
    state.activeModel = data.active_profile;
    state.modelGroups = data.groups || [];
    renderProviderTabs(state.modelGroups);
    renderModelGroups(state.modelGroups);
    renderActiveModel();
  } catch (e) {
    console.error(e);
  }
}

function normalizeProvider(provider) {
  if (!provider) return "unknown";
  return provider.replace(/(-all|-free).*$/, "").toLowerCase();
}

function providerLabel(key) {
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

function renderProviderTabs(groups) {
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

function renderModelGroups(groups) {
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

function renderDynamicGroup(section, g) {
  const prov = g.provider.replace("-all", "").replace("-free", "");
  const query = String(state.modelSearch || "").trim();
  const freeOnly = g.free || /\bfree\b/i.test(query);
  const placeholder = freeOnly ? "Search free " + prov + " models…" : "Search all " + prov + " models…";
  const listWrap = document.createElement("div");
  listWrap.className = "dynamic-model-list";
  section.appendChild(listWrap);
  
  // Add filter chips
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
        // Client-side filtering for capabilities not in API
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
          
          // Add tooltip with model info
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

function selectDynamicModel(backend, modelId, silent) {
  state.selectedModelId = `dyn:${modelId}`;
  $$('.model-option input').forEach((i) => { i.closest(".model-option").classList.toggle("selected", i.value === `dyn:${modelId}`); });
  api("/api/models/select", { method: "POST", body: JSON.stringify({ model_id: "dyn", backend, model: modelId }) })
    .then((res) => { state.activeModel = res.active || res.name || modelId; renderActiveModel(); updateComposerEnabled(); })
    .catch((e) => { if (!silent) alert("Could not select model: " + e.message); state.selectedModelId = null; });
}

function buildModelTooltip(model, provider) {
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

async function selectModel(modelId) {
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

function renderActiveModel() {
  const el = $("#active-model");
  if (state.activeModel) {
    el.textContent = "model: " + state.activeModel;
    el.style.color = "var(--ok)";
  } else {
    el.textContent = "no model selected";
    el.style.color = "var(--text-dim)";
  }
}

// ---------------------------------------------------------------------------
// Remote OCR health indicator
// ---------------------------------------------------------------------------
async function fetchOCRHealth() {
  try {
    const res = await fetch('/api/ocr/remote_health');
    if (!res.ok) throw new Error('health check failed');
    return await res.json();
  } catch (e) {
    return { ok: false, error: e.message };
  }
}

async function checkLocalOCR() {
  try {
    const res = await fetch('/api/ocr/local_health');
    if (!res.ok) return { ok: false, available: false };
    return await res.json();
  } catch (e) {
    return { ok: false, available: false, error: e.message };
  }
}

async function updateOCRHealthUI() {
  const el = $('#ocr-health');
  if (!el) return;
  
  const [remote, local] = await Promise.all([fetchOCRHealth(), checkLocalOCR()]);
  
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

function startOCRHealthPoll(intervalMs = 15000) {
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

// ---------------------------------------------------------------------------
// Developer mode (unlock + restart)
// ---------------------------------------------------------------------------
function loadDevState() {
  const unlocked = localStorage.getItem('jarvis_dev') === '1';
  state.devMode = !!unlocked;
}

function showDevUnlock() {
  const pw = prompt('Enter developer password to unlock dev features:');
  if (!pw) return;
  if (pw === 'password') {
    state.devMode = true;
    state.devPassword = pw;
    localStorage.setItem('jarvis_dev', '1');
    updateDevUI();
    alert('Developer mode unlocked');
  } else {
    alert('Incorrect password');
  }
}

function updateComposerEnabled() {
  const ready = !!state.activeModel;
  $("#send-btn").disabled = !ready;
  $("#input").disabled = !ready;
  if (!ready) {
    $("#input").placeholder = "Select a model in Settings to start chatting…";
  } else {
    $("#input").placeholder = "Message JARVIS…  (Enter to send, Shift+Enter for newline)";
  }
}

// ---------------------------------------------------------------------------
// Conversations
// ---------------------------------------------------------------------------
async function loadConversations(filter = "") {
  try {
    const data = await api("/api/conversations");
    const list = $("#conversation-list");
    list.innerHTML = "";
    const q = filter.toLowerCase().trim();
    data.conversations.forEach((c) => {
      const title = c.title || "";
      const preview = c.preview || "";
      if (q && !title.toLowerCase().includes(q) && !preview.toLowerCase().includes(q)) {
        return; // Skip non-matching
      }
      const item = document.createElement("div");
      item.className = "conv-item" + (c.id === state.conversationId ? " active" : "");
      item.dataset.id = c.id;
      item.innerHTML = `
        <span class="conv-del" title="Delete">🗑</span>
        <div class="conv-title">${escapeHtml(title)}</div>
        <div class="conv-preview">${escapeHtml(preview)}</div>`;
      item.addEventListener("click", (ev) => {
        if (ev.target.classList.contains("conv-del")) return;
        openConversation(c.id);
      });
      item.querySelector(".conv-del").addEventListener("click", (ev) => {
        ev.stopPropagation();
        deleteConversation(c.id);
      });
      list.appendChild(item);
    });
  } catch (e) { console.error(e); }
}

async function ensureConversation() {
  if (state.conversationId) return;
  const data = await api("/api/conversations", { method: "POST", body: JSON.stringify({}) });
  state.conversationId = data.id;
  await loadConversations();
}

async function openConversation(id) {
  state.conversationId = id;
  $("#chat-title").textContent = "Loading…";
  const data = await api(`/api/conversations/${id}`);
  renderMessages(data.messages);
  $$(".conv-item").forEach((el) => el.classList.toggle("active", el.dataset.id === id));
  // rename title from first user message
  const firstUser = data.messages.find((m) => m.role === "user");
  $("#chat-title").textContent = firstUser ? firstUser.content.slice(0, 40) : "Chat";
  updateComposerEnabled();
}

async function deleteConversation(id) {
  if (!confirm("Delete this conversation?")) return;
  await api(`/api/conversations/${id}`, { method: "DELETE" });
  if (state.conversationId === id) {
    state.conversationId = null;
    clearMessages();
  }
  await loadConversations();
  await ensureConversation();
}

function newChat() {
  state.conversationId = null;
  clearMessages();
  ensureConversation();
  $("#sidebar").classList.remove("open");
}

// ---------------------------------------------------------------------------
// Messages rendering
// ---------------------------------------------------------------------------
function clearMessages() {
  const btn = $("#scroll-bottom-btn");
  $("#messages").innerHTML = "";
  // Re-insert the persistent jump-to-bottom button that innerHTML wiped.
  if (btn) $("#messages").appendChild(btn);
  $("#empty-state")?.remove();
}

function renderMessages(messages) {
  clearMessages();
  if (!messages.length) return;
  messages.forEach((m, i) => appendMessage(m.role, m.content, false, m.pinned, i));
  scrollToBottom();
}

function appendMessage(role, content, isNew, pinned = false, messageIndex = -1) {
  const empty = $("#empty-state");
  if (empty) empty.remove();
  const wrap = document.createElement("div");
  wrap.className = `msg ${role}${pinned ? ' pinned' : ''}`;
  const avatar = role === "user" ? "🧑" : "🤖";
  const pinIcon = pinned ? "📌" : "📍";
  wrap.innerHTML = `
    <div class="msg-avatar">${avatar}</div>
    <div class="msg-body"></div>
    <button class="pin-btn" title="${pinned ? 'Unpin' : 'Pin'} message" data-index="${messageIndex}">${pinIcon}</button>`;
  const body = wrap.querySelector(".msg-body");
  body.innerHTML = renderMarkdown(content);
  
  // Add pin button handler
  const pinBtn = wrap.querySelector('.pin-btn');
  if (pinBtn) {
    pinBtn.addEventListener('click', async (ev) => {
      ev.stopPropagation();
      if (state.conversationId && messageIndex >= 0) {
        try {
          const res = await api(`/api/conversations/${state.conversationId}/pin`, {
            method: 'POST',
            body: JSON.stringify({ index: messageIndex })
          });
          if (res.pinned) {
            pinBtn.textContent = '📌';
            pinBtn.title = 'Unpin message';
            wrap.classList.add('pinned');
          } else {
            pinBtn.textContent = '📍';
            pinBtn.title = 'Pin message';
            wrap.classList.remove('pinned');
          }
        } catch (e) {
          console.error('Pin failed:', e);
        }
      }
    });
  }
  
  $("#messages").appendChild(wrap);
  scrollToBottom();
  return body;
}

function escapeHtml(s) {
  return String(s).replace(/[&<>"']/g, (c) => ({
    "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;",
  }[c]));
}

// Lightweight markdown: code fences, inline code, and basic line breaks.
function renderMarkdown(text) {
  if (!text) return "";
  // Escape first, then re-enable fenced/inline code formatting.
  const escaped = escapeHtml(text);
  // fenced code blocks
  let html = escaped.replace(/```(\w*)\n([\s\S]*?)```/g, (_, lang, code) =>
    `<pre><code>${code.replace(/\n$/, "")}</code></pre>`);
  // inline code
  html = html.replace(/`([^`]+?)`/g, "<code>$1</code>");
  // paragraphs / line breaks
  html = html.split(/\n{2,}/).map((p) =>
    p.includes("<pre>") ? p : `<p>${p.replace(/\n/g, "<br>")}</p>`
  ).join("");
  return html;
}

function isNearBottom(el, threshold = 80) {
  return el.scrollHeight - el.scrollTop - el.clientHeight <= threshold;
}

function scrollToBottom() {
  const el = $("#messages");
  // Only auto-scroll if the user is already near the bottom. This lets them
  // scroll up to read earlier content while tokens stream in, without being
  // yanked back down on every token.
  if (isNearBottom(el)) {
    el.scrollTop = el.scrollHeight;
  }
  updateScrollButton();
}

function updateScrollButton() {
  const el = $("#messages");
  const btn = $("#scroll-bottom-btn");
  if (!btn) return;
  const hidden = isNearBottom(el, 80);
  btn.classList.toggle("hidden", hidden);
}

function jumpToBottom() {
  const el = $("#messages");
  el.scrollTop = el.scrollHeight;
  updateScrollButton();
}

// ---------------------------------------------------------------------------
// Chat (SSE streaming)
// ---------------------------------------------------------------------------
async function sendMessage() {
  const input = $("#input");
  const text = input.value.trim();
  if (!text || state.streaming || !state.activeModel) return;

  const convId = state.conversationId || (await ensureConversation(), state.conversationId);
  appendMessage("user", text, true);
  input.value = "";
  autoGrow(input);

  // Collect any attached files and send them inline with this message, so the
  // chat always has the bytes it needs (no fragile global buffer).
  const attachments = state.attachments.slice();
  state.attachments = [];
  renderAttachments();

  // assistant placeholder
  const body = appendMessage("assistant", "", true);
  const wrap = body.closest(".msg");
  wrap.classList.add("thinking");
  body.textContent = "Thinking…";

  startStreaming(convId, text, attachments, body, wrap);
}

async function startStreaming(convId, text, attachments, body, wrap) {
  state.streaming = true;
  setStreamingUI(true);

  const assistantText = { value: "" };
  try {
    let res;
    if (attachments && attachments.length) {
      // Resolve any library-attachments (referencing a stored file id) into
      // real File objects before building the multipart request.
      const resolved = await Promise.all(attachments.map(async (a) => {
        if (a.file) return a;
        if (a.fileId) {
          const blob = await (await fetch(`/api/attachments/files/${a.fileId}`)).blob();
          return { name: a.name, file: new File([blob], a.name, { type: a.mime || "application/octet-stream" }) };
        }
        return a;
      }));
      // Multipart: include the attached files directly in the chat request.
      const fd = new FormData();
      fd.append("conversation_id", convId);
      fd.append("message", text);
      resolved.forEach((a) => fd.append("attachments", a.file, a.name));
      res = await fetch("/api/chat", { method: "POST", body: fd });
    } else {
      res = await fetch("/api/chat", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ conversation_id: convId, message: text }),
      });
    }
    if (!res.ok) throw new Error("Chat request failed");

    const reader = res.body.getReader();
    const decoder = new TextDecoder();
    let buffer = "";

    while (true) {
      const { done, value } = await reader.read();
      if (done) break;
      buffer += decoder.decode(value, { stream: true });
      const events = buffer.split("\n\n");
      buffer = events.pop();
      for (const raw of events) {
        const ev = parseSSE(raw);
        if (!ev) continue;
        handleStreamEvent(ev, assistantText, body, wrap);
      }
    }
  } catch (e) {
    wrap.classList.remove("thinking");
    body.innerHTML = `<span style="color:var(--danger)">Error: ${escapeHtml(e.message)}</span>`;
  } finally {
    state.streaming = false;
    setStreamingUI(false);
    await loadConversations();
  }
}

function parseSSE(raw) {
  const lines = raw.split("\n");
  let event = "message", data = "";
  for (const line of lines) {
    if (line.startsWith("event:")) event = line.slice(6).trim();
    else if (line.startsWith("data:")) data += line.slice(5).trim();
  }
  if (!data) return null;
  try { return { event, data: JSON.parse(data) }; }
  catch { return { event, data: {} }; }
}

function handleStreamEvent(ev, assistantText, body, wrap) {
  if (ev.event === "token") {
    wrap.classList.remove("thinking");
    assistantText.value += ev.data.token;
    body.innerHTML = renderMarkdown(assistantText.value);
    scrollToBottom();
  } else if (ev.event === "memory") {
    // no-op visually; memory stored server-side
  } else if (ev.event === "stopped") {
    wrap.classList.remove("thinking");
    body.innerHTML = renderMarkdown(assistantText.value + "\n\n_(stopped)_");
  } else if (ev.event === "done") {
    wrap.classList.remove("thinking");
  } else if (ev.event === "error") {
    wrap.classList.remove("thinking");
    body.innerHTML = `<span style="color:var(--danger)">${escapeHtml(ev.data.message)}</span>`;
  }
}

function setStreamingUI(on) {
  $("#stop-btn").classList.toggle("hidden", !on);
  $("#send-btn").classList.toggle("hidden", on);
  $("#input").disabled = on || !state.activeModel;
}

async function stopGeneration() {
  try { await api("/api/stop", { method: "POST" }); } catch (e) {}
}

// ---------------------------------------------------------------------------
// Files
// ---------------------------------------------------------------------------
async function uploadFiles(fileList) {
  for (const file of fileList) {
    // Keep the live File object so we can stream its bytes with the chat
    // request. The chip just shows name/size for feedback.
    state.attachments.push({ name: file.name, size: file.size, file });
  }
  renderAttachments();
}

function renderAttachments() {
  const wrap = $("#attachments");
  wrap.innerHTML = "";
  state.attachments.forEach((a, i) => {
    const chip = document.createElement("span");
    chip.className = "chip";
    chip.innerHTML = `📄 ${escapeHtml(a.name)} <button title="Remove">✕</button>`;
    chip.querySelector("button").addEventListener("click", () => {
      state.attachments.splice(i, 1);
      renderAttachments();
    });
    wrap.appendChild(chip);
  });
}

async function clearFilesOnServer() {
  try { await api("/api/files", { method: "DELETE" }); } catch (_) {}
}

// ===========================================================================
// Attachments Library (persistent files organized into folders/subfolders)
// ===========================================================================
function iconForMime(mime, name) {
  const m = (mime || "").toLowerCase();
  const n = (name || "").toLowerCase();
  if (m.includes("pdf")) return "📕";
  if (m.includes("image")) return "🖼";
  if (m.includes("audio")) return "🎵";
  if (m.includes("video")) return "🎬";
  if (m.includes("zip") || m.includes("compressed") || n.endsWith(".zip")) return "🗜";
  if (n.endsWith(".md") || n.endsWith(".markdown")) return "📝";
  if (n.endsWith(".json") || n.endsWith(".yaml") || n.endsWith(".yml")) return "⚙";
  if (n.endsWith(".py") || n.endsWith(".js") || n.endsWith(".ts") || n.endsWith(".go") ||
      n.endsWith(".c") || n.endsWith(".cpp") || n.endsWith(".rs")) return "💻";
  if (n.endsWith(".csv") || n.endsWith(".xlsx") || n.endsWith(".xls")) return "📊";
  if (n.endsWith(".tex") || n.includes("latex")) return "∑";
  return "📄";
}

function formatSize(bytes) {
  if (!bytes && bytes !== 0) return "";
  if (bytes < 1024) return bytes + " B";
  if (bytes < 1024 * 1024) return (bytes / 1024).toFixed(1) + " KB";
  return (bytes / (1024 * 1024)).toFixed(1) + " MB";
}

async function openAttachments() {
  $("#attachments-modal").classList.remove("hidden");
  state.lib.currentFolder = "";
  await libRefreshTree();
  await libLoadFiles("");
  renderBreadcrumb();
}

function closeAttachments() {
  $("#attachments-modal").classList.add("hidden");
  $("#attachments-search").value = "";
}

async function libRefreshTree() {
  try {
    const data = await api("/api/attachments/tree");
    state.lib.tree = data.tree;
    renderFolderTree();
  } catch (e) { console.error(e); }
}

function renderFolderTree() {
  const wrap = $("#folder-tree");
  wrap.innerHTML = "";
  const root = state.lib.tree;
  const node = document.createElement("div");
  node.className = "folder-node";
  const row = document.createElement("div");
  row.className = "folder-node-row" + (state.lib.currentFolder === "" ? " active" : "");
  const count = root ? root.file_count || 0 : 0;
  row.innerHTML = `<span>📂</span><span class="fname">All files</span><span class="fcount">${count}</span>`;
  row.addEventListener("click", () => libNavigate(""));
  node.appendChild(row);
  if (root && root.children) {
    root.children.forEach((c) => node.appendChild(renderFolderNode(c)));
  }
  wrap.appendChild(node);
}

function renderFolderNode(f) {
  const node = document.createElement("div");
  node.className = "folder-node";
  const row = document.createElement("div");
  const isActive = state.lib.currentFolder === f.path;
  row.className = "folder-node-row" + (isActive ? " active" : "");
  row.innerHTML = `
    <span>📁</span>
    <span class="fname">${escapeHtml(f.name)}</span>
    <span class="fcount">${f.file_count}</span>
    <span class="fmenu" title="Delete folder">🗑</span>`;
  row.addEventListener("click", (ev) => {
    if (ev.target.classList.contains("fmenu")) return;
    libNavigate(f.path);
  });
  row.querySelector(".fmenu").addEventListener("click", (ev) => {
    ev.stopPropagation();
    libDeleteFolder(f.path);
  });
  node.appendChild(row);
  if (f.children && f.children.length) {
    const kids = document.createElement("div");
    kids.className = "folder-children";
    f.children.forEach((c) => kids.appendChild(renderFolderNode(c)));
    node.appendChild(kids);
  }
  return node;
}

async function libNavigate(path) {
  state.lib.currentFolder = path;
  renderFolderTree();
  renderBreadcrumb();
  await libLoadFiles(path);
}

function renderBreadcrumb() {
  const bc = $("#folder-breadcrumb");
  bc.innerHTML = "";
  const parts = (state.lib.currentFolder || "").split("/").filter(Boolean);
  const home = document.createElement("span");
  home.className = "crumb" + (parts.length === 0 ? " crumb-current" : "");
  home.textContent = "Library";
  home.addEventListener("click", () => libNavigate(""));
  bc.appendChild(home);
  let acc = "";
  parts.forEach((p, i) => {
    acc = acc ? acc + "/" + p : p;
    const sep = document.createElement("span");
    sep.className = "sep";
    sep.textContent = "/";
    bc.appendChild(sep);
    const crumb = document.createElement("span");
    const last = i === parts.length - 1;
    crumb.className = "crumb" + (last ? " crumb-current" : "");
    crumb.textContent = p;
    if (!last) crumb.addEventListener("click", () => libNavigate(acc));
    bc.appendChild(crumb);
  });
}

async function libLoadFiles(folder) {
  try {
    const data = await api("/api/attachments/files?folder=" + encodeURIComponent(folder || ""));
    state.lib.files = data.files;
    renderFiles(data.files);
  } catch (e) {
    $("#attachments-files").innerHTML = `<div class="empty-folder">Error: ${escapeHtml(e.message)}</div>`;
  }
}

function renderFiles(files) {
  const wrap = $("#attachments-files");
  wrap.innerHTML = "";
  if (!files.length) {
    wrap.innerHTML = `<div class="empty-folder">No files here yet. Use <b>Upload</b> or drop files anywhere in this modal.</div>`;
    return;
  }
  files.forEach((f) => {
    const row = document.createElement("div");
    row.className = "file-row";
    const meta = [formatSize(f.size)];
    if (f.folder) meta.push("📁 " + f.folder);
    row.innerHTML = `
      <span class="file-icon">${iconForMime(f.mime, f.name)}</span>
      <div class="file-info">
        <div class="file-name" title="${escapeHtml(f.name)}">${escapeHtml(f.name)}</div>
        <div class="file-meta">${meta.join("  ·  ")}</div>
      </div>
      <div class="file-actions">
        <button class="mini-btn attach" title="Attach to current chat">Attach</button>
        <button class="mini-btn danger" title="Delete file">Delete</button>
      </div>`;
    row.querySelector(".attach").addEventListener("click", () => libAttachFile(f));
    row.querySelector(".danger").addEventListener("click", () => libDeleteFile(f));
    wrap.appendChild(row);
  });
}

function libAttachFile(f) {
  // Avoid duplicates by file id.
  if (state.attachments.some((a) => a.fileId === f.id)) return;
  state.attachments.push({ name: f.name, size: f.size, fileId: f.id, mime: f.mime });
  renderAttachments();
  // Give quick visual feedback that it landed in the composer.
  const chip = Array.from(document.querySelectorAll("#attachments .chip")).pop();
  if (chip) {
    chip.style.outline = "2px solid var(--ok)";
    setTimeout(() => { chip.style.outline = ""; }, 600);
  }
}

async function libDeleteFile(f) {
  if (!confirm(`Delete "${f.name}"? This cannot be undone.`)) return;
  try {
    await api("/api/attachments/files/" + f.id, { method: "DELETE" });
    await libRefreshTree();
    await libLoadFiles(state.lib.currentFolder);
  } catch (e) { alert("Error: " + e.message); }
}

async function libCreateFolder() {
  // Show the inline new-folder input instead of a native prompt() (which some
  // browsers/contexts block). Pre-fill the parent label from the current folder.
  const parent = state.lib.currentFolder || "";
  $("#nf-parent").textContent = parent ? parent : "Library";
  $("#new-folder-input").value = "";
  $("#new-folder-row").classList.remove("hidden");
  $("#new-folder-input").focus();
}

async function libConfirmFolder() {
  const name = $("#new-folder-input").value.trim();
  if (!name) { $("#new-folder-input").focus(); return; }
  const base = state.lib.currentFolder || "";
  const path = base ? base + "/" + name : name;
  $("#new-folder-row").classList.add("hidden");
  try {
    await api("/api/attachments/folders", {
      method: "POST",
      body: JSON.stringify({ path }),
    });
    await libRefreshTree();
    // Jump into the folder we just created so the user sees it immediately.
    await libNavigate(path);
  } catch (e) { alert("Error: " + e.message); }
}

function libCancelFolder() {
  $("#new-folder-row").classList.add("hidden");
}

async function libDeleteFolder(path) {
  if (!confirm(`Delete folder "${path}" and all its files?`)) return;
  try {
    await api("/api/attachments/folders?path=" + encodeURIComponent(path) + "&recursive=true", { method: "DELETE" });
    if (state.lib.currentFolder === path || state.lib.currentFolder.startsWith(path + "/")) {
      state.lib.currentFolder = "";
      renderBreadcrumb();
    }
    await libRefreshTree();
    await libLoadFiles(state.lib.currentFolder);
  } catch (e) { alert("Error: " + e.message); }
}

async function libUploadFiles(fileList) {
  const folder = state.lib.currentFolder || "";
  for (const file of fileList) {
    const fd = new FormData();
    fd.append("folder", folder);
    fd.append("file", file, file.name);
    try {
      await fetch("/api/attachments/files", { method: "POST", body: fd });
    } catch (e) { console.error(e); }
  }
  await libRefreshTree();
  await libLoadFiles(folder);
}

let libSearchDebounce;
async function libSearch(q) {
  if (!q.trim()) { await libLoadFiles(state.lib.currentFolder); return; }
  try {
    const data = await api("/api/attachments/search?query=" + encodeURIComponent(q));
    renderFiles(data.files);
  } catch (e) { console.error(e); }
}

function renderCapabilitiesMatrix(providers) {
  const wrap = $("#capabilities-matrix");
  const headers = [
    { key: 'provider', label: 'Provider' },
    { key: 'name', label: 'Name' },
    { key: 'openai_compatible', label: 'OpenAI Compatible' },
    { key: 'reasoning', label: 'Reasoning' },
    { key: 'code_generation', label: 'Code Gen' },
    { key: 'stem', label: 'STEM' },
    { key: 'documentation', label: 'Docs' },
    { key: 'realtime', label: 'Realtime' },
    { key: 'has_free_models', label: 'Free Models' },
    { key: 'context_window', label: 'Context' },
    { key: 'max_output', label: 'Max Out' },
    { key: 'status', label: 'Status' },
    { key: 'has_key', label: 'Has Key' },
  ];
  
  const yes = '<span class="cap-yes">✓</span>';
  const no = '<span class="cap-no">✗</span>';
  
  let html = '<table><thead><tr>';
  headers.forEach(h => html += `<th>${h.label}</th>`);
  html += '</tr></thead><tbody>';
  
  providers.forEach(p => {
    html += '<tr>';
    html += `<td>${p.provider}</td>`;
    html += `<td>${p.name}</td>`;
    html += `<td>${p.openai_compatible ? yes : no}</td>`;
    html += `<td>${p.reasoning ? yes : no}</td>`;
    html += `<td>${p.code_generation ? yes : no}</td>`;
    html += `<td>${p.stem ? yes : no}</td>`;
    html += `<td>${p.documentation ? yes : no}</td>`;
    html += `<td>${p.realtime ? yes : no}</td>`;
    html += `<td>${p.has_free_models ? yes : no}</td>`;
    html += `<td>${p.context_window ? (p.context_window / 1000) + 'k' : 'N/A'}</td>`;
    html += `<td>${p.max_output ? (p.max_output / 1000) + 'k' : 'N/A'}</td>`;
    html += `<td><span class="status ${p.status === 'ok' ? 'ok' : p.status === 'missing' ? 'missing' : 'off'}">${p.status}</span></td>`;
    html += `<td>${p.has_key ? yes : no}</td>`;
    html += '</tr>';
  });
  
  html += '</tbody></table>';
  wrap.innerHTML = html;
}


// ===========================================================================
// Research Papers (RAG knowledge base)
// ===========================================================================
// Tracks the last RAG answer + sources so the "Save finding" button can persist
// the highlighted text into long-term memory via /api/papers/findings.
const papersState = {
  folder: "",            // selected folder scope ("") = all
  folders: [],           // known folder names from /api/papers/folders
  documents: [],         // ingested docs from /api/papers
  lastAnswer: null,      // { answer, sources }
  pendingTitle: "",      // title to use on the next ingest
};

async function openPapers() {
  $("#papers-modal").classList.remove("hidden");
  await papersLoadFolders();
  papersLoadDocuments();
  papersRenderFolderSelect();
  // Reset any prior answer.
  papersState.lastAnswer = null;
  $("#papers-answer").classList.add("hidden");
}

function closePapers() {
  $("#papers-modal").classList.add("hidden");
  $("#papers-upload-row").classList.add("hidden");
  $("#papers-file-input").value = "";
}

async function papersLoadFolders() {
  try {
    const data = await api("/api/papers/folders");
    papersState.folders = data.folders || [];
  } catch (e) {
    console.error(e);
    papersState.folders = [];
  }
}

function papersRenderFolderSelect() {
  const sel = $("#papers-folder");
  const current = papersState.folder;
  sel.innerHTML = `<option value="">All folders</option>`;
  papersState.folders.forEach((f) => {
    const opt = document.createElement("option");
    opt.value = f;
    opt.textContent = f;
    if (f === current) opt.selected = true;
    sel.appendChild(opt);
  });
  // Make sure the pre-created "Materials Science" folder is always offered,
  // even if the server list is momentarily empty.
  if (!papersState.folders.includes("Materials Science")) {
    const opt = document.createElement("option");
    opt.value = "Materials Science";
    opt.textContent = "Materials Science";
    sel.appendChild(opt);
  }
  const label = $("#papers-scope-label");
  if (label) label.textContent = current ? `“${current}”` : "all folders";
}

function papersLoadDocuments() {
  const folder = papersState.folder || "";
  const url = "/api/papers" + (folder ? "?folder=" + encodeURIComponent(folder) : "");
  api(url)
    .then((data) => {
      papersState.documents = data.documents || [];
      papersRenderDocuments();
    })
    .catch((e) => {
      $("#papers-list").innerHTML = `<div class="empty-folder">Error: ${escapeHtml(e.message)}</div>`;
    });
}

function papersRenderDocuments() {
  const wrap = $("#papers-list");
  wrap.innerHTML = "";
  const docs = papersState.documents;
  if (!docs.length) {
    wrap.innerHTML = `<div class="empty-folder">No papers ingested yet. Upload a PDF to get started.</div>`;
    return;
  }
  docs.forEach((d) => {
    const row = document.createElement("div");
    row.className = "papers-doc";
    row.innerHTML = `
      <span class="papers-doc-icon">📄</span>
      <div class="papers-doc-info">
        <div class="papers-doc-title">${escapeHtml(d.title || d.filename)}</div>
        <div class="papers-doc-meta">${escapeHtml(d.filename)} · ${d.chunk_count} chunks${d.folder ? " · 📁 " + escapeHtml(d.folder) : ""}</div>
      </div>
      <div class="papers-doc-actions">
        <button class="mini-btn danger" title="Delete paper">Delete</button>
      </div>`;
    row.querySelector(".danger").addEventListener("click", () => papersDeleteDocument(d.doc_id));
    wrap.appendChild(row);
  });
}

async function papersDeleteDocument(docId) {
  if (!confirm("Delete this paper from the knowledge base?")) return;
  try {
    await api("/api/papers/" + encodeURIComponent(docId), { method: "DELETE" });
    papersLoadDocuments();
  } catch (e) { alert("Error: " + e.message); }
}

// --- Upload / ingest ---
function papersShowUpload() {
  $("#papers-title-input").value = papersState.pendingTitle || "";
  $("#papers-upload-row").classList.remove("hidden");
  $("#papers-title-input").focus();
}

function papersCancelUpload() {
  $("#papers-upload-row").classList.add("hidden");
  $("#papers-file-input").value = "";
}

async function papersConfirmUpload() {
  const fileInput = $("#papers-file-input");
  if (!fileInput.files || !fileInput.files.length) {
    // No file picked yet — open the picker.
    fileInput.click();
    return;
  }
  const file = fileInput.files[0];
  if (!file.name.toLowerCase().endsWith(".pdf")) {
    alert("Only PDF files are supported.");
    return;
  }
  const folder = papersState.folder || "Materials Science";
  const title = $("#papers-title-input").value.trim();
  const fd = new FormData();
  fd.append("file", file, file.name);
  fd.append("folder", folder);
  if (title) fd.append("title", title);

  const btn = $("#papers-upload-confirm");
  btn.disabled = true;
  btn.textContent = "Ingesting…";
  try {
    await fetch("/api/papers/ingest", { method: "POST", body: fd });
    papersCancelUpload();
    papersLoadDocuments();
  } catch (e) {
    alert("Ingestion failed: " + e.message);
  } finally {
    btn.disabled = false;
    btn.textContent = "Ingest";
  }
}

// --- Ask within a folder (RAG) ---
async function papersAsk() {
  const query = $("#papers-query").value.trim();
  if (!query) return;
  const folder = papersState.folder || null;
  const btn = $("#papers-ask-btn");
  btn.disabled = true;

  const answerBody = $("#papers-answer-body");
  $("#papers-answer").classList.remove("hidden");
  answerBody.innerHTML = `<span class="papers-thinking">Searching papers…</span>`;
  $("#papers-sources").innerHTML = "";

  try {
    const data = await api("/api/papers/query", {
      method: "POST",
      body: JSON.stringify({ query, folder, limit: 8 }),
    });
    papersState.lastAnswer = data;
    answerBody.innerHTML = renderMarkdown(data.answer || "_No answer._");
    papersRenderSources(data.sources || []);
  } catch (e) {
    answerBody.innerHTML = `<span style="color:var(--danger)">Error: ${escapeHtml(e.message)}</span>`;
  } finally {
    btn.disabled = false;
  }
}

// Render retrieved chunks as clickable [title, p.X] citation chips.
function papersRenderSources(sources) {
  const wrap = $("#papers-sources");
  wrap.innerHTML = "";
  if (!sources.length) {
    wrap.innerHTML = `<div class="papers-no-sources">No matching excerpts in this scope.</div>`;
    return;
  }
  sources.forEach((s, i) => {
    const chip = document.createElement("div");
    chip.className = "papers-source-chip";
    const title = s.title || s.filename || "unknown";
    chip.innerHTML = `
      <span class="ps-index">${i + 1}</span>
      <span class="ps-cite">[${escapeHtml(title)}, p.${escapeHtml(String(s.page))}]</span>
      <span class="ps-text">${escapeHtml((s.text || "").slice(0, 160))}${(s.text || "").length > 160 ? "…" : ""}</span>`;
    wrap.appendChild(chip);
  });
}

// --- Save finding ---
async function papersSaveFinding() {
  const last = papersState.lastAnswer;
  if (!last) return;
  // Default the finding text to the answer; the user can edit before saving via
  // a prompt is avoided (some contexts block it) so we send the answer text and
  // cite the first source as the provenance.
  const first = (last.sources && last.sources[0]) || {};
  const text = (last.answer || "").trim();
  if (!text) { alert("Nothing to save yet — ask a question first."); return; }
  const sourceMeta = {
    source_title: first.title || first.filename || "",
    page: first.page || 0,
    doc_id: first.doc_id || "",
  };
  try {
    await api("/api/papers/findings", {
      method: "POST",
      body: JSON.stringify({ text, source_meta: sourceMeta }),
    });
    const btn = $("#papers-save-finding");
    const original = btn.textContent;
    btn.textContent = "✓ Saved";
    setTimeout(() => { btn.textContent = original; }, 1200);
  } catch (e) {
    alert("Could not save finding: " + e.message);
  }
}

// ---------------------------------------------------------------------------
// Settings
// ---------------------------------------------------------------------------
async function switchSettingsTab(tabName) {
  $$(".settings-tab").forEach((tab) => {
    tab.classList.toggle("selected", tab.dataset.tab === tabName);
  });
  $$(".settings-tab-panel").forEach((panel) => {
    panel.classList.toggle("hidden", panel.id !== `settings-tab-${tabName}`);
  });

  // Load capabilities matrix when capabilities tab is shown
  if (tabName === "capabilities") {
    const wrap = $("#capabilities-matrix");
    if (!wrap.innerHTML.trim()) {
      wrap.innerHTML = "<div class='status off'>Loading…</div>";
      try {
        const data = await api("/api/models/capabilities");
        renderCapabilitiesMatrix(data.providers);
      } catch (e) {
        wrap.innerHTML = `<div class='status missing'>Error: ${escapeHtml(e.message)}</div>`;
      }
    }
  }
}

async function openSettings() {
  try {
    await api("/api/settings");
    // Only show key status, never echo secrets back.
    const status = $("#settings-status");
    status.className = "settings-status";
    status.textContent = "";
  } catch (e) {}
  switchSettingsTab("models");
  $("#settings-modal").classList.remove("hidden");
}

async function saveSettings() {
  const keys = {
    google: $("#google-key").value,
    grok: $("#xai-key").value,
    openrouter: $("#openrouter-key").value,
    openai: $("#openai-key").value,
    anthropic: $("#anthropic-key").value,
    together: $("#together-key").value,
    cerebras: $("#cerebras-key").value,
    groq: $("#groq-key").value,
    sambanova: $("#sambanova-key").value,
    nvidia: $("#nvidia-key").value,
  };

  const status = $("#settings-status");
  status.className = "settings-status";
  status.textContent = "Saving locally…";

  try {
    for (const [provider, val] of Object.entries(keys)) {
      if (val) {
        localStorage.setItem(`jarvis_key_${provider}`, val);
      } else {
        localStorage.removeItem(`jarvis_key_${provider}`);
      }
    }
    
    // Notify backend to rebuild switcher (it might still use dev keys if no user key provided)
    await api("/api/settings", { 
      method: "POST", 
      body: JSON.stringify({ use_developer_keys: $("#use-dev-keys")?.checked }) 
    });

    status.className = "settings-status ok";
    status.textContent = "Saved to browser storage.";
    await loadModels();
    setTimeout(() => $("#settings-modal").classList.add("hidden"), 600);
  } catch (e) {
    status.className = "settings-status err";
    status.textContent = "Error: " + e.message;
  }
}

// ---------------------------------------------------------------------------
// Memories
// ---------------------------------------------------------------------------
async function openMemories() {
  const list = $("#memories-list");
  list.innerHTML = "<div class='status off'>Loading…</div>";
  $("#memories-modal").classList.remove("hidden");
  try {
    const data = await api("/api/memories");
    list.innerHTML = "";
    if (!data.memories.length) {
      list.innerHTML = "<div class='status off'>No memories stored yet.</div>";
      return;
    }
    data.memories.forEach((m) => {
      const item = document.createElement("div");
      item.className = "memory-item";
      item.innerHTML = `
        <div class="memory-meta">${escapeHtml(m.category)} · ${escapeHtml(m.memory_type)} · used ${m.access_count}×</div>
        <div class="memory-value">${escapeHtml(m.value)}</div>`;
      list.appendChild(item);
    });
  } catch (e) {
    list.innerHTML = `<div class='status missing'>Error: ${escapeHtml(e.message)}</div>`;
  }
}

// ---------------------------------------------------------------------------
// Events
// ---------------------------------------------------------------------------
function bindEvents() {
  $("#send-btn").addEventListener("click", sendMessage);
  $("#stop-btn").addEventListener("click", stopGeneration);
  $("#new-chat-btn").addEventListener("click", newChat);
  $("#settings-btn").addEventListener("click", openSettings);
  $("#memories-btn").addEventListener("click", openMemories);
  $("#attachments-btn").addEventListener("click", openAttachments);
  $("#save-settings").addEventListener("click", saveSettings);
  $("#toggle-sidebar").addEventListener("click", () => $("#sidebar").classList.toggle("open"));

  const input = $("#input");
  input.addEventListener("keydown", (e) => {
    if (e.key === "Enter" && !e.shiftKey) {
      e.preventDefault();
      sendMessage();
    }
  });
  input.addEventListener("input", () => autoGrow(input));

  $("#attach-btn").addEventListener("click", () => $("#file-input").click());
  $("#file-input").addEventListener("change", (e) => {
    if (e.target.files.length) uploadFiles(e.target.files);
    e.target.value = "";
  });
  // Prevent the browser from navigating when a file is dropped onto the
  // composer, and route the drop through the same upload path.
  const dropZone = $("#chat-input-area") || $("#input").closest(".composer") || document.body;
  dropZone.addEventListener("dragover", (e) => { e.preventDefault(); });
  dropZone.addEventListener("drop", (e) => {
    e.preventDefault();
    if (e.dataTransfer && e.dataTransfer.files.length) uploadFiles(e.dataTransfer.files);
  });

  // close modals
  $$("[data-close]").forEach((el) => {
    el.addEventListener("click", () => {
      const which = el.dataset.close;
      $(`#${which}-modal`).classList.add("hidden");
      if (which === "attachments") $("#attachments-search").value = "";
    });
  });

  // Attachments Library wiring
  $("#new-folder-btn").addEventListener("click", libCreateFolder);
  $("#new-folder-confirm").addEventListener("click", libConfirmFolder);
  $("#new-folder-cancel").addEventListener("click", libCancelFolder);
  $("#new-folder-input").addEventListener("keydown", (e) => {
    if (e.key === "Enter") { e.preventDefault(); libConfirmFolder(); }
    if (e.key === "Escape") { e.preventDefault(); libCancelFolder(); }
  });
  $("#upload-lib-btn").addEventListener("click", () => $("#lib-file-input").click());
  $("#lib-file-input").addEventListener("change", (e) => {
    if (e.target.files.length) libUploadFiles(e.target.files);
    e.target.value = "";
  });
  $("#attachments-search").addEventListener("input", (e) => {
    clearTimeout(libSearchDebounce);
    libSearchDebounce = setTimeout(() => libSearch(e.target.value), 200);
  });
  // Drag-and-drop uploads anywhere inside the library modal.
  const libModal = $("#attachments-modal");
  libModal.addEventListener("dragover", (e) => { e.preventDefault(); });
  libModal.addEventListener("drop", (e) => {
    e.preventDefault();
    if (e.dataTransfer && e.dataTransfer.files.length) libUploadFiles(e.dataTransfer.files);
  });

  // "Jump to latest" button (shown only when scrolled up during streaming).
  $("#scroll-bottom-btn").addEventListener("click", jumpToBottom);
  $("#messages").addEventListener("scroll", updateScrollButton);

  // Research Papers wiring
  $("#papers-btn").addEventListener("click", openPapers);
  $("#papers-folder").addEventListener("change", (e) => {
    papersState.folder = e.target.value;
    papersRenderFolderSelect();
    papersLoadDocuments();
    papersState.lastAnswer = null;
    $("#papers-answer").classList.add("hidden");
  });
  $("#papers-upload-btn").addEventListener("click", papersShowUpload);
  $("#papers-upload-cancel").addEventListener("click", papersCancelUpload);
  $("#papers-upload-confirm").addEventListener("click", papersConfirmUpload);
  $("#papers-file-input").addEventListener("change", (e) => {
    if (e.target.files && e.target.files.length) papersConfirmUpload();
    e.target.value = "";
  });
  $("#papers-ask-btn").addEventListener("click", papersAsk);
  $("#papers-query").addEventListener("keydown", (e) => {
    if (e.key === "Enter" && !e.shiftKey) { e.preventDefault(); papersAsk(); }
  });
  $("#papers-save-finding").addEventListener("click", papersSaveFinding);

  // Dev unlock
  const devBtn = $('#dev-unlock');
  if (devBtn) devBtn.addEventListener('click', showDevUnlock);

  const searchInput = $("#model-search-input");
  if (searchInput) {
    let debounce;
    searchInput.value = state.modelSearch || "";
    searchInput.addEventListener("input", (e) => {
      clearTimeout(debounce);
      debounce = setTimeout(() => {
        state.modelSearch = e.target.value;
        renderModelGroups();
      }, 150);
    });
  }

  $$(".settings-tab").forEach((tab) => {
    tab.addEventListener("click", () => switchSettingsTab(tab.dataset.tab));
  });
}

function autoGrow(el) {
  el.style.height = "auto";
  el.style.height = Math.min(el.scrollHeight, 180) + "px";
}

// ---------------------------------------------------------------------------
boot();

