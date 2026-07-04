"""
JARVIS v2.0 - Main Entry Point

Architecture:
1. Extract facts from user input (FIRST - enables immediate personalization)
2. Store extracted facts
3. Retrieve relevant memories (includes just-stored facts!)
4. Build prompt with system + memories + conversation
5. Fit into context window (trimming in pairs)
6. Generate response
7. Add response to conversation

This order ensures that when a user says "My name is Sajan",
the fact is stored BEFORE retrieval, so it can be included
in the same turn's context.
"""

from app.config.settings import get_settings
from app.config.prompt import SYSTEM_PROMPT
from app.config.version import VERSION
from app.memory.manager import MemoryManager
from app.memory.fact_extractor import extract_facts
from app.conversation.manager import ConversationManager
from app.prompt.builder import PromptBuilder
from app.context.manager import ContextWindowManager
from app.models.llamacpp_client import LlamaCppClient
from app.models.router import ModelRouter, TaskType


def main():
    print("=" * 50)
    print(f"JARVIS {VERSION}")
    print("=" * 50)
    
    # Get centralized settings
    settings = get_settings()
    
    # Initialize subsystems with clean interfaces
    memory = MemoryManager()
    conversation = ConversationManager()
    prompt_builder = PromptBuilder(system_prompt=SYSTEM_PROMPT)
    context_manager = ContextWindowManager(
        max_tokens=settings.context.max_tokens,
        safety_margin=settings.context.safety_margin,
        model_name=settings.default_model,
    )
    
    # Initialize model
    model = LlamaCppClient(model=settings.default_model)
    
    # Set up model router (for future multi-model support)
    router = ModelRouter(default_model=model)
    
    # Show tokenizer info
    tokenizer_info = context_manager.get_tokenizer_info()
    print(f"\nTokenizer: {tokenizer_info.get('active_method', 'unknown')}")
    print(f"Memories loaded: {memory.count()}")
    print(f"Messages loaded: {conversation.count()}")
    print("\nCommands: quit, memories, help, stats\n")
    
    while True:
        # Fix in main.py:
        try:
            response = selected_model.generate(fitted_messages)
        except Exception as e:
            print(f"\n[Error] Model unavailable: {e}")
            print("Is llama-server running on port 8080?\n")
            conversation.pop_last_message()  # remove the user message we just added
        continue
        
        if prompt == "quit":
            print("\nGoodbye!")
            _cleanup(memory, conversation)
            break
        
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
        #    This enables immediate personalization: if user says "My name is Sajan",
        #    we store it now so it can be retrieved for this same turn.
        facts = extract_facts(prompt)
        
        # 3. Store extracted facts
        for fact in facts:
            stored = memory.store(fact)
            if stored:
                print(f"  [Memory] Stored: {stored.memory_type} → {stored.value}")
        
        # 4. Retrieve relevant memories (now includes just-stored facts!)
        relevant_memories = memory.retrieve(prompt, limit=settings.memory.retrieval_limit)
        
        if relevant_memories:
            print(f"  [Context] Retrieved {len(relevant_memories)} relevant memories")
        
        # 5. Build prompt with proper structure
        messages = prompt_builder.build(
            memories=relevant_memories,
            conversation=conversation.get_recent_formatted(),
        )
        
        # 6. Fit into context window (trims in pairs, never breaks exchanges)
        fitted_messages = context_manager.fit(messages)
        
        # 7. Generate response
        selected_model, task_type = router.route(prompt)
        response = selected_model.generate(fitted_messages)
        
        # 8. Add assistant response to conversation
        conversation.add_message("assistant", response.content)
        
        print(f"\nJarvis: {response.content}\n")
        
        # Show context stats if trimming occurred
        stats = context_manager.get_stats()
        if stats and stats.was_trimmed:
            print(f"  [Context] Trimmed {stats.pairs_trimmed} pairs ({stats.utilization:.0%} used)")
  

def _cleanup(memory: MemoryManager, conversation: ConversationManager):
    """Ensure all data is saved before exit"""
    memory.save_if_dirty()
    conversation.save_if_dirty()


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


def _show_stats(memory: MemoryManager, conversation: ConversationManager,
                context: ContextWindowManager, tokenizer_info: dict):
    """Show system statistics"""
    stats = context.last_stats
    
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

    if stats:
        print(f"""  Last utilization: {stats.utilization:.0%}
  Last pairs kept: {stats.pairs_kept}
  Last pairs trimmed: {stats.pairs_trimmed}""")
    
    print()


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


def _format_time(timestamp: float) -> str:
    """Format a timestamp for display"""
    import datetime
    dt = datetime.datetime.fromtimestamp(timestamp)
    return dt.strftime("%Y-%m-%d %H:%M")


if __name__ == "__main__":
    main()