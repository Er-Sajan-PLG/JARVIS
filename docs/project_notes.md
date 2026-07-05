## JARVIS v0.9.0 Mission
Goal

Transform:

One Message
        ↓
One Fact

into

One Message
        ↓
Many Sentences
        ↓
Many Facts
Current extractor

Currently it does:

message
     ↓
loop through RULES
     ↓
first match
     ↓
return fact

which immediately exits the function.

New extractor

Instead it should become:

message
     ↓
split into sentences
     ↓
for each sentence
          ↓
     for each rule
          ↓
     if matched
          ↓
     append fact
     ↓
return list of facts

Notice you'll now have two loops.

Conceptually:

for each sentence
    for each rule

The outer loop is new.

The inner loop is your existing rule matcher.

Return value changes

Instead of

return {
    ...
}

you'll eventually have

facts = []

...

facts.append(...)

...

return facts

If nothing is found:

return []

instead of

return None

because now the function returns a list.

A list with zero facts is:

[]

A list with one fact is:

[
    {...}
]

A list with five facts is:

[
    {...},
    {...},
    {...},
    {...},
    {...}
]

## For v2.0 

I think this is the right time to define **v2.0** before writing any code. It'll prevent feature creep and give you a clear roadmap.

Here's how I'd organize it.

# JARVIS v2.0 Roadmap

1. Intelligent Memory Retrieval (Highest Priority)

**Problem**

* Sends all memories to the LLM.
* Exceeds context limit.

**Solution**

* Build `retrieve(prompt)`.
* Return only relevant memories.
* Keyword retrieval first.
* ChromaDB later without changing the interface.

---

2. Memory Manager Redesign

Current

```text
Store everything
```

New

```text
Store
Update
Replace
Delete
Merge
Retrieve
```

One class should own the entire memory lifecycle.

---

3. Better Memory Schema

Current

```json
{
 category,
 type,
 value
}
```

Future

```json
{
 id,
 category,
 type,
 value,
 timestamp,
 source,
 confidence,
 importance,
 last_used,
 access_count
}
```

This prepares the system for ranking memories later.

---

4. Prompt Builder

Instead of

```text
All memories
```

Build prompts like

```text
System Prompt

↓

Relevant memories

↓

Recent conversation

↓

Current prompt
```

One dedicated component should assemble prompts.

---

5. Multi-Model Architecture

Instead of

```text
One model
```

Have roles:

```text
Autocomplete
↓

Coder

↓

Reasoner

↓

STEM
```

Future routing could even be automatic.

---

6. Conversation Manager

Current

```text
Everything
```

Future

```text
Recent history

↓

Summaries

↓

Retrieved memories
```

Three different context sources.

---

7. Better Fact Extraction

Current

```text
Rules
```

Future

```text
Rules

↓

LLM Extractor

↓

Hybrid
```

The interface remains identical.

---

8. Memory Ranking

Not every memory is equally important.

Example ranking factors:

* Importance
* Frequency
* Recency
* User preference
* Confidence

Then retrieve the highest-ranked memories.

---

9. Context Window Manager

Before calling the LLM:

```text
Count tokens

↓

If too large

↓

Compress

↓

Trim

↓

Summarize
```

Never exceed model limits again.

---

10. Configuration System

Centralize settings such as:

* Models
* Context size
* Retrieval limits
* Memory limits
* Paths
* Prompt templates

No hard-coded values scattered through the code.

---

11. (v2.x)

These can come after the core v2.0 release:

* ChromaDB integration
* Embeddings
* Vector search
* Hybrid retrieval
* Automatic model routing
* Long-term memory summarization
* Agent/tool framework
* Memory visualization
* Plugin system

---

12. Suggested implementation order

1. ✅ Memory Retrieval (`retrieve(prompt)`)
2. ✅ Prompt Builder
3. ✅ Memory Manager redesign
4. ✅ Context Window Manager
5. ✅ Better Memory Schema
6. ✅ Conversation Manager
7. ✅ Multi-Model support
8. ✅ Memory Ranking
9. ⏳ ChromaDB integration
10. ⏳ Embeddings

---

I also recommend one guiding principle for v2.0:

> **Every major subsystem should expose one clean interface, while hiding its implementation.**

For example:

```python
memory.retrieve(prompt)
memory.store(facts)
memory.update(fact)

prompt_builder.build(...)
conversation.get_recent()

model_router.select(task)
```

Internally you can replace JSON with ChromaDB, rules with LLM extraction, or keyword search with embeddings, but the rest of Jarvis never needs to change. That kind of separation will make future upgrades much easier.
