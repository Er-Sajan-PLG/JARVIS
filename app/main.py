print("Starting Jarvis...")

from app.config.settings import DEFAULT_MODEL
from app.models.ollama_client import OllamaClient
from app.memory.manager import MemoryManager


def main():
    print("=" * 40)
    print("      JARVIS")
    print("=" * 40)

    memory = MemoryManager(path="app/memory/conversation.json")
    conversation = memory.load()
    client = OllamaClient(model=DEFAULT_MODEL,conversation=conversation)

    while True:

        prompt = input("You: ")

        if prompt == 'quit':
            print("Good Bye")
            break

        answer = client.ask(prompt)
        memory.save(client.conversation)

        print(f"\nJarvis: {answer}")



if __name__ == "__main__":
    main()