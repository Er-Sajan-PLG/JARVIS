# Changelog
All notable changes documented here.
Format: Keep a Changelog (https://keepachangelog.com)

## [2.2.0] - 2026-07-05
### Added
- Semantic Memory system with ChromaDB vector retrieval
- Hybrid retriever (keyword + vector) for balanced search
- Conversation Store for persistent memory
- Agent integration for auto-generating devlogs and changelogs
- Streaming support via external config
- Multi-backend architecture for flexible model switching

### Changed
- Updated memory management to separate conversation facts from persistent storage
- Refactored ConversationManager to include error recovery (pop_last_message)
- Enhanced memory pipeline with structured fact extraction

### Fixed
- Resolved memory leakage issues in multi-trigger extraction
- Fixed config loading for external streaming parameters

### Known Issues
- ChromaDB vector index may require manual cleanup after heavy usage
- Hybrid retriever's keyword overlap threshold needs tuning for edge cases