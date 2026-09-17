/* Chat shell — sidebar conversations, message list, composer.
   The model selector sits in the composer bar (bottom), not the topbar. */

import {
  $, $$, el, api, state, toast, loadModels, loadCustomState,
  findModel, providerByKey, formatBytes, escapeHtml, statusInfo,
} from './core.js';
import { openPicker } from './picker.js';

const CONV_KEY = 'jarvis.conversations';

/* `settings.js` imports `applyDefaultToChat` from this module, so importing
   openSettings statically here would create a cycle. Load it on demand. */
const openSettings = (...args) =>
  import('./settings.js').then((m) => m.openSettings(...args));

/* ── Conversation store (local index; memories live server-side) ────────── */

function loadConversations() {
  try {
    const raw = localStorage.getItem(CONV_KEY);
    state.conversations = raw ? JSON.parse(raw) : [];
  } catch {
    state.conversations = [];
  }
  return state.conversations;
}

function saveConversations() {
  try {
    localStorage.setItem(CONV_KEY, JSON.stringify(state.conversations.slice(0, 200)));
  } catch { /* quota — keep going */ }
}

function newSessionId() {
  return (crypto.randomUUID ? crypto.randomUUID() : `s-${Date.now()}-${Math.random().toString(36).slice(2)}`);
}

function ensureConversation() {
  if (state.currentSessionId) return state.currentSessionId;
  const id = newSessionId();
  state.conversations.unshift({
    id, title: 'New chat', created: Date.now(), updated: Date.now(), messages: [],
  });
  state.currentSessionId = id;
  saveConversations();
  return id;
}

function currentConversation() {
  return state.conversations.find((c) => c.id === state.currentSessionId) || null;
}

/* ── Rendering ──────────────────────────────────────────────────────────── */

function groupLabel(ts) {
  const d = new Date(ts);
  const now = new Date();
  if (d.toDateString() === now.toDateString()) return 'Today';
  const diff = Math.floor((now - d) / 86400000);
  if (diff === 1) return 'Yesterday';
  if (diff < 7) return 'Previous 7 Days';
  return 'Older';
}

export function renderConversations() {
  const host = $('#convList');
  if (!host) return;
  host.innerHTML = '';

  if (!state.conversations.length) {
    host.appendChild(el('div', {
      style: 'padding:12px 8px;color:var(--text-muted);font-size:12.5px',
      text: 'No conversations yet.',
    }));
    return;
  }

  const groups = new Map();
  for (const c of state.conversations) {
    const g = groupLabel(c.updated || c.created);
    if (!groups.has(g)) groups.set(g, []);
    groups.get(g).push(c);
  }

  for (const [label, items] of groups) {
    host.appendChild(el('div', { class: 'conv-group-label', text: label }));
    for (const c of items) {
      host.appendChild(convRow(c));
    }
  }
}

function convRow(c) {
  const active = c.id === state.currentSessionId;

  const actions = el('div', { class: 'conv-actions' }, [
    el('button', {
      class: 'conv-action',
      title: 'Rename',
      'aria-label': `Rename ${c.title}`,
      text: '✏️',
      onclick: (e) => { e.stopPropagation(); startRename(c, row); },
    }),
    el('button', {
      class: 'conv-action conv-del',
      title: 'Delete',
      'aria-label': `Delete ${c.title}`,
      text: '🗑️',
      onclick: (e) => { e.stopPropagation(); deleteConversation(c); },
    }),
  ]);

  const row = el('div', {
    class: `conv-item${active ? ' active' : ''}`,
    role: 'button',
    tabindex: '0',
    onclick: () => openConversation(c.id),
    onkeydown: (e) => { if (e.key === 'Enter') openConversation(c.id); },
  }, [
    el('span', { class: 'conv-title', text: c.title }),
    actions,
  ]);
  return row;
}

