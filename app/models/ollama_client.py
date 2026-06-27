from ollama import chat
from app.config.prompt import SYSTEM_PROMPT


class OllamaClient:

    def __init__(self, model: str):
        self.model = model
        self.conversation = [
            {
                "role": "system",
                "content": SYSTEM_PROMPT,
            }
        ] 

    def ask(self, prompt: str) -> str:

        self.conversation.append(
                {
                    "role": "user",
                    "content": prompt,
                }
            )

        response = chat(
            model=self.model,
            messages=self.conversation,  
        )
        
        answer = response["message"]["content"]

        self.conversation.append(
                {
                    "role": "assistant",
                    "content": answer,
                }
        )

        return answer
