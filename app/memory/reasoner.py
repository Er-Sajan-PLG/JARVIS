def decide_behavior(new_fact, existing_facts):
    """
    Decide how a new fact should be stored.

    Returns:
        "append"
        "replace"
        "ignore"
    """

    return new_fact["behavior"]