function startRename(c, row) {
  const titleEl = row.querySelector('.conv-title');
  const input = el('input', {
    class: 'input',
    style: 'padding:2px 6px;font-size:13px',
    value: c.title,
  });
  titleEl.replaceWith(input);
  input.focus();
  input.select();

  const commit = () => {
    const next = input.value.trim() || c.title;
    c.title = next;
    saveConversations();
    renderConversations();
  };

  input.addEventListener('blur', commit);
  input.addEventListener('keydown', (e) => {
    if (e.key === 'Enter') { e.preventDefault(); input.blur(); }
    if (e.key === 'Escape') { input.value = c.title; input.blur(); }
  });
}

async function deleteConversation(c) {
  if (!confirm(`Delete "${c.title}" and its saved memories?`)) return;
  try {
    const res = await api.deleteConversation(c.id);
    state.conversations = state.conversations.filter((x) => x.id !== c.id);
    if (state.currentSessionId === c.id) {
      state.currentSessionId = null;
      state.messages = [];
    }
    saveConversations();
    renderConversations();
    renderMessages();
    const n = res.deleted_memories ?? 0;
    toast(`Deleted conversation${n ? ` and ${n} memories` : ''}`);
  } catch (err) {
    toast(err.message, 'err');
  }
}

export function openConversation(id) {
  state.currentSessionId = id;
  const c = currentConversation();
  state.messages = c?.messages || [];
  renderConversations();
  renderMessages();
  $('#topbarTitle').textContent = c?.title || 'New chat';
}

export function newConversation() {
  state.currentSessionId = null;
  state.messages = [];
  state.attachments = [];
  renderConversations();
  renderMessages();
  renderAttachments();
  $('#topbarTitle').textContent = 'New chat';
}

export function renderMessages() {
  const host = $('#messagesInner');
  if (!host) return;
  host.innerHTML = '';

  if (!state.messages.length) {
    host.appendChild(el('div', { class: 'welcome' }, [
      el('h1', { text: 'JARVIS' }),
      el('p', { text: 'Ask anything, or attach a file to work with it.' }),
    ]));
    return;
  }

  for (const m of state.messages) {
    const isUser = m.role === 'user';
    const body = [el('div', { class: 'msg-role', text: isUser ? 'You' : (m.model || 'JARVIS') })];
    const text = el('div', { class: 'msg-text' });
    text.innerHTML = mdToHtml(m.content || '');
    body.push(text);

    if (m.files?.length) {
      body.push(el('div', { class: 'msg-files' },
        m.files.map((f) => el('span', { class: 'attach-chip', text: `📎 ${f.filename}` }))));
    }
    if (m.error) {
      body.push(el('div', {
        style: 'margin-top:8px;padding:9px 11px;background:var(--danger-soft);border-radius:9px;font-size:12.5px;color:var(--text-secondary)',
        text: m.error,
      }));
    }

    host.appendChild(el('div', { class: `msg ${isUser ? 'msg-user' : 'msg-assistant'}` }, [
      el('div', { class: 'msg-avatar', text: isUser ? 'You'.slice(0, 1) : 'J' }),
      el('div', { class: 'msg-body' }, body),
    ]));
  }

  const scroller = $('#messages');
  if (scroller) scroller.scrollTop = scroller.scrollHeight;
}

