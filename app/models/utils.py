import os


def resolve_env_key(api_key: str) -> str:
    """
    Resolve API key from value or environment variable reference.
    "env:XAI_API_KEY" → reads from os.environ
    "literal-key"     → returned as-is
    """
    if api_key.startswith("env:"):
        var_name = api_key[4:].strip()
        value = os.environ.get(var_name, "")
        if not value:
            raise ValueError(
                f"Environment variable '{var_name}' is not set.\n"
                f"Add it to your .env file or export it in your shell."
            )
        return value
    return api_key
