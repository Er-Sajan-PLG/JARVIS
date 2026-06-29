from app.memory.rules import RULES



def _split_into_sentences(message: str) -> list[str]:
    sentences = []
    current = []

    for char in message:
        current.append(char)
        if char in ".!?":
            sentence = "".join(current).strip()
            if sentence:
                sentences.append(sentence)
            current = []

    if current:                          # trailing text with no punctuation
        leftover = "".join(current).strip()
        if leftover:
            sentences.append(leftover)

    return sentences

def extract_facts(message: str) -> list[dict]:
    """
    Split message into sentences and extract all rule-matching facts.
    Returns a list of fact dicts (one per matched sentence).
    """
    sentences = _split_into_sentences(message)
    facts = []

    for sentence in sentences:
        lowered = sentence.lower()
        for rule in RULES:
            for trigger in rule["triggers"]:
                if trigger in lowered:
                    idx = lowered.find(trigger)
                    value = lowered[idx + len(trigger):].strip().rstrip(".!?")
                    facts.append({
                        "category": rule["category"],
                        "type":     rule["type"],
                        "value":    value,
                        "behavior": rule["behavior"],
                    })
                    break  # first matching rule wins per sentence

    return facts  # empty list if nothing matched

        




