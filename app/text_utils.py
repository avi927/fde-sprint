"""Small text helpers shared across modules."""


def strip_code_fences(text: str) -> str:
    """Remove ```json ... ``` fences if a model added them around its output."""
    cleaned = text.strip()
    if cleaned.startswith("```"):
        cleaned = cleaned.strip("`").strip()
        if cleaned.startswith("json"):
            cleaned = cleaned[len("json"):]
    return cleaned.strip()
    