
"""
JARVIS — version is derived automatically from git tags (vA.B.C).

Architecture:
1. Extract facts from user input (FIRST - enables immediate personalization)
2. Store extracted facts
3. Retrieve relevant memories (includes just-stored facts!)
4. Build prompt with system + memories + conversation
5. Fit into context window (trimming in pairs)
6. Generate response (with streaming)
7. Add response to conversation

This order ensures that when a user says "My name is Sajan",
the fact is stored BEFORE retrieval, so it can be included
in the same turn's context.
"""





import datetime
import os
from dotenv import load_dotenv
from app.config.settings import get_settings
from app.config.prompt import SYSTEM_PROMPT
from app.config.version import VERSION
from app.memory.manager import MemoryManager
from app.memory.fact_extractor import extract_facts
from app.conversation.manager import ConversationManager
from app.prompt.builder import PromptBuilder
from app.context.manager import ContextWindowManager
from app.models.exceptions import ModelError
from app.utils.server_manager import ensure_server_running
from app.utils.model_selector import _startup_model_select
from app.memory.retrieval import KeywordRetriever
from app.memory.hybrid_retriever import HybridRetriever
from app.memory.vector_retriever import VectorRetriever
from app.memory.conversation_store import ConversationVectorStore
from app.models.llamacpp_client import LlamaCppClient
from app.agents.doc_agent import DocumentationAgent, run_interactive
from app.models.switcher import ModelSwitcher


# --- AUTO-START PREREQUISITE SERVERS ---
def _autostart_servers(settings) -> None:
    """Best-effort launch/repair of every local model server JARVIS needs.

    For each model whose ``backend == "llamacpp"`` AND whose ``base_url`` points
    at this machine (localhost / 127.0.0.1) on a real model port:

    * if the port is already open  -> nothing to do.
    * elif a ``llama-server`` binary is available -> launch it in the background
      and wait for the port to open.
    * else (no binary, e.g. llama.cpp was never installed) -> try to remap the
      model to an equivalently-named Ollama model that *is* pulled, so JARVIS can
      still serve it through Ollama (which is already running).

    Remote llamacpp entries (OpenRouter, xAI, ...) and non-llamacpp backends
    (ollama, google) are never touched. All failures are non-fatal: JARVIS
    prints a warning and continues so cloud/API models still work. The
    ``settings.models`` dict is mutated in place; the ``ModelSwitcher`` built
    immediately afterwards picks up any remaps.
    """
    from app.utils.server_manager import (
        ensure_server_running,
        warn_if_missing,
        find_llama_server_binary,
        port_from_url,
        is_local_url,
        is_port_open,
        ollama_model_names,
        match_ollama_model,
    )

    ollama_url = settings.paths.ollama_url
    ollama_available = ollama_model_names(ollama_url)  # [] if Ollama is down

    models_dir = os.environ.get("LLAMA_MODELS_DIR", os.path.join(os.getcwd(), "models"))
    binary = find_llama_server_binary()

    resolved_ports: set[int] = set()  # ports already handled (open or launched)
    for key, cfg in settings.models.items():
        # Only genuine localhost llama.cpp chat servers are auto-managed.
        if cfg.backend != "llamacpp":
            continue
        if not is_local_url(cfg.base_url):
            continue  # remote endpoint (OpenRouter/xAI) — leave alone
        port = port_from_url(cfg.base_url)
        if port < 1024:
            continue  # 80/443 etc. are not model servers
        if port in resolved_ports:
            continue  # this port was already evaluated below

        host = "localhost"
        if is_port_open(port, host):
            resolved_ports.add(port)
            continue  # server already up for every model on this port

        if binary:
            model_path = os.path.join(models_dir, cfg.name)
            ensure_server_running(
                port=port,
                command=[binary, "-m", model_path, "-c", "4096", "--port", str(port)],
                name=f"llama.cpp ({cfg.name} @ :{port})",
                host=host,
            )
            resolved_ports.add(port)
            continue

        # No llama-server binary: remap EVERY model that shares this port to a
        # matching Ollama model (so sibling models like local_docs are fixed too).
        ollama_name = match_ollama_model(cfg.name, ollama_available) if ollama_available else None
        if ollama_name:
            for other_key, other_cfg in settings.models.items():
                if (other_cfg.backend == "llamacpp"
                        and is_local_url(other_cfg.base_url)
                        and port_from_url(other_cfg.base_url) == port):
                    print(f"↻ Remapping '{other_key}' ({other_cfg.name}) -> Ollama "
                          f"'{ollama_name}' (no llama.cpp server available)")
                    other_cfg.backend = "ollama"
                    other_cfg.base_url = ollama_url
                    other_cfg.name = ollama_name
        else:
            print(f"⚠️  '{key}' ({cfg.name}) needs a server on :{port} but no "
                  f"llama-server binary was found and no matching Ollama model exists.")
        resolved_ports.add(port)

    # Ollama is required for embeddings — detect, don't launch.
    warn_if_missing(ollama_url, "Ollama (embeddings)")


