print("Starting Jarvis...")

from app.config.settings import DEFAULT_MODEL
from app.models.ollama_client import OllamaClient


def main():
    print("=" * 40)
    print("      JARVIS")
    print("=" * 40)

    client = OllamaClient(model=DEFAULT_MODEL)

    prompt = input("You: ")

    answer = client.ask(prompt)

    print(f"\nJarvis: {answer}")


if __name__ == "__main__":
    main()