"""
JARVIS v2.1.0 - Main Entry Point

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


from dotenv import load_dotenv
load_dotenv()

import sys
from app.config.settings import get_settings
from app.config.prompt import SYSTEM_PROMPT
from app.config.version import VERSION
from app.memory.manager import MemoryManager
from app.memory.fact_extractor import extract_facts
from app.conversation.manager import ConversationManager
from app.prompt.builder import PromptBuilder
from app.context.manager import ContextWindowManager
from app.models.factory import create_client  
from app.models.router import ModelRouter, TaskType
from app.utils.server_manager import ensure_server_running
from app.memory.retrieval import KeywordRetriever
from app.memory.hybrid_retriever import HybridRetriever
from app.memory.vector_retriever import VectorRetriever
from app.memory.conversation_store import ConversationVectorStore
from app.models.llamacpp_client import LlamaCppClient
from app.agents.doc_agent import DocumentationAgent, run_interactive
from app.models.switcher import ModelSwitcher


# --- AUTO-START LLM SERVER ---
#LLAMA_SERVER_PATH = "./llama-server"
#MAIN_MODEL_PATH = "./models/llama-3.2-3b-instruct-q4_k_m.gguf"

#ensure_server_running(
#    port=8080,
#    command=[LLAMA_SERVER_PATH, "-m", MAIN_MODEL_PATH, "-c", "4096", "--port", "8080"],
#    name="Main LLM (3B)"
#)
# -------------------------------------------------

print("Starting Jarvis...")




def main():

    
    print("=" * 50)
    print(f"JARVIS {VERSION}")
    print("=" * 50)


    # Load settings from environment variables or config file
    settings = get_settings()
    
    # Initialize model clients
    memory = MemoryManager(
        retriever=HybridRetriever(
        vector=VectorRetriever(
            persist_dir="data/chroma",
            ollama_url="http://localhost:11434",
            ),
        keyword=KeywordRetriever(min_keyword_overlap=1),
        )
    )
    conversation = ConversationManager()
    prompt_builder = PromptBuilder(system_prompt=SYSTEM_PROMPT)
    conv_store = ConversationVectorStore(persist_dir="data/chroma")
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

    doc_agent = DocumentationAgent(
        model=switcher.get_client(
            settings.profiles.get(settings.active_profile, {}).get("docs", "general")
        ) or switcher.router.default_model
    )

    # Show tokenizer info
    tokenizer_info = context_manager.get_tokenizer_info()
    print(f"\nTokenizer: {tokenizer_info.get('active_method', 'unknown')}")
    print(f"Memories loaded: {memory.count()}")
    print(f"Messages loaded: {conversation.count()}")
    print("\nCommands: quit, memories, help, stats\n")

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
            print("DEBUG: intercepted")
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

    
        

        if prompt.startswith("model"):
            arg = prompt[5:].strip()
            if not arg:
                result = _interactive_model_select(switcher, settings)
                if result:
                    if result.startswith("model:"):
                        mk = result[len("model:"):]
                        client = switcher.get_client(mk)
                        if client:
                            doc_agent = DocumentationAgent(model=client)
                    else:
                        print(f"✅ Switched to '{result}' profile")
                        docs_key = settings.profiles.get(result, {}).get("docs", "general")
                        new_model = switcher.get_client(docs_key)
                        if new_model:
                            doc_agent = DocumentationAgent(model=new_model)
            elif arg == "list":
                print(switcher.list_profiles())
            elif switcher.switch(arg):
                print(f"✅ Switched to '{arg}' profile")
                docs_key = settings.profiles.get(arg, {}).get("docs", "general")
                new_model = switcher.get_client(docs_key)
                if new_model:
                    doc_agent = DocumentationAgent(model=new_model)
            else:
                print(f"❌ Unknown profile: '{arg}'")
                print(f"Available: {list(settings.profiles.keys())}")
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
            
        except Exception as e:
            print(f"\n[Error] Model unavailable: {e}")
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


# app/main.py
def _categorize_profiles(settings) -> dict:
    """Split profiles into local vs api by the general model's base_url."""
    cats = {"local": [], "api": []}
    for name, mapping in settings.profiles.items():
        gen_key = mapping.get("general") or next(iter(mapping.values()), None)
        cfg = settings.models.get(gen_key)
        is_local = bool(cfg) and ("localhost" in cfg.base_url or "127.0.0.1" in cfg.base_url)
        cats["local" if is_local else "api"].append(name)
    return cats


