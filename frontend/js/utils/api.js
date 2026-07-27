/* ===========================================================================
   API Request Utilities & Data Formatting Helpers
   =========================================================================== */

export function getSecurityHeaders() {
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

export async function api(path, opts = {}) {
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

export function escapeHtml(s) {
  return String(s).replace(/[&<>"']/g, (c) => ({
    "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;",
  }[c]));
}

// Lightweight markdown: code fences, inline code, and basic line breaks.
export function renderMarkdown(text) {
  if (!text) return "";
  const escaped = escapeHtml(text);
  let html = escaped.replace(/```(\w*)\n([\s\S]*?)```/g, (_, lang, code) =>
    `<pre><code>${code.replace(/\n$/, "")}</code></pre>`);
  html = html.replace(/`([^`]+?)`/g, "<code>$1</code>");
  html = html.split(/\n{2,}/).map((p) =>
    p.includes("<pre>") ? p : `<p>${p.replace(/\n/g, "<br>")}</p>`
  ).join("");
  return html;
}

export function iconForMime(mime, name) {
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

export function formatSize(bytes) {
  if (!bytes && bytes !== 0) return "";
  if (bytes < 1024) return bytes + " B";
  if (bytes < 1024 * 1024) return (bytes / 1024).toFixed(1) + " KB";
  return (bytes / (1024 * 1024)).toFixed(1) + " MB";
}