/* Minimal, safe formatting: escape first, then apply a few patterns. */
function mdToHtml(src) {
  let s = escapeHtml(src);
  s = s.replace(/```([\s\S]*?)```/g, (_, code) => `<pre><code>${code.trim()}</code></pre>`);
  s = s.replace(/`([^`\n]+)`/g, '<code>$1</code>');
  s = s.replace(/\*\*([^*\n]+)\*\*/g, '<strong>$1</strong>');
  return s;
}

/* ── Attachments ────────────────────────────────────────────────────────── */

export function renderAttachments() {
  const host = $('#attachments');
  if (!host) return;
  host.innerHTML = '';
  state.attachments.forEach((a, i) => {
    host.appendChild(el('span', { class: 'attach-chip' }, [
      `📎 ${a.filename}`,
      el('button', {
        class: 'conv-action',
        style: 'width:18px;height:18px',
        text: '×',
        'aria-label': `Remove ${a.filename}`,
        onclick: () => {
          state.attachments.splice(i, 1);
          renderAttachments();
        },
      }),
    ]));
  });
}

async function handleFiles(fileList) {
  for (const file of Array.from(fileList)) {
    if (state.attachments.length >= 5) {
      toast('Up to 5 files per message', 'err');
      break;
    }
    toast(`Uploading ${file.name}…`);
    try {
      const fd = new FormData();
      fd.append('file', file);
      const res = await fetch('/api/upload', { method: 'POST', body: fd });
      const data = await res.json();
      if (!res.ok) throw new Error(data.detail || 'Upload failed');
      state.attachments.push({
        file_id: data.file_id,
        filename: data.filename,
        size: data.size,
        extracted_text: data.extracted_text,
      });
      renderAttachments();
      toast(`Attached ${data.filename}`);
    } catch (err) {
      toast(`Upload failed: ${err.message}`, 'err');
    }
  }
}

/* ── Model trigger (in the composer bar) ────────────────────────────────── */

export function renderModelTrigger() {
  const nameEl = $('#modelTriggerName');
  const dotEl = $('#modelTriggerDot');
  if (!nameEl) return;

  const { provider, id, name } = state.selectedModel;
  if (!provider || !id) {
    nameEl.textContent = 'Select model';
    if (dotEl) dotEl.className = 'dot dot-off';
    return;
  }
  nameEl.textContent = name || id;

  const p = providerByKey(provider);
  if (dotEl) {
    const si = statusInfo(p?.status);
    dotEl.className = `dot ${si.dot}`;
    dotEl.title = p ? `${p.name}: ${si.label}` : provider;
  }
}

export function applyDefaultToChat() {
  const { provider, model } = state.defaultModel;
  if (!provider || !model) {
    // Fall back to the first model of the first available provider.
    const first = state.providers.find((p) => p.status === 'available' && p.models?.length);
    if (first) {
      state.selectedModel = { provider: first.key, id: first.models[0].id, name: first.models[0].name || first.models[0].id };
    }
  } else {
    const m = findModel(provider, model);
    state.selectedModel = { provider, id: model, name: m ? (m.name || m.id) : model };
  }
  renderModelTrigger();
}

/* ── Send ───────────────────────────────────────────────────────────────── */

export async function sendMessage() {
  if (state.sending) return;
  const input = $('#composerInput');
  const text = input.value.trim();
  if (!text && !state.attachments.length) return;

  if (!state.selectedModel.provider || !state.selectedModel.id) {
    toast('Pick a model first', 'err');
    openPicker({
      title: 'Select a model',
      onSelect: (entry) => {
        state.selectedModel = { provider: entry.provider, id: entry.id, name: entry.name || entry.id };
        renderModelTrigger();
      },
    });
    return;
  }

  ensureConversation();
  const c = currentConversation();
  const files = [...state.attachments];

  state.messages.push({ role: 'user', content: text, files });
  if (c) {
    c.messages = state.messages;
    if (c.title === 'New chat' && text) c.title = text.slice(0, 48) + (text.length > 48 ? '…' : '');
    c.updated = Date.now();
  }
  input.value = '';
  input.style.height = 'auto';
  state.attachments = [];
  renderAttachments();
  renderMessages();
  renderConversations();
  $('#topbarTitle').textContent = c?.title || 'New chat';

  state.sending = true;
  $('#sendBtn').disabled = true;

  const pending = el('div', { class: 'msg msg-assistant' }, [
    el('div', { class: 'msg-avatar', text: 'J' }),
    el('div', { class: 'msg-body' }, [
      el('div', { class: 'msg-role', text: state.selectedModel.name || 'JARVIS' }),
      el('div', { style: 'display:flex;gap:8px;align-items:center;color:var(--text-muted)' }, [
        el('span', { class: 'spinner' }),
        el('span', { class: 'pending-label', text: 'Thinking…' }),
      ]),
    ]),
  ]);
  $('#messagesInner')?.appendChild(pending);
  const scroller = $('#messages');
  if (scroller) scroller.scrollTop = scroller.scrollHeight;

  try {
    const res = await api.chat(
      {
        message: text,
        model: state.selectedModel,
        session_id: state.currentSessionId,
        memory_enabled: state.memoryEnabled,
        files: files.map((f) => f.filename),
        file_contents: files.map((f) => [f.filename, f.extracted_text || '']),
      },
      {
        // Show elapsed time once a reply passes a few seconds, so a slow
        // agentic provider reads as "still working" rather than "hung".
        onProgress: (ms) => {
          if (!pending.isConnected) return;
          const label = pending.querySelector('.pending-label');
          if (label && ms > 3000) label.textContent = `Thinking… ${Math.round(ms / 1000)}s`;
        },
      }
    );

    pending.remove();

    if (res.error) {
      state.messages.push({ role: 'assistant', content: '', error: res.error, model: state.selectedModel.name });
    } else {
      state.messages.push({
        role: 'assistant',
        content: res.response || '(empty response)',
        model: state.selectedModel.name || state.selectedModel.id,
      });
    }
  } catch (err) {
    pending.remove();
    state.messages.push({
      role: 'assistant', content: '', error: err.message, model: state.selectedModel.name,
    });
  } finally {
    state.sending = false;
    $('#sendBtn').disabled = false;
    if (c) { c.messages = state.messages; c.updated = Date.now(); saveConversations(); }
    renderMessages();
    renderConversations();
  }
}

/* ── Wiring ─────────────────────────────────────────────────────────────── */

export function initChat() {
  loadConversations();

  $('#newChatBtn')?.addEventListener('click', newConversation);
  $('#settingsBtn')?.addEventListener('click', () => openSettings());
  $('#topbarSettings')?.addEventListener('click', () => openSettings());
  $('#sidebarToggle')?.addEventListener('click', () => {
    const app = $('#app');
    app.classList.toggle('sidebar-collapsed');
    localStorage.setItem('jarvis.sidebar', app.classList.contains('sidebar-collapsed') ? 'collapsed' : 'open');
  });

  $('#modelTrigger')?.addEventListener('click', () => openPicker({
    title: 'Select a model',
    onSelect: (entry) => {
      state.selectedModel = { provider: entry.provider, id: entry.id, name: entry.name || entry.id };
      renderModelTrigger();
      toast(`Using ${entry.name || entry.id}`);
    },
  }));

  const input = $('#composerInput');
  if (input) {
    input.addEventListener('input', () => {
      input.style.height = 'auto';
      input.style.height = `${Math.min(input.scrollHeight, 200)}px`;
    });
    input.addEventListener('keydown', (e) => {
      if (e.key === 'Enter' && !e.shiftKey) {
        e.preventDefault();
        sendMessage();
      }
    });
  }

  $('#sendBtn')?.addEventListener('click', sendMessage);

  const fileInput = $('#fileInput');
  $('#attachBtn')?.addEventListener('click', () => fileInput?.click());
  fileInput?.addEventListener('change', (e) => {
    handleFiles(e.target.files);
    e.target.value = '';
  });

  // Drag and drop onto the composer.
  const box = $('#composerBox');
  if (box) {
    ['dragenter', 'dragover'].forEach((ev) =>
      box.addEventListener(ev, (e) => { e.preventDefault(); box.style.borderColor = 'var(--accent)'; }));
    ['dragleave', 'drop'].forEach((ev) =>
      box.addEventListener(ev, (e) => { e.preventDefault(); box.style.borderColor = ''; }));
    box.addEventListener('drop', (e) => {
      if (e.dataTransfer?.files?.length) handleFiles(e.dataTransfer.files);
    });
  }
}

export { loadModels, loadCustomState };