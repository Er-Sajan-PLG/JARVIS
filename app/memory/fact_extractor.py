def extract_fact(message: str):
    msg = message.lower()

    if "i like" in msg:
        return "user likes " + msg.split("i like")[1].strip()

    if "i am" in msg:
        return "user is " + msg.split("i am")[1].strip()

    if "i prefer" in msg:
        return "user prefers " + msg.split("i prefer")[1].strip()

    if "remember that" in msg:
        return msg.replace("remember that", "user").strip()

    return None