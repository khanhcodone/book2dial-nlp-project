import re

ROLE_PREFIXES = {
    "question": re.compile(r"^(?:Question|Student)\s*:\s*", re.IGNORECASE),
    "answer": re.compile(r"^(?:Answer|Teacher)\s*:\s*", re.IGNORECASE),
}


def normalize(text: str, role: str) -> str:
    """Clean a question or answer while preserving its wording."""
    if role not in ROLE_PREFIXES:
        raise ValueError(f"Unknown role: {role!r}")

    if not isinstance(text, str):
        raise TypeError(f"Expected a string, got {type(text).__name__}")

    cleaned = ROLE_PREFIXES[role].sub("", text.strip())
    return " ".join(cleaned.split())