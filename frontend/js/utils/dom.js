/* ===========================================================================
   DOM Manipulation & UI Helper Utilities
   =========================================================================== */

export const $ = (sel) => document.querySelector(sel);
export const $$ = (sel) => document.querySelectorAll(sel);

export function autoGrow(el) {
  if (!el) return;
  el.style.height = "auto";
  el.style.height = Math.min(el.scrollHeight, 180) + "px";
}

export function jumpToBottom() {
  const container = $("#messages");
  if (!container) return;
  container.scrollTop = container.scrollHeight;
  const btn = $("#scroll-bottom-btn");
  if (btn) btn.classList.add("hidden");
}

export function updateScrollButton() {
  const container = $("#messages");
  const btn = $("#scroll-bottom-btn");
  if (!container || !btn) return;

  const distanceToBottom = container.scrollHeight - container.scrollTop - container.clientHeight;
  if (distanceToBottom > 120) {
    btn.classList.remove("hidden");
  } else {
    btn.classList.add("hidden");
  }
}
