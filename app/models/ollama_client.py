from ollama import chat
from app.config.prompt import SYSTEM_PROMPT



class OllamaClient:

    def __init__(self, model: str, conversation: list, facts: list):
        self.model = model
        self.SYSTEM_PROMPT = SYSTEM_PROMPT
        self.conversation = conversation
        self.facts = facts


    def build_messages(self) -> list:
        
        messages=[]

        messages.append(
                {
                    "role": "system",
                    "content": self.SYSTEM_PROMPT,
                }
        )
        # fixed
        if self.facts:
            facts_text = "Here are some known facts:\n"
            for fact in self.facts:        # singular 'fact' — one item per iteration
               facts_text += f"- {fact}\n"  # append to facts_text, print the single item

            messages.append({
                "role": "system",
                "content": facts_text
            })
       
        messages.extend(self.conversation)

        return messages

    def ask(self, prompt: str) -> str:

        self.conversation.append(
                {
                    "role": "user",
                    "content": prompt,
                }
            )
        messages = self.build_messages()
        response = chat(
            model=self.model,
            messages=messages,  
        )
        
        answer = response["message"]["content"]

        self.conversation.append(
                {
                    "role": "assistant",
                    "content": answer,
                }
        )

        return answer