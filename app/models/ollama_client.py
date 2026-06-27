from ollama import chat



class OllamaClient:

    def __init__(self, model: str, conversation : str):
        self.model = model
        self.conversation = conversation

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