def _categorize_cloud_models(settings) -> dict:
    """
    Group cloud model KEYS by provider, inferred from base_url host.
    (Google entries in your config use base_url 'http://localhost' for the
     Python block — fix those to the real host or they'll be missed here.)
    """
    from urllib.parse import urlparse
    host_map = {
        "api.x.ai": "grok",
        "openrouter.ai": "openrouter",
        "generativelanguage.googleapis.com": "google",
    }
    groups = {}
    for key, cfg in settings.models.items():
        if "localhost" in cfg.base_url or "127.0.0.1" in cfg.base_url:
            continue
        host = urlparse(cfg.base_url).netloc
        provider = host_map.get(host, host)
        groups.setdefault(provider, []).append(key)
    return groups


def _interactive_model_select(switcher, settings) -> str | None:
    """
    Local -> pick profile.  API -> pick provider -> pick specific model.
    Returns profile name, or 'model:<key>' when a single cloud model was chosen.
    """
    print("\n╔══════════════════════════════════════╗")
    print("║        Select Model Provider         ║")
    print("╚══════════════════════════════════════╝")
    print("  [1] Local  (runs on your machine)")
    print("  [2] API    (cloud providers)")

    choice = input("Provider (1/2): ").strip()

    # ---------- LOCAL ----------
    if choice == "1":
        cats = _categorize_profiles(settings)
        pool = cats["local"]
        if not pool:
            print("  No local profiles available."); return None
        print("\nLocal profiles:")
        for i, p in enumerate(pool, 1):
            marker = "●" if p == switcher.active_profile else " "
            print(f"  {i}. {marker} {p}")
        sel = input(f"Select (1-{len(pool)}): ").strip()
        try:
            profile = pool[int(sel) - 1]
        except (ValueError, IndexError):
            print("Invalid selection."); return None
        if switcher.switch(profile):
            return profile
        return None

    # ---------- API ----------
    if choice == "2":
        cloud = _categorize_cloud_models(settings)
        providers = list(cloud.keys())
        if not providers:
            print("  No cloud models configured."); return None
        print("\nCloud providers:")
        for i, p in enumerate(providers, 1):
            print(f"  {i}. {p}")
        sel = input(f"Select provider (1-{len(providers)}): ").strip()
        try:
            prov = providers[int(sel) - 1]
        except (ValueError, IndexError):
            print("Invalid selection."); return None

        models = cloud[prov]
        print(f"\nModels in {prov}:")
        for i, m in enumerate(models, 1):
            client = switcher.get_client(m)
            status = "✓ loaded" if client else "✗ key missing"
            print(f"  {i}. {settings.models[m].name}  [{m}]  {status}")
        selm = input(f"Select model (1-{len(models)}): ").strip()
        try:
            model_key = models[int(selm) - 1]
        except (ValueError, IndexError):
            print("Invalid selection."); return None

        if switcher.switch_to_model(model_key):
            print(f"✅ Using cloud model: {settings.models[model_key].name}")
            return f"model:{model_key}"
        print("  ⚠️ Model not loaded — check its API key in .env.")
        return None

    print("Invalid selection.")
    return None


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
  Dirty: {memory._store.is_dirty}

Conversation:
  Messages: {conversation.count()}
  Dirty: {conversation._dirty}

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
  memories - View all stored memories
  stats    - Show system statistics
  help     - Show this help

Try saying:
  - "My name is Sajan"
  - "I like chocolate"
  - "I work as a developer"
  - "Remember that my favorite color is blue"
""")

#=== Utility Functions ===
def _format_time(timestamp: float) -> str:
    """Format a timestamp for display"""
    import datetime
    dt = datetime.datetime.fromtimestamp(timestamp)
    return dt.strftime("%Y-%m-%d %H:%M")


if __name__ == "__main__":
    main()