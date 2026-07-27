---
doc_id: DOC-FRONTEND
title: "Frontend Subsystem"
target_audience: ["developers", "JARVIS"]
generated_from: "repository_archaeology"
---

# Frontend Subsystem

## 1. Overview
[Auto-generated from repository tree scan]

## 2. Active Symbols & API Surface
| Symbol | Type | Source File | Introduced Commit | Status |
| :--- | :--- | :--- | :--- | :--- |
| `boot` | function | `frontend/app.js` | `f9fa068` | ACTIVE |
| `api` | function | `frontend/app.js` | `f9fa068` | ACTIVE |
| `loadModels` | function | `frontend/app.js` | `f9fa068` | ACTIVE |
| `renderModelGroups` | function | `frontend/app.js` | `f9fa068` | ACTIVE |
| `renderDynamicGroup` | function | `frontend/app.js` | `f9fa068` | ACTIVE |
| `refresh` | function | `frontend/app.js` | `f9fa068` | ACTIVE |
| `selectDynamicModel` | function | `frontend/app.js` | `f9fa068` | ACTIVE |
| `selectModel` | function | `frontend/app.js` | `f9fa068` | ACTIVE |
| `renderActiveModel` | function | `frontend/app.js` | `f9fa068` | ACTIVE |
| `updateComposerEnabled` | function | `frontend/app.js` | `f9fa068` | ACTIVE |
| `loadConversations` | function | `frontend/app.js` | `81e45f0` | DELETED |
| `ensureConversation` | function | `frontend/app.js` | `f9fa068` | ACTIVE |
| `openConversation` | function | `frontend/app.js` | `f9fa068` | ACTIVE |
| `deleteConversation` | function | `frontend/app.js` | `f9fa068` | ACTIVE |
| `newChat` | function | `frontend/app.js` | `f9fa068` | ACTIVE |
| `clearMessages` | function | `frontend/app.js` | `f9fa068` | ACTIVE |
| `renderMessages` | function | `frontend/app.js` | `f9fa068` | ACTIVE |
| `appendMessage` | function | `frontend/app.js` | `81e45f0` | DELETED |
| `escapeHtml` | function | `frontend/app.js` | `f9fa068` | ACTIVE |
| `renderMarkdown` | function | `frontend/app.js` | `f9fa068` | ACTIVE |
| `isNearBottom` | function | `frontend/app.js` | `f9fa068` | ACTIVE |
| `scrollToBottom` | function | `frontend/app.js` | `f9fa068` | ACTIVE |
| `updateScrollButton` | function | `frontend/app.js` | `f9fa068` | ACTIVE |
| `jumpToBottom` | function | `frontend/app.js` | `f9fa068` | ACTIVE |
| `sendMessage` | function | `frontend/app.js` | `f9fa068` | ACTIVE |
| `startStreaming` | function | `frontend/app.js` | `f9fa068` | ACTIVE |
| `parseSSE` | function | `frontend/app.js` | `f9fa068` | ACTIVE |
| `handleStreamEvent` | function | `frontend/app.js` | `f9fa068` | ACTIVE |
| `setStreamingUI` | function | `frontend/app.js` | `f9fa068` | ACTIVE |
| `stopGeneration` | function | `frontend/app.js` | `f9fa068` | ACTIVE |
| `uploadFiles` | function | `frontend/app.js` | `f9fa068` | ACTIVE |
| `renderAttachments` | function | `frontend/app.js` | `f9fa068` | ACTIVE |
| `clearFilesOnServer` | function | `frontend/app.js` | `f9fa068` | ACTIVE |
| `iconForMime` | function | `frontend/app.js` | `f9fa068` | ACTIVE |
| `m` | function | `frontend/app.js` | `f9fa068` | ACTIVE |
| `n` | function | `frontend/app.js` | `f9fa068` | ACTIVE |
| `formatSize` | function | `frontend/app.js` | `f9fa068` | ACTIVE |
| `openAttachments` | function | `frontend/app.js` | `f9fa068` | DELETED |
| `closeAttachments` | function | `frontend/app.js` | `f9fa068` | DELETED |
| `libRefreshTree` | function | `frontend/app.js` | `f9fa068` | DELETED |
| `renderFolderTree` | function | `frontend/app.js` | `f9fa068` | DELETED |
| `renderFolderNode` | function | `frontend/app.js` | `f9fa068` | DELETED |
| `libNavigate` | function | `frontend/app.js` | `f9fa068` | DELETED |
| `renderBreadcrumb` | function | `frontend/app.js` | `f9fa068` | DELETED |
| `parts` | function | `frontend/app.js` | `f9fa068` | DELETED |
| `libLoadFiles` | function | `frontend/app.js` | `f9fa068` | DELETED |
| `renderFiles` | function | `frontend/app.js` | `f9fa068` | DELETED |
| `libAttachFile` | function | `frontend/app.js` | `f9fa068` | DELETED |
| `libDeleteFile` | function | `frontend/app.js` | `f9fa068` | DELETED |
| `libCreateFolder` | function | `frontend/app.js` | `f9fa068` | DELETED |
| `libConfirmFolder` | function | `frontend/app.js` | `f9fa068` | DELETED |
| `libCancelFolder` | function | `frontend/app.js` | `f9fa068` | DELETED |
| `libDeleteFolder` | function | `frontend/app.js` | `f9fa068` | DELETED |
| `libUploadFiles` | function | `frontend/app.js` | `f9fa068` | DELETED |
| `libSearch` | function | `frontend/app.js` | `f9fa068` | DELETED |
| `openSettings` | function | `frontend/app.js` | `f9fa068` | ACTIVE |
| `saveSettings` | function | `frontend/app.js` | `f9fa068` | ACTIVE |
| `openMemories` | function | `frontend/app.js` | `f9fa068` | ACTIVE |
| `bindEvents` | function | `frontend/app.js` | `f9fa068` | ACTIVE |
| `autoGrow` | function | `frontend/app.js` | `f9fa068` | ACTIVE |
| `openPapers` | function | `frontend/app.js` | `6e1b09a` | DELETED |
| `closePapers` | function | `frontend/app.js` | `6e1b09a` | DELETED |
| `papersLoadFolders` | function | `frontend/app.js` | `6e1b09a` | DELETED |
| `papersRenderFolderSelect` | function | `frontend/app.js` | `6e1b09a` | DELETED |
| `papersLoadDocuments` | function | `frontend/app.js` | `6e1b09a` | DELETED |
| `papersRenderDocuments` | function | `frontend/app.js` | `6e1b09a` | DELETED |
| `papersDeleteDocument` | function | `frontend/app.js` | `6e1b09a` | DELETED |
| `papersShowUpload` | function | `frontend/app.js` | `6e1b09a` | DELETED |
| `papersCancelUpload` | function | `frontend/app.js` | `6e1b09a` | DELETED |
| `papersConfirmUpload` | function | `frontend/app.js` | `6e1b09a` | DELETED |
| `papersAsk` | function | `frontend/app.js` | `6e1b09a` | DELETED |
| `papersRenderSources` | function | `frontend/app.js` | `6e1b09a` | DELETED |
| `papersSaveFinding` | function | `frontend/app.js` | `6e1b09a` | DELETED |
| `first` | function | `frontend/app.js` | `6e1b09a` | DELETED |
| `text` | function | `frontend/app.js` | `6e1b09a` | DELETED |
| `getSecurityHeaders` | function | `frontend/app.js` | `81e45f0` | ACTIVE |
| `normalizeProvider` | function | `frontend/app.js` | `81e45f0` | ACTIVE |
| `providerLabel` | function | `frontend/app.js` | `81e45f0` | ACTIVE |
| `renderProviderTabs` | function | `frontend/app.js` | `81e45f0` | ACTIVE |
| `freeTag` | function | `frontend/app.js` | `81e45f0` | ACTIVE |
| `buildModelTooltip` | function | `frontend/app.js` | `81e45f0` | ACTIVE |
| `fetchOCRHealth` | function | `frontend/app.js` | `81e45f0` | ACTIVE |
| `checkLocalOCR` | function | `frontend/app.js` | `81e45f0` | ACTIVE |
| `updateOCRHealthUI` | function | `frontend/app.js` | `81e45f0` | ACTIVE |
| `startOCRHealthPoll` | function | `frontend/app.js` | `81e45f0` | ACTIVE |
| `loadDevState` | function | `frontend/app.js` | `81e45f0` | ACTIVE |
| `showDevUnlock` | function | `frontend/app.js` | `81e45f0` | ACTIVE |
| `renderCapabilitiesMatrix` | function | `frontend/app.js` | `81e45f0` | ACTIVE |
| `switchSettingsTab` | function | `frontend/app.js` | `81e45f0` | ACTIVE |
| `boot` | function | `frontend/js/main.js` | `d86e203` | ACTIVE |
| `parseSSE` | function | `frontend/js/modules/chat.js` | `d86e203` | ACTIVE |
| `handleStreamEvent` | function | `frontend/js/modules/chat.js` | `d86e203` | ACTIVE |
| `refresh` | function | `frontend/js/modules/models.js` | `d86e203` | ACTIVE |
| `freeTag` | function | `frontend/js/modules/models.js` | `d86e203` | ACTIVE |
| `m` | function | `frontend/js/utils/api.js` | `d86e203` | ACTIVE |
| `n` | function | `frontend/js/utils/api.js` | `d86e203` | ACTIVE |
