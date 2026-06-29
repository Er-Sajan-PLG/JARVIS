RULES = [
    # ===== IDENTITY =====
    {
        "triggers": ["i am ", "i'm "],
        "category": "identity",
        "type": "state",
        "behavior": "append"
    },
    {
        "triggers": ["my name is ", "my name's ", "call me ", "i go by "],
        "category": "identity",
        "type": "name",
        "behavior": "append"
    },
    {
        "triggers": ["i identify as ", "i see myself as ", "i consider myself "],
        "category": "identity",
        "type": "self_identification",
        "behavior": "append"
    },

    # ===== PREFERENCES =====
    {
        "triggers": ["i like ", "i love ", "i enjoy ", "i prefer ", "i'm into ", "i'm a fan of "],
        "category": "preference",
        "type": "like",
        "behavior": "append"
    },

    # ===== SKILLS =====
    {
        "triggers": ["i can ", "i know how to ", "i'm able to "],
        "category": "skills",
        "type": "ability",
        "behavior": "append"
    },
    {
        "triggers": ["i am skilled at ", "i'm good at ", "i excel at ", "i specialize in "],
        "category": "skills",
        "type": "proficiency",
        "behavior": "append"
    },
    {
        "triggers": ["i have experience with ", "i've worked with ", "i've used "],
        "category": "skills",
        "type": "experience",
        "behavior": "append"
    },

    # ===== GOALS =====
    {
        "triggers": ["i want to ", "i'd like to ", "i wish to "],
        "category": "goals",
        "type": "desire",
        "behavior": "append"
    },
    {
        "triggers": ["my goal is ", "my aim is ", "my objective is "],
        "category": "goals",
        "type": "objective",
        "behavior": "append"
    },
    {
        "triggers": ["i aspire to ", "i dream of ", "i hope to "],
        "category": "goals",
        "type": "aspiration",
        "behavior": "append"
    },

    # ===== PLANS =====
    {
        "triggers": ["i plan to ", "i'm planning to ", "i intend to "],
        "category": "plans",
        "type": "intention",
        "behavior": "append"
    },
    {
        "triggers": ["i will ", "i'll "],
        "category": "plans",
        "type": "future_action",
        "behavior": "append"
    },
    {
        "triggers": ["i am going to ", "i'm going to ", "i'm about to "],
        "category": "plans",
        "type": "near_future",
        "behavior": "append"
    },

    # ===== TASKS =====
    {
        "triggers": ["i need to ", "i must ", "i should "],
        "category": "tasks",
        "type": "requirement",
        "behavior": "append"
    },
    {
        "triggers": ["i have to ", "i've got to ", "i'm supposed to "],
        "category": "tasks",
        "type": "obligation",
        "behavior": "append"
    },
    {
        "triggers": ["my task is ", "my job is ", "my responsibility is "],
        "category": "tasks",
        "type": "action_item",
        "behavior": "append"
    },

    # ===== LOCATION =====
    {
        "triggers": ["i am in ", "i'm in ", "i'm currently in "],
        "category": "location",
        "type": "current_position",
        "behavior": "append"
    },
    {
        "triggers": ["i live in ", "i'm based in ", "i reside in "],
        "category": "location",
        "type": "residence",
        "behavior": "append"
    },
    {
        "triggers": ["i am located at ", "i'm located at ", "my location is "],
        "category": "location",
        "type": "geographical",
        "behavior": "append"
    },

    # ===== PROFESSION =====
    {
        "triggers": ["i am a ", "i'm a "],
        "category": "profession",
        "type": "job_title",
        "behavior": "append"
    },
    {
        "triggers": ["i work as ", "i work at ", "i'm employed as "],
        "category": "profession",
        "type": "role",
        "behavior": "append"
    },
    {
        "triggers": ["my profession is ", "my career is ", "my occupation is "],
        "category": "profession",
        "type": "career",
        "behavior": "append"
    },
]