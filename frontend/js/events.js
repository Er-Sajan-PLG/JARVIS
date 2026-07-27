/* ===========================================================================
   Event Wiring & Controller Bindings Module
   =========================================================================== */

import { state } from "./state.js";
import { $, $$, autoGrow, jumpToBottom, updateScrollButton } from "./utils/dom.js";
import { sendMessage, stopGeneration, uploadFiles } from "./modules/chat.js";
import { newChat, loadConversations } from "./modules/conversations.js";
import { renderModelGroups, showDevUnlock } from "./modules/models.js";
import { openSettings, saveSettings, switchSettingsTab } from "./modules/settings.js";
import { openMemories } from "./modules/memories.js";

export function bindEvents() {
  const sendBtn = $("#send-btn");
  if (sendBtn) sendBtn.addEventListener("click", sendMessage);

  const stopBtn = $("#stop-btn");
  if (stopBtn) stopBtn.addEventListener("click", stopGeneration);

  const newChatBtn = $("#new-chat-btn");
  if (newChatBtn) newChatBtn.addEventListener("click", newChat);

  const settingsBtn = $("#settings-btn");
  if (settingsBtn) settingsBtn.addEventListener("click", openSettings);

  const memoriesBtn = $("#memories-btn");
  if (memoriesBtn) memoriesBtn.addEventListener("click", openMemories);

  const saveSettingsBtn = $("#save-settings");
  if (saveSettingsBtn) saveSettingsBtn.addEventListener("click", saveSettings);

  const toggleSidebarBtn = $("#toggle-sidebar");
  if (toggleSidebarBtn) {
    toggleSidebarBtn.addEventListener("click", () => {
      const sidebar = $("#sidebar");
      if (sidebar) sidebar.classList.toggle("open");
    });
  }

  // Composer textarea enter key & autogrow
  const input = $("#input");
  if (input) {
    input.addEventListener("keydown", (e) => {
      if (e.key === "Enter" && !e.shiftKey) {
        e.preventDefault();
        sendMessage();
      }
    });
    input.addEventListener("input", () => autoGrow(input));
  }

  // File attachment trigger & upload handler
  const attachBtn = $("#attach-btn");
  if (attachBtn) attachBtn.addEventListener("click", () => $("#file-input")?.click());

  const fileInput = $("#file-input");
  if (fileInput) {
    fileInput.addEventListener("change", (e) => {
      if (e.target.files.length) uploadFiles(e.target.files);
    });
  }

  // Drag and drop attachment zone
  const composer = $("#composer");
  if (composer) {
    composer.addEventListener("dragover", (e) => e.preventDefault());
    composer.addEventListener("drop", (e) => {
      e.preventDefault();
      if (e.dataTransfer && e.dataTransfer.files.length) {
        uploadFiles(e.dataTransfer.files);
      }
    });
  }

  // Close modals backdrop & buttons
  $$("[data-close]").forEach((el) => {
    el.addEventListener("click", () => {
      const which = el.dataset.close;
      const modal = $(`#${which}-modal`);
      if (modal) modal.classList.add("hidden");
    });
  });

  // Scroll to bottom button & messages container scroll listener
  const sbBtn = $("#scroll-bottom-btn");
  if (sbBtn) sbBtn.addEventListener("click", jumpToBottom);

  const msgs = $("#messages");
  if (msgs) msgs.addEventListener("scroll", updateScrollButton);

  // Developer mode unlock
  const devBtn = $("#dev-unlock");
  if (devBtn) devBtn.addEventListener("click", showDevUnlock);

  // Model search input debounce
  const modelSearchInput = $("#model-search-input");
  if (modelSearchInput) {
    let debounce;
    modelSearchInput.value = state.modelSearch || "";
    modelSearchInput.addEventListener("input", (e) => {
      clearTimeout(debounce);
      debounce = setTimeout(() => {
        state.modelSearch = e.target.value;
        renderModelGroups();
      }, 150);
    });
  }

  // Conversation search input debounce
  const convSearchInput = $("#conversation-search-input");
  if (convSearchInput) {
    let debounce;
    convSearchInput.addEventListener("input", (e) => {
      clearTimeout(debounce);
      debounce = setTimeout(() => {
        loadConversations(e.target.value);
      }, 150);
    });
  }

  // Settings tab switching
  $$(".settings-tab").forEach((tab) => {
    tab.addEventListener("click", () => switchSettingsTab(tab.dataset.tab));
  });
}
