"""
Fact Extractor for JARVIS v2.0

Interface remains identical regardless of implementation.
"""

from app.memory.rules import RULES
from app.memory.schema import SOURCE_USER

# Boundaries where we should stop extracting a value
VALUE_BOUNDARIES = [
    # Coordinating conjunctions
    ", but",
    ", and",
    ", or",
    ", yet",
    ", so",
    " and ",
    " but ",
    " or ",
    " yet ",
    " so ",
    # Subordinating conjunctions
    " because ",
    " although ",
    " though ",
    " while ",
    " whereas ",
    " if ",
    " when ",
    " since ",
    " unless ",
    " until ",
    # Sentence endings (redundant with rstrip but safe)
    ". ",
    "! ",
    "? ",
]


def _split_into_sentences(message: str) -> list[str]:
    """Split message into sentences, handling common abbreviations"""
    sentences = []
    current = []

    # Abbreviations that shouldn't end sentences
    abbreviations = {"mr", "mrs", "ms", "dr", "prof", "sr", "jr", "st", "ave", "etc"}

    message_lower = message.lower()
    i = 0

    while i < len(message):
        current.append(message[i])

        if message[i] in ".!?":
            # Check if this is an abbreviation
            # Look back to find the word before the period
            word_start = len(current) - 2
            while word_start >= 0 and current[word_start].isalpha():
                word_start -= 1
            word = "".join(current[word_start + 1 : -1]).lower().rstrip(".")

            if word not in abbreviations:
                sentence = "".join(current).strip()
                if sentence:
                    sentences.append(sentence)
                current = []

        i += 1

    # Handle remaining text
    if current:
        leftover = "".join(current).strip()
        if leftover:
            sentences.append(leftover)

    return sentences


def _extract_value(text: str, trigger: str) -> str:
    """
    Extract the value after a trigger, stopping at natural boundaries.

    Args:
        text: The full lowercase text
        trigger: The trigger phrase that was found

    Returns:
        Extracted value, trimmed at boundaries
    """
    idx = text.find(trigger)
    if idx == -1:
        return ""

    start = idx + len(trigger)
    value = text[start:].strip()

    # Find earliest boundary
    earliest_boundary = len(value)
    for boundary in VALUE_BOUNDARIES:
        pos = value.find(boundary)
        if pos != -1 and pos < earliest_boundary:
            earliest_boundary = pos

    if earliest_boundary < len(value):
        value = value[:earliest_boundary]

    # Clean up
    value = value.strip().rstrip(".!?")

    # Remove leading articles/prepositions that are artifacts
    value = value.removeprefix("that ")
    value = value.removeprefix("to ")

    return value


def extract_facts(message: str, source: str = SOURCE_USER) -> list[dict]:
    """
    Extract facts from a message using rule-based extraction.

    Interface is stable - can swap to LLM extraction later.

    Args:
        message: The user's message
        source: Where this message came from

    Returns:
        List of fact dicts compatible with MemoryManager.store()
    """
    sentences = _split_into_sentences(message)
    facts = []

    for sentence in sentences:
        lowered = sentence.lower()

        for rule in RULES:
            matched = False

            for trigger in rule["triggers"]:
                if trigger in lowered:
                    value = _extract_value(lowered, trigger)

                    # Validate the extracted value
                    if value and len(value) >= 2:
                        facts.append(
                            {
                                "category": rule["category"],
                                "type": rule["type"],
                                "value": value,
                                "behavior": rule["behavior"],
                                "source": source,
                                "confidence": 1.0,
                            }
                        )
                        matched = True
                        break  # One match per rule per sentence

            if matched:
                continue  # Move to next rule (allow multiple facts from one sentence)

    return facts
