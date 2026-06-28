import json
from app.config.prompt import SYSTEM_PROMPT


class MemoryManager:

    def __init__(self, path: str):
        self.path = path
        self.facts = []

    def load(self):
        try:
            with open(self.path, "r") as file:
                data = json.load(file)

            # OLD FORMAT (list)
            if isinstance(data, list):
                conversation = data
                self.facts = []

            # NEW FORMAT (dict)
            else:
                conversation = data.get("conversation", [])
                self.facts = data.get("facts", [])

        except FileNotFoundError:
            conversation = [
                {
                    "role": "system",
                    "content": SYSTEM_PROMPT
                }
            ]
            self.facts = []

        return conversation, self.facts

    def save(self, conversation, facts):
        data = {
            "conversation": conversation,
            "facts": facts
        }

        with open(self.path, "w") as file:
            json.dump(data, file, indent=4)

    def clear(self):
        conversation = [
            {
                "role": "system",
                "content": SYSTEM_PROMPT
            }
        ]
        self.facts = []
        self.save(conversation, self.facts)

    def add_fact(self, fact):
        self.facts.append(fact)