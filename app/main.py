print("Starting Jarvis...")

from app.config.settings import DEFAULT_MODEL
from app.models.ollama_client import OllamaClient
from app.memory.manager import MemoryManager
from app.memory.fact_extractor import extract_facts
from app.config.version import VERSION




def main():
    print("=" * 40)
    print(f"JARVIS {VERSION}")
    print("=" * 40)

    memory = MemoryManager(path="app/memory/conversation.json")

    conversation, facts = memory.load()

    client = OllamaClient(
        model=DEFAULT_MODEL,
        conversation=conversation,
        facts=facts
    )

    while True:

        prompt = input("You: ")

        if prompt == "quit":
            print("Good Bye")
            break

        # 1. Get AI response
        answer = client.ask(prompt)

        print(f"\nJarvis: {answer}")

        # 2. Extract fact from USER message (important!)
        facts = extract_facts(prompt)
        print("Extracted facts:")
        print(facts)

        for fact in facts:
             memory.add_fact(fact)

        # 3. Save updated conversation
        memory.save(
            conversation=client.conversation,
            facts=memory.facts
        )


if __name__ == "__main__":
    main()