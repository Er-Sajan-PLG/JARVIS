import json


class MemoryManager:

    def __init__(self, path: str):
        self.path = path

    def load(self):
        with open(self.path, "r") as file:
            conversation = json.load(file)

        return conversation

    def save(self, conversation):
        with open(self.path, "w") as file:
            json.dump(conversation, file, indent=4)

    def clear(self):
        conversation = new_conversation()
        self.save(conversation)