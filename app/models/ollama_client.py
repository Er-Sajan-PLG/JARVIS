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
        # 1. System prompt
        messages.append(
                {
                    "role": "system",
                    "content": self.SYSTEM_PROMPT,
                }
        )
        # fixed
        if self.facts:
            facts_text = "Known user facts:\n"

            print("self.facts =", self.facts)
            print("type(self.facts) =", type(self.facts))

            for i, fact in enumerate(self.facts):
                 print(f"fact[{i}] =", fact)
                 print(f"type(fact[{i}]) =", type(fact))

            for fact in self.facts:
                facts_text += (
                    f"- [{fact['category']}] "
                    f"{fact['type']} → {fact['value']}\n"
                )

            messages.append({
                "role": "system",
                "content": facts_text
            })

        messages.extend(self.conversation)
        print("Conversation extension is DISABLED")
        return messages

    def ask(self, prompt: str) -> str:
        # add user message to memory
        self.conversation.append(
                {
                    "role": "user",
                    "content": prompt,
                }
            )
        # build full prompt
        messages = self.build_messages()
        response = chat(
            model=self.model,
            messages=messages,  
        )
        from pprint import pprint

        print("=== Messages being sent ===")
        pprint(messages)
        print("===========================")
        
        answer = response["message"]["content"]
        # store assistant response
        self.conversation.append(
                {
                    "role": "assistant",
                    "content": answer,
                }
        )

        return answer