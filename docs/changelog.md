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



# v0.9.0

1. Added
-----
+ extract_facts()
+ Multi-fact extraction
+ Sentence splitting
+ Dictionary-based structured facts
+ Rule-driven extraction pipeline

2. Changed
-------
* Extractor now returns List[dict]
* main.py processes multiple facts
* Memory storage supports multiple structured facts
* Prompt builder uses structured memory

3. Fixed
-----
* Single-fact extraction limitation
* Nested list storage bug
* Dictionary/string incompatibility

4. Known Issues
------------
- Regex sentence splitter
- Duplicate memories
- Compound facts remain unparsed


# v1.0.0

1. Added

- Multiple fact extraction
- Sentence splitting
- Structured memory objects
- Behavior-based memory engine
- append behavior
- replace behavior
- ignore behavior framework
- Cleaner memory architecture

2. Changed

- MemoryManager no longer hardcodes replacement logic.
- Memory behavior is now controlled entirely by RULES.
- Fact extraction supports multiple sentences.

3. Fixed

- Nested fact list bug
- Conversation memory loading issues
- Behavior persistence
- Various extractor bugs


# v1.1


1. Added

- Multiple triggers per rule.
- Behavior field inside rules.
- Behavior propagation through extractor.
- MemoryManager behavior dispatcher.
- Pressure testing of extraction pipeline.

2. Improved

- Rule flexibility.
- Natural language coverage.
- Cleaner extractor architecture.

3. Fixed

- Trigger schema migration (`trigger` → `triggers`).
- Behavior persistence.
- Rule iteration logic.