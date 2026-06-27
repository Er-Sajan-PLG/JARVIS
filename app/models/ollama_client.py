from ollama import chat
from app.config.prompts import SYSTEM_PROMPT


class OllamaClient:
    def __init__(self, model: str):
        self.model = model

    def ask(self, prompt: str) -> str:
        response = chat(
            model=self.model,
            messages=[
                {
                    "role": "user",
                    "content": prompt,
                }
            ],
        )

        return response["message"]["content"]
        