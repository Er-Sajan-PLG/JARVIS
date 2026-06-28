# v0.8.0

1. Added

* Structured dictionary-based memory
* Rule-based fact extraction
* rules.py
* Category/type/value memory format

2. Changed

* Updated fact_extractor.py
* Updated ollama_client.py
* Updated memory.py
* build_messages() now formats structured facts

3. Fixed

* Variable scope issues
* Missing RULES import
* Compatibility with new memory format

4. Verified

* Confirmed Ollama is stateless
* Verified complete memory pipeline
* Verified structured facts persist correctly

5. Known Issues

* Only one fact extracted per prompt
* No sentence splitting
* No duplicate detection