# -------------------------------------------------

def main():

    
    # Load .env (API keys, model URLs) before any settings / clients are
    # created. Kept inside main() so importing this module (e.g. in tests)
    # has no side effects.
    load_dotenv()

    # Configure diagnostics logging once, before any module emits warnings.
    from app.utils.logging_setup import setup_logging
    setup_logging()

    print("Starting Jarvis...")
    print("=" * 50)
    print(f"JARVIS {VERSION}")


    # Load settings from environment variables or config file
    settings = get_settings()
    
    # Initialize model clients
    memory = MemoryManager(
        retriever=HybridRetriever(
        vector=VectorRetriever(
            persist_dir=str(settings.paths.chroma_dir),
            ollama_url=settings.paths.ollama_url,
            embed_model=settings.paths.embed_model,
            ),
        keyword=KeywordRetriever(min_keyword_overlap=1),
        )
    )
    conversation = ConversationManager()
    prompt_builder = PromptBuilder(system_prompt=SYSTEM_PROMPT)
    conv_store = ConversationVectorStore(
        persist_dir=str(settings.paths.chroma_dir),
        ollama_url=settings.paths.ollama_url,
        embed_model=settings.paths.embed_model,
    )
    if conv_store.count() == 0:
        indexed = conv_store.index_history(conversation.get_all())
        if indexed>0:
            print(f"  [ConversationStore] Indexed {indexed} exchanges indexed")    
    context_manager = ContextWindowManager(
        max_tokens=settings.context.max_tokens,
        safety_margin=settings.context.safety_margin,
        model_name=settings.default_model,
    )
    
    
    #=== Model Router and Switcher ===

    switcher = ModelSwitcher(settings)

    # --- STARTUP MODEL SELECTOR ---
    # Present Ollama / llama.cpp / Google (+ free cloud APIs) and let the user
    # pick a backend and a concrete model before the chat loop begins.
    _startup_model_select(switcher, settings)

    doc_agent = DocumentationAgent(model=switcher.router.default_model)

    # Show tokenizer info
    tokenizer_info = context_manager.get_tokenizer_info()
    print(f"\nTokenizer: {tokenizer_info.get('active_method', 'unknown')}")
    print(f"Memories loaded: {memory.count()}")
    print(f"Messages loaded: {conversation.count()}")
    print("\nCommands: quit, model, memories, help, stats\n")

    #=== MAIN LOOP ===
    while True:

    
        # FIXED: Put input() back at the top of the loop!
        try:
            prompt = input("You: ").strip()
        except (EOFError, KeyboardInterrupt):
            print("\n\nGoodbye!")
            _cleanup(memory, conversation)
            break
        
        if not prompt:
            continue
           
        if prompt == "quit":
            print("\nGoodbye!")
            _cleanup(memory, conversation)
            break

        if prompt == "docs":
            try:
                run_interactive(doc_agent)
            except Exception as e:
                import traceback
                traceback.print_exc()
            continue      
        
        if prompt == "memories":
            _show_memories(memory)
            continue
        
        if prompt == "help":
            _show_help()
            continue
        
        if prompt == "stats":
            _show_stats(memory, conversation, context_manager, tokenizer_info)
            continue

        if prompt == "model":
            # Re-open the startup model selector to switch backend/model
            # without restarting JARVIS.
            _startup_model_select(switcher, settings)
            # Rebuild the documentation agent so it uses the new model.
            doc_agent = DocumentationAgent(model=switcher.router.default_model)
            continue

        # === MAIN PIPELINE ===
        
        # 1. Add user message to conversation
        conversation.add_message("user", prompt)
        
        # 2. Extract facts from user input (BEFORE retrieval!)
        facts = extract_facts(prompt)
        
        # 3. Store extracted facts
        for fact in facts:
            stored = memory.store(fact)
            if stored:
                print(f"  [Memory] Stored: {stored.memory_type} → {stored.value}")
        
        # 4. Retrieve relevant memories (now includes just-stored facts!)
        relevant_memories = memory.retrieve(prompt, limit=settings.memory.retrieval_limit)

        # 5. Retrieve relevant past exchanges from conversation store
        past_exchanges = conv_store.search(prompt, limit=2)
        if relevant_memories:
            print(f"  [Context] Retrieved {len(relevant_memories)} relevant memories")
        
        if past_exchanges :
            print(f"  [History] Retrieved {len(past_exchanges)} relevant past exchange(s)")

        # 6. Build prompt with proper structure
        messages = prompt_builder.build(
            memories=relevant_memories,
            conversation=conversation.get_recent_formatted(),
            past_exchanges=past_exchanges,
        )
        
        # 7. Fit into context window (trims in pairs, never breaks exchanges)
        fitted_messages = context_manager.fit(messages)
        
        # 8. Generate response
        selected_model, task_type = switcher.router.route(prompt)

        
        # 9. Stream response to console
        try:
            print(f"\nJarvis: ", end="", flush=True)
            
            response = selected_model.generate(
                fitted_messages,
                stream=True,  # Enable streaming
                on_token=lambda t: print(t, end="", flush=True)
            )
            
            print()  # Newline after streaming finishes
            
        except ModelError as e:
            # Clients now raise a typed ModelError instead of leaking raw
            # provider tracebacks, so only genuine model failures land here.
            print(f"\n[Error] {e}")
            print("Is the required server running?\n")
            conversation.pop_last_message()  # Remove the user message we just added
            continue  # Skip saving assistant response and go to next loop iteration
        
        # 10. Add assistant response to conversation
        conversation.add_message("assistant", response.content)

        conv_store.add_exchange(prompt, response.content)  # Store the exchange in the vector store 
        
        # Show context stats if trimming occurred
        stats = context_manager.get_stats()
        if stats and stats.was_trimmed:
            print(f"  [Context] Trimmed {stats.pairs_trimmed} pairs ({stats.utilization:.0%} used)")

        

