// JARVIS Web UI — frontend controller (vanilla JS, no build step).

const $ = (sel) => document.querySelector(sel);
const $$ = (sel) => Array.from(document.querySelectorAll(sel));

const state = {
  conversationId: null,
  activeModel: null,
  streaming: false,
  attachments: [], // { name, size }
  selectedModelId: null,
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
  updateComposerEnabled();
}

// ---------------------------------------------------------------------------
// API helpers
// ---------------------------------------------------------------------------
async function api(path, opts = {}) {
  const res = await fetch(path, {
    headers: { "Content-Type": "application/json" },
    ...opts,
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
    renderModelGroups(data.groups);
    renderActiveModel();
  } catch (e) {
    console.error(e);
  }
}

function renderModelGroups(groups) {
  const wrap = $("#model-groups");
  wrap.innerHTML = "";
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
          ${g.requires_key ? (g.key_set ? "key set" : "key missing") : "available"}
        </span>`;
      opt.querySelector("input").addEventListener("change", () => selectModel(m.id));
      section.appendChild(opt);
    });
    if ((g.models || []).length === 0) {
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
  const prov = g.provider.replace("-all", "");
  const search = document.createElement("input");
  search.type = "search";
  search.placeholder = "Search all " + prov + " models…";
  search.className = "model-search";
  section.appendChild(search);
  const listWrap = document.createElement("div");
  listWrap.className = "dynamic-model-list";
  section.appendChild(listWrap);
  let debounce;
  function refresh(q) {
    listWrap.innerHTML = "<div class='status off'>Loading models…</div>";
    api(`/api/models/catalog?provider=${prov}&query=${encodeURIComponent(q)}&limit=50`)
      .then((data) => {
        listWrap.innerHTML = "";
        if (!data.models.length) { listWrap.innerHTML = "<div class='status off'>No models match.</div>"; return; }
        data.models.forEach((m) => {
          const opt = document.createElement("label");
          opt.className = "model-option";
          const checked = state.selectedModelId === `dyn:${m.id}` ? "checked" : "";
          const ctx = m.context_length ? " · " + (m.context_length / 1000) + "k ctx" : "";
          opt.innerHTML = `<input type="radio" name="model" value="dyn:${m.id}" data-backend="${prov}" data-model="${m.id}" ${checked} /><span>${m.id}</span><span class="status ok">${ctx}</span>`;
          opt.querySelector("input").addEventListener("change", (ev) => selectDynamicModel(ev.target.dataset.backend, ev.target.dataset.model));
          listWrap.appendChild(opt);
        });
      })
      .catch((e) => { listWrap.innerHTML = `<div class='status missing'>Error: ${escapeHtml(e.message)}</div>`; });
  }
  if (g.default_model) { state.selectedModelId = `dyn:${g.default_model}`; selectDynamicModel(prov, g.default_model, true); }
  refresh("");
  search.addEventListener("input", () => { clearTimeout(debounce); debounce = setTimeout(() => refresh(search.value), 250); });
}

function selectDynamicModel(backend, modelId, silent) {
  state.selectedModelId = `dyn:${modelId}`;
  $$('.model-option input').forEach((i) => { i.closest(".model-option").classList.toggle("selected", i.value === `dyn:${modelId}`); });
  api("/api/models/select", { method: "POST", body: JSON.stringify({ model_id: "dyn", backend, model: modelId }) })
    .then((res) => { state.activeModel = res.active || res.name || modelId; renderActiveModel(); updateComposerEnabled(); })
    .catch((e) => { if (!silent) alert("Could not select model: " + e.message); state.selectedModelId = null; });
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
async function loadConversations() {
  try {
    const data = await api("/api/conversations");
    const list = $("#conversation-list");
    list.innerHTML = "";
    data.conversations.forEach((c) => {
      const item = document.createElement("div");
      item.className = "conv-item" + (c.id === state.conversationId ? " active" : "");
      item.dataset.id = c.id;
      item.innerHTML = `
        <span class="conv-del" title="Delete">🗑</span>
        <div class="conv-title">${escapeHtml(c.title)}</div>
        <div class="conv-preview">${escapeHtml(c.preview || "")}</div>`;
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
  messages.forEach((m) => appendMessage(m.role, m.content, false));
  scrollToBottom();
}

function appendMessage(role, content, isNew) {
  const empty = $("#empty-state");
  if (empty) empty.remove();
  const wrap = document.createElement("div");
  wrap.className = `msg ${role}`;
  const avatar = role === "user" ? "🧑" : "🤖";
  wrap.innerHTML = `
    <div class="msg-avatar">${avatar}</div>
    <div class="msg-body"></div>`;
  const body = wrap.querySelector(".msg-body");
  body.innerHTML = renderMarkdown(content);
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

// ---------------------------------------------------------------------------
// Settings
// ---------------------------------------------------------------------------
async function openSettings() {
  try {
    const s = await api("/api/settings");
    $("#use-dev-keys").checked = !!s.use_developer_keys;
    // Only show key status, never echo secrets back.
    const status = $("#settings-status");
    status.className = "settings-status";
    status.textContent = "";
  } catch (e) {}
  $("#settings-modal").classList.remove("hidden");
}

async function saveSettings() {
  const payload = {
    use_developer_keys: $("#use-dev-keys").checked,
    google_api_key: $("#google-key").value,
    xai_api_key: $("#xai-key").value,
    openrouter_api_key: $("#openrouter-key").value,
    openai_api_key: $("#openai-key").value,
  };
  const status = $("#settings-status");
  status.className = "settings-status";
  status.textContent = "Saving…";
  try {
    const res = await api("/api/settings", { method: "POST", body: JSON.stringify(payload) });
    status.className = "settings-status ok";
    status.textContent = "Saved. Rebuilding model clients…";
    // refresh models to reflect any new keys
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
}

function autoGrow(el) {
  el.style.height = "auto";
  el.style.height = Math.min(el.scrollHeight, 180) + "px";
}

// ---------------------------------------------------------------------------
boot();


