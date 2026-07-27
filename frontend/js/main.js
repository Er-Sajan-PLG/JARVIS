/* ===========================================================================
   JARVIS Frontend Application Entry Point
   =========================================================================== */

import { loadModels, startOCRHealthPoll, loadDevState } from "./modules/models.js";
import { loadConversations, ensureConversation } from "./modules/conversations.js";
import { updateComposerEnabled } from "./modules/chat.js";
import { bindEvents } from "./events.js";

async function boot() {
  await loadModels();
  await loadConversations();
  bindEvents();
  await ensureConversation();
  startOCRHealthPoll();
  updateComposerEnabled();
  loadDevState();
}

// Initialize application on DOM ready
if (document.readyState === "loading") {
  document.addEventListener("DOMContentLoaded", boot);
} else {
  boot();
}
