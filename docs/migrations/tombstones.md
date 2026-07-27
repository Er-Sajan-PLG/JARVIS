# Deleted & Deprecated Symbol Tombstone Registry

| Symbol Name | Removal Commit | Last Active Commit | Reason for Removal | Replacement Symbol |
| :--- | :--- | :--- | :--- | :--- |
| `app.prompt.builder.PromptBuilder` | `ec0dc4e` | `f9fa068` | Obsolete monolithic prompt builder; superseded by Jinja2 template loader & ContextBuilder | `app.prompt.loader.PromptLoader`, `app.context.builder.ContextBuilder` |
| `app/project/` | `ec0dc4e` | `1999e53` | Unused legacy empty directory | `app/workspace/manager.py` (`WorkspaceManager`) |
| `app.services.ocr` | `ec0dc4e` | `2c855c7` | Relocated to integrations layer to enforce third-party OSS boundary isolation | `app.integrations.ocr.OCRService` |
