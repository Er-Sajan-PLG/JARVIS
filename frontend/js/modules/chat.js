/* ===========================================================================
   Chat & Composer Module
   =========================================================================== */

import { state } from "../state.js";
import { $, $$, autoGrow, jumpToBottom } from "../utils/dom.js";
import { api, escapeHtml, renderMarkdown } from "../utils/api.js";

export function updateComposerEnabled() {
  const ready = !!state.activeModel;
  const sendBtn = $("#send-btn");
  const input = $("#input");
  if (sendBtn) sendBtn.disabled = !ready;
  if (input) {
    input.disabled = !ready;
    input.placeholder = ready
      ? "Message JARVIS…  (Enter to send, Shift+Enter for newline)"
      : "Select a model in Settings to start chatting…";
  }
}

export function clearMessages() {
  const container = $("#messages");
  if (!container) return;
  const btn = $("#scroll-bottom-btn");
  container.innerHTML = "";
  if (btn) container.appendChild(btn);
  const empty = $("#empty-state");
  if (empty) empty.remove();
}

export function renderMessages(messages) {
  clearMessages();
  if (!messages || !messages.length) return;
  messages.forEach((m, i) => appendMessage(m.role, m.content, false, m.pinned, i));
  jumpToBottom();
}

export function appendMessage(role, content, isNew, pinned = false, messageIndex = -1) {
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
  
  const container = $("#messages");
  if (container) container.appendChild(wrap);
  jumpToBottom();
  return body;
}

export async function sendMessage() {
  if (state.streaming || !state.activeModel) return;
  const input = $("#input");
  if (!input) return;
  const text = input.value.trim();
  if (!text && !state.attachments.length) return;

  const convId = state.conversationId;
  if (!convId) return;

  appendMessage("user", text || "(attachment)", true);
  input.value = "";
  autoGrow(input);

  const attachments = state.attachments.slice();
  state.attachments = [];
  renderAttachments();

  const body = appendMessage("assistant", "", true);
  const wrap = body.closest(".msg");
  if (wrap) {
    wrap.classList.add("thinking");
    body.textContent = "Thinking…";
  }

  await startStreaming(convId, text, attachments, body, wrap);
}

export async function startStreaming(convId, text, attachments, body, wrap) {
  state.streaming = true;
  setStreamingUI(true);

  const assistantText = { value: "" };
  try {
    let res;
    if (attachments && attachments.length) {
      const fd = new FormData();
      fd.append("conversation_id", convId);
      fd.append("message", text);
      attachments.forEach((a) => fd.append("attachments", a.file, a.name));
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
    if (wrap) wrap.classList.remove("thinking");
    if (body) body.innerHTML = `<span style="color:var(--danger)">Error: ${escapeHtml(e.message)}</span>`;
  } finally {
    state.streaming = false;
    setStreamingUI(false);
    // Reload conversations list dynamically so preview updates
    const { loadConversations } = await import("./conversations.js");
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
    if (wrap) wrap.classList.remove("thinking");
    assistantText.value += ev.data.token;
    if (body) body.innerHTML = renderMarkdown(assistantText.value);
    jumpToBottom();
  } else if (ev.event === "memory") {
    // server-side memory stored
  } else if (ev.event === "stopped") {
    if (wrap) wrap.classList.remove("thinking");
    if (body) body.innerHTML = renderMarkdown(assistantText.value + "\n\n_(stopped)_");
  } else if (ev.event === "done") {
    if (wrap) wrap.classList.remove("thinking");
  } else if (ev.event === "error") {
    if (wrap) wrap.classList.remove("thinking");
    if (body) body.innerHTML = `<span style="color:var(--danger)">${escapeHtml(ev.data.message)}</span>`;
  }
}

export function setStreamingUI(on) {
  const stopBtn = $("#stop-btn");
  const sendBtn = $("#send-btn");
  const input = $("#input");
  if (stopBtn) stopBtn.classList.toggle("hidden", !on);
  if (sendBtn) sendBtn.classList.toggle("hidden", on);
  if (input) input.disabled = on || !state.activeModel;
}

export async function stopGeneration() {
  try { await api("/api/stop", { method: "POST" }); } catch (e) {}
}

export async function uploadFiles(fileList) {
  for (const file of fileList) {
    state.attachments.push({ name: file.name, size: file.size, file });
  }
  renderAttachments();
}

export function renderAttachments() {
  const wrap = $("#attachments");
  if (!wrap) return;
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
