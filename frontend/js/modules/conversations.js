/* ===========================================================================
   Conversations Module
   =========================================================================== */

import { state } from "../state.js";
import { $, $$ } from "../utils/dom.js";
import { api, escapeHtml } from "../utils/api.js";
import { renderMessages, clearMessages, updateComposerEnabled } from "./chat.js";

export async function loadConversations(filter = "") {
  try {
    const data = await api("/api/conversations");
    const list = $("#conversation-list");
    if (!list) return;
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
  } catch (e) {
    console.error("Failed to load conversations:", e);
  }
}

export async function ensureConversation() {
  if (state.conversationId) return;
  const data = await api("/api/conversations", { method: "POST", body: JSON.stringify({}) });
  state.conversationId = data.id;
  await loadConversations();
}

export async function openConversation(id) {
  state.conversationId = id;
  const chatTitle = $("#chat-title");
  if (chatTitle) chatTitle.textContent = "Loading…";
  const data = await api(`/api/conversations/${id}`);
  renderMessages(data.messages);
  $$(".conv-item").forEach((el) => el.classList.toggle("active", el.dataset.id === id));
  
  // rename title from first user message
  const firstUser = data.messages.find((m) => m.role === "user");
  if (chatTitle) chatTitle.textContent = firstUser ? firstUser.content.slice(0, 40) : "Chat";
  updateComposerEnabled();
}

export async function deleteConversation(id) {
  if (!confirm("Delete this conversation?")) return;
  await api(`/api/conversations/${id}`, { method: "DELETE" });
  if (state.conversationId === id) {
    state.conversationId = null;
    clearMessages();
  }
  await loadConversations();
  await ensureConversation();
}

export function newChat() {
  state.conversationId = null;
  clearMessages();
  ensureConversation();
  const sidebar = $("#sidebar");
  if (sidebar) sidebar.classList.remove("open");
}