## === Helper Functions ===
def _cleanup(memory: MemoryManager, conversation: ConversationManager):
    """Ensure all data is saved before exit"""
    memory.save_if_dirty()
    conversation.save_if_dirty()


# NOTE: model-selection helpers (_categorize_cloud_models,
# _build_ollama_router, _startup_model_select) live in
# app/utils/model_selector.py to keep this file focused on the pipeline.


#=== Display Functions ===
def _show_memories(memory: MemoryManager):
    """Display all stored memories"""
    memories = memory.get_all()
    
    if not memories:
        print("\nNo memories stored yet.\n")
        return
    
    print(f"\n=== {len(memories)} Memories ===")
    for m in memories:
        print(f"  [{m.category}] {m.memory_type}: {m.value}")
        print(f"    ID: {m.id} | Created: {_format_time(m.created_at)} | "
              f"Access: {m.access_count} | Conf: {m.confidence}")
    print()

#=== Show Statistics Function ===
def _show_stats(memory: MemoryManager, conversation: ConversationManager,
                context: ContextWindowManager, tokenizer_info: dict):
    """Show system statistics"""
    stats = context.last_stats
    
    # Print summary of system stats
    print(f"""
=== JARVIS Statistics ===

Tokenizer:
  Method: {tokenizer_info.get('active_method', 'unknown')}
  Test count: {tokenizer_info.get('test_count', 'N/A')}

Memory:
  Total: {memory.count()}
  Dirty: {memory.is_dirty}

Conversation:
  Messages: {conversation.count()}
  Dirty: {conversation.is_dirty}

Context Window:
  Max tokens: {context.max_tokens}
  Effective: {context.effective_max}""")
    
    # Show last utilization stats if available
    if stats:
        print(f"""  Last utilization: {stats.utilization:.0%}
  Last pairs kept: {stats.pairs_kept}
  Last pairs trimmed: {stats.pairs_trimmed}""")
    
    print()

#=== Help Function ===
def _show_help():
    """Show available commands"""
    print("""
Commands:
  quit     - Exit JARVIS
  model    - Re-open the model selector (switch backend / model)
  memories - View all stored memories
  stats    - Show system statistics
  help     - Show this help

Model selection: type 'model' any time to pick a different backend
(Ollama / llama.cpp / Google / Grok / OpenRouter) or model.

Try saying:
  - "My name is Sajan"
  - "I like chocolate"
  - "I work as a developer"
  - "Remember that my favorite color is blue"
""")

#=== Utility Functions ===
def _format_time(timestamp: float) -> str:
    """Format a timestamp for display"""
    dt = datetime.datetime.fromtimestamp(timestamp)
    return dt.strftime("%Y-%m-%d %H:%M")


if __name__ == "__main__":
    main()

