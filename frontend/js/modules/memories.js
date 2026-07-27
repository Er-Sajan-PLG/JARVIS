/* ===========================================================================
   Memories Modal Module
   =========================================================================== */

import { $ } from "../utils/dom.js";
import { api, escapeHtml } from "../utils/api.js";

export async function openMemories() {
  const list = $("#memories-list");
  if (!list) return;
  list.innerHTML = "<div class='status off'>Loading…</div>";
  const modal = $("#memories-modal");
  if (modal) modal.classList.remove("hidden");
  try {
    const data = await api("/api/memories");
    list.innerHTML = "";
    if (!data.memories || !data.memories.length) {
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
