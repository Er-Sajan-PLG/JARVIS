/* ===========================================================================
   Settings Modal & API Key Management Module
   =========================================================================== */

import { $, $$ } from "../utils/dom.js";
import { api } from "../utils/api.js";
import { loadModels, renderCapabilitiesMatrix } from "./models.js";

export function switchSettingsTab(tabName) {
  $$(".settings-tab").forEach((tab) => {
    tab.classList.toggle("selected", tab.dataset.tab === tabName);
  });
  $$(".settings-tab-panel").forEach((panel) => {
    panel.classList.toggle("hidden", panel.id !== `settings-tab-${tabName}`);
  });
  if (tabName === "capabilities") {
    renderCapabilitiesMatrix();
  }
}

export async function openSettings() {
  try {
    await api("/api/settings");
    const status = $("#settings-status");
    if (status) {
      status.className = "settings-status";
      status.textContent = "";
    }
  } catch (e) {}
  
  // Populate existing keys from localStorage
  const keyInputs = {
    google: "#google-key",
    grok: "#xai-key",
    openrouter: "#openrouter-key",
    openai: "#openai-key",
    anthropic: "#anthropic-key",
    together: "#together-key",
    cerebras: "#cerebras-key",
    groq: "#groq-key",
    sambanova: "#sambanova-key",
    nvidia: "#nvidia-key"
  };
  
  for (const [provider, selector] of Object.entries(keyInputs)) {
    const input = $(selector);
    if (input) {
      input.value = localStorage.getItem(`jarvis_key_${provider}`) || "";
    }
  }

  switchSettingsTab("models");
  const modal = $("#settings-modal");
  if (modal) modal.classList.remove("hidden");
}

export async function saveSettings() {
  const keyInputs = {
    google: "#google-key",
    grok: "#xai-key",
    openrouter: "#openrouter-key",
    openai: "#openai-key",
    anthropic: "#anthropic-key",
    together: "#together-key",
    cerebras: "#cerebras-key",
    groq: "#groq-key",
    sambanova: "#sambanova-key",
    nvidia: "#nvidia-key"
  };
  
  const keys = {};
  for (const [provider, selector] of Object.entries(keyInputs)) {
    const el = $(selector);
    keys[provider] = el ? el.value.trim() : "";
  }

  const status = $("#settings-status");
  if (status) {
    status.className = "settings-status";
    status.textContent = "Saving locally…";
  }

  try {
    for (const [provider, val] of Object.entries(keys)) {
      if (val) {
        localStorage.setItem(`jarvis_key_${provider}`, val);
      } else {
        localStorage.removeItem(`jarvis_key_${provider}`);
      }
    }

    await api("/api/settings", { 
      method: "POST", 
      body: JSON.stringify({ use_developer_keys: $("#use-dev-keys")?.checked }) 
    });

    if (status) {
      status.className = "settings-status ok";
      status.textContent = "Saved to browser storage.";
    }
    await loadModels();
    setTimeout(() => {
      const modal = $("#settings-modal");
      if (modal) modal.classList.add("hidden");
    }, 600);
  } catch (e) {
    if (status) {
      status.className = "settings-status err";
      status.textContent = "Error: " + e.message;
    }
  }
}
