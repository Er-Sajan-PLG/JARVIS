/* ===========================================================================
   Application State Container
   =========================================================================== */

export const state = {
  activeConversationId: null,
  conversations: [], // [{ id, title, updated_at }]
  activeModelKey: null,
  activeModelLabel: "",
  activeModelRole: "general",
  models: {},
  streaming: false,
  abortController: null,
  modelSearch: "",
  activeProvider: "all",
  attachments: [], // { name, size, file }
  lib: {
    tree: null,
    currentFolder: "",
    files: [],
  },
};
