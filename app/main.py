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


    # Get centralized settings (reads config.yaml if it exists)
    settings = get_settings()
    
    # Initialize subsystems with clean interfaces
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
    
    # === NEW: DYNAMIC MODEL ROUTING FROM CONFIG ===
    router = ModelRouter()
    
    for key, model_cfg in settings.models.items():
        try:
            client = create_client(model_cfg)
            task_type = TaskType(model_cfg.role)
            router.register(task_type, client)
            print(f"✅ Loaded {model_cfg.role}: {model_cfg.name} ({model_cfg.backend})")
        except Exception as e:
            print(f"❌ Failed to load {key}: {e}")
    
    # Set fallback default model
    if "general" in settings.models:
        router.set_default(create_client(settings.models["general"]))
    elif settings.models:
        router.set_default(create_client(list(settings.models.values())[0]))
    # ===============================================
    
    #=== NEW: DOCUMENTATION AGENT ===
    doc_agent = DocumentationAgent(
        model=router.select(TaskType.DOCS)
        if TaskType.DOCS in router.models
        else router.default_model
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
        selected_model, task_type = router.route(prompt)
        if selected_model is None:
            selected_model = router.default_model

        
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