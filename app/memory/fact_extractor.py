from app.memory.rules import RULES

def extract_fact(message: str):
     msg = message.lower()

     for rule in RULES:
        if rule["trigger"] in msg:
            trigger = rule["trigger"]
            category = rule["category"]
            type_ = rule["type"]
            idx = msg.find(trigger)          # Finds the starting index (0)
            value = msg[idx + len(trigger):]  # Starts after the trigger, goes to end 
            return {
                        "category": category,
                        "type": type_,
                        "value": value
            }
     return None
        




