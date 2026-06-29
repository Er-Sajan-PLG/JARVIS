RULES = [
    # ===== IDENTITY =====
    {
        "trigger": "i am ",
        "category": "identity",
        "type": "state",
        "behavior": "append"

    },
    {
        "trigger": "my name is ",
        "category": "identity",
        "type": "name",
        "behavior": "append"

    },
    {
        "trigger": "i identify as ",
        "category": "identity",
        "type": "self_identification",
        "behavior": "append"

    },

    # ===== PREFERENCES =====
    {
        "trigger": "i like ",
        "category": "preference",
        "type": "like",
        "behavior": "append"

    },
    {
        "trigger": "i prefer ",
        "category": "preference",
        "type": "preference",
        "behavior": "append"
        
    },
    {
        "trigger": "i enjoy ",
        "category": "preference",
        "type": "enjoyment",
        "behavior": "append"

    },

    # ===== SKILLS =====
    {
        "trigger": "i can ",
        "category": "skills",
        "type": "ability",
        "behavior": "append"

    },
    {
        "trigger": "i am skilled at ",
        "category": "skills",
        "type": "proficiency",
        "behavior": "append"

    },
    {
        "trigger": "i have experience with ",
        "category": "skills",
        "type": "experience",
        "behavior": "append"

    },

    # ===== GOALS =====
    {
        "trigger": "i want to ",
        "category": "goals",
        "type": "desire",
        "behavior": "append"

    },
    {
        "trigger": "my goal is ",
        "category": "goals",
        "type": "objective",
        "behavior": "append"

    },
    {
        "trigger": "i aspire to ",
        "category": "goals",
        "type": "aspiration",
        "behavior": "append"

    },

    # ===== PLANS =====
    {
        "trigger": "i plan to ",
        "category": "plans",
        "type": "intention",
        "behavior": "append"

    },
    {
        "trigger": "i will ",
        "category": "plans",
        "type": "future_action",
        "behavior": "append"

    },
    {
        "trigger": "i am going to ",
        "category": "plans",
        "type": "near_future",
        "behavior": "append"

    },

    # ===== TASKS =====
    {
        "trigger": "i need to ",
        "category": "tasks",
        "type": "requirement",
        "behavior": "append"

    },
    {
        "trigger": "i have to ",
        "category": "tasks",
        "type": "obligation",
        "behavior": "append"

    },
    {
        "trigger": "my task is ",
        "category": "tasks",
        "type": "action_item",
        "behavior": "append"

    },

    # ===== LOCATION =====
    {
        "trigger": "i am in ",
        "category": "location",
        "type": "current_position",
        "behavior": "append"

    },
    {
        "trigger": "i live in ",
        "category": "location",
        "type": "residence",
        "behavior": "append"

    },
    {
        "trigger": "i am located at ",
        "category": "location",
        "type": "geographical",
        "behavior": "append"

    },

    # ===== PROFESSION =====
    {
        "trigger": "i am a ",
        "category": "profession",
        "type": "job_title",
        "behavior": "append"

    },
    {
        "trigger": "i work as ",
        "category": "profession",
        "type": "role",
        "behavior": "append"

    },
    {
        "trigger": "my profession is ",
        "category": "profession",
        "type": "career",
        "behavior": "append"

    },
]