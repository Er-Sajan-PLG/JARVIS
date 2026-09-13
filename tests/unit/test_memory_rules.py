"""Unit tests for memory rules defined in app/memory/rules.py."""

from app.memory.rules import RULES


def test_rules_structure():
    """Verify RULES is a non-empty list of valid rule definitions."""
    assert isinstance(RULES, list)
    assert len(RULES) > 0

    expected_categories = {
        "identity",
        "preference",
        "skills",
        "goals",
        "plans",
        "tasks",
        "location",
        "profession",
    }

    found_categories = set()

    for idx, rule in enumerate(RULES):
        assert isinstance(rule, dict), f"Rule at index {idx} is not a dict"
        assert "triggers" in rule, f"Rule at index {idx} missing 'triggers'"
        assert "category" in rule, f"Rule at index {idx} missing 'category'"
        assert "type" in rule, f"Rule at index {idx} missing 'type'"
        assert "behavior" in rule, f"Rule at index {idx} missing 'behavior'"

        assert isinstance(rule["triggers"], list), f"Triggers for rule {idx} is not a list"
        assert len(rule["triggers"]) > 0, f"Triggers for rule {idx} is empty"
        for trig in rule["triggers"]:
            assert isinstance(trig, str)
            assert len(trig.strip()) > 0

        assert rule["behavior"] == "append"
        found_categories.add(rule["category"])

    assert expected_categories.issubset(found_categories)


def test_rules_distinct_trigger_types():
    """Verify rules within the same category have distinct types."""
    category_types = {}
    for rule in RULES:
        cat = rule["category"]
        rtype = rule["type"]
        category_types.setdefault(cat, set()).add(rtype)

    assert "state" in category_types["identity"]
    assert "name" in category_types["identity"]
    assert "like" in category_types["preference"]
    assert "ability" in category_types["skills"]
    assert "desire" in category_types["goals"]
    assert "intention" in category_types["plans"]
    assert "requirement" in category_types["tasks"]
    assert "current_position" in category_types["location"]
    assert "job_title" in category_types["profession"]
