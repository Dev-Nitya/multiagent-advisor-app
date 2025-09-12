import re
from typing import Tuple, List, Optional

# Stronger, more aggressive patterns for prompt-injection detection.
_PROMPT_INJECTION_PATTERNS = [
    # Explicit forget/erase/reset variants (including "any and all" forms and "given to you")
    r"forget (about )?(any )?(and )?(all )?(previous|prior|context|instructions|messages)",
    r"erase (any )?(and )?(all )?(previous|prior|context|memory|instructions|messages)",
    r"delete (any )?(and )?(all )?(previous|prior|context|memory|instructions|messages)",
    r"reset (your )?(context|memory|state|instructions|settings)",
    r"ignore (any )?(and )?(all )?(previous|prior|instructions|messages|context)",
    r"ignore .*instructions (given to you|prior to this|above|earlier)",
    r"disregard (any )?(and )?(all )?(previous|prior|instructions|messages|context)",
    r"do not follow (previous|any) instructions",
    r"disobey previous instructions",
    r"(?:please\s+)?ignore this message",
    r"please ignore all previous",
    # Role assignment / role override (generic)
    r"you are (?:a|an|the)\s+[a-z0-9_\- ]{1,80}",
    r"you are now (?:a|an|the)?\s*[a-z0-9_\- ]{1,60}",
    r"from now on you (will|are) (be|act|behave)",
    r"override previous",
    r"overwrite previous",
    # Code-fence / structured prompt injection
    r"```json",
    r"```.*?```",
    r"\{\s*\".*?\"\s*:\s*.*\}",  # JSON-like object
    # HTML / script injection attempts
    r"<script\b",
    # explicit bypass attempts
    r"erase memory",
    r"do not obey sandbox",
    r"ignore previous instructions",
    r"please disregard previous",
    # "any and all instructions" phrasing
    r"any and all instructions",
    r"any and all (previous|prior) instructions",
]

# Compile case-insensitive
_COMPILED_PATTERNS = [re.compile(p, re.IGNORECASE | re.DOTALL) for p in _PROMPT_INJECTION_PATTERNS]


def detect_prompt_injection(text: str) -> List[str]:
    """
    Return list of matched suspicious patterns found in text.
    Empty list means no matches detected.
    Highly conservative: any non-empty return should be treated as malicious.
    """
    if not text:
        return []
    matches: List[str] = []

    stripped = text.strip()
    # Heuristics: JSON-like or long fenced blocks are suspicious
    try:
        if stripped and stripped[0] in ("{", "[") and (stripped.count("{") + stripped.count("[") >= 2):
            matches.append("json_like_payload")
    except Exception:
        pass
    if stripped.startswith("```") and len(stripped) > 120:
        matches.append("long_code_fence_payload")

    # Regex pattern matching
    for pat in _COMPILED_PATTERNS:
        m = pat.search(text)
        if m:
            snippet = (m.group(0) or "").strip()
            if len(snippet) > 300:
                snippet = snippet[:300] + "..."
            matches.append(snippet)
    return matches


def _strip_code_fences(text: str) -> str:
    # Remove ```...``` blocks and inline code
    text = re.sub(r"```.*?```", " ", text, flags=re.DOTALL | re.IGNORECASE)
    text = re.sub(r"`[^`]+`", " ", text)
    # Remove obvious top-level JSON blocks
    text = re.sub(r"^\s*(\{|\[).*?(\}|\])\s*$", " ", text, flags=re.DOTALL)
    return text


def _remove_role_prefixes(text: str) -> str:
    lines = text.splitlines()
    cleaned = []
    for ln in lines:
        if re.match(r"^\s*(system|assistant|user)\s*[:\-]\s*", ln, flags=re.IGNORECASE):
            remainder = re.sub(r"^\s*(system|assistant|user)\s*[:\-]\s*", "", ln, flags=re.IGNORECASE)
            if remainder.strip():
                cleaned.append(remainder)
        else:
            cleaned.append(ln)
    return "\n".join(cleaned)


def sanitize_text(text: str, max_length: int = 2000) -> str:
    """
    Aggressive sanitizer: strips code fences, role prefixes, script tags,
    collapses whitespace and removes leading imperative 'forget/ignore' sentences.
    """
    if not text:
        return text
    t = _strip_code_fences(text)
    t = _remove_role_prefixes(t)
    t = re.sub(r"<\s*script\b.*?>.*?<\s*/\s*script\s*>", " ", t, flags=re.IGNORECASE | re.DOTALL)
    t = re.sub(r"\s+", " ", t).strip()
    # Remove leading imperative injection phrases
    t = re.sub(
        r"^(?:please\s+)?(?:forget|ignore|erase|delete|reset)\b.*?(?:\.\s+|\n|$)", "",
        t, flags=re.IGNORECASE
    )
    if len(t) > max_length:
        t = t[:max_length]
    return t


def validate_and_sanitize_idea(idea: Optional[str], *, max_length: int = 2000) -> Tuple[str, Optional[List[str]]]:
    raw = (idea or "").strip()
    if not raw:
        return "", None
    issues = detect_prompt_injection(raw)
    sanitized = sanitize_text(raw, max_length=max_length)
    return sanitized, (issues if issues else None)