"""
Code-based lexical stripping for AI-style vocabulary and platitudes.
Enforces deterministic harness constraints from AGENTS.md.
"""

import re
from typing import List, Tuple

# Patterns to strip completely (e.g. conversational filler, AI throat-clearing)
AI_FILLER_PATTERNS: List[re.Pattern] = [
    # English fillers
    re.compile(
        r"(?i)\b(?:in\s+today's\s+fast-paced\s+(?:world|digital\s+landscape|era|society)|in\s+a\s+fast-paced\s+world|in\s+an\s+ever-changing\s+world)\b[,\s]*"
    ),
    re.compile(
        r"(?i)\b(?:it\s+is\s+(?:crucial|important|essential)\s+to\s+(?:remember|note|recognize)(?:\s+that)?)\b[,\s]*"
    ),
    re.compile(
        r"(?i)\b(?:it's\s+(?:worth\s+noting|important\s+to\s+note|crucial\s+to\s+remember)(?:\s+that)?)\b[,\s]*"
    ),
    re.compile(r"(?i)\b(?:at\s+the\s+end\s+of\s+the\s+day)\b[,\s]*"),
    re.compile(r"(?i)\b(?:all\s+in\s+all|in\s+summary|in\s+conclusion)\s*,\s*"),
    re.compile(r"(?i)\b(?:without\s+further\s+ado)\b[,\s]*"),
    # Chinese fillers (pure ASCII unicode escapes to avoid terminal/platform codepage corruption)
    re.compile(
        r"\u5728\u5f53\u4eca(?:\u5feb\u901f\u53d1\u5c55\u7684|\u65e5\u65b0\u6708\u5f02\u7684|\u77ac\u606f\u4e07\u53d8\u7684|\u5feb\u8282\u594f\u7684)?(?:\u65f6\u4ee3|\u793e\u4f1a|\u4e16\u754c)\u4e2d?[\uff0c,]?\s*"
    ),
    re.compile(
        r"(?:\u4e0d\u53ef\u5426\u8ba4\u7684\u662f|\u503c\u5f97\u6ce8\u610f\u7684\u662f|\u663e\u800c\u6613\u89c1\u7684\u662f)[\uff0c,]?\s*"
    ),
    re.compile(
        r"(?:\u603b\u800c\u8a00\u4e4b|\u7efc\u4e0a\u6240\u8ff0|\u603b\u7684\u6765\u8bf4)[\uff0c,]?\s*"
    ),
    re.compile(r"\u72b9\u5982\u4e00\u628a\u53cc\u5203\u5251[\uff0c,]?\s*"),
]

# Replacement pairs for clich?d metaphors / phrases -> direct language
AI_REPLACEMENT_PATTERNS: List[Tuple[re.Pattern, str]] = [
    (re.compile(r"(?i)\bdelve\s+into\b"), "explore"),
    (re.compile(r"(?i)\bdelving\s+into\b"), "exploring"),
    (re.compile(r"(?i)\bdelves\s+into\b"), "explores"),
    (re.compile(r"(?i)\brich\s+tapestry\b"), "diverse fabric"),
    (re.compile(r"(?i)\btapestry\s+of\b"), "fabric of"),
    (
        re.compile(
            r"(?i)\b(?:stands?\s+as\s+a\s+testament\s+to|serves?\s+as\s+a\s+testament\s+to|a\s+testament\s+to)\b"
        ),
        "evidence of",
    ),
    (re.compile(r"(?i)\b(?:beacon\s+of\s+hope|a\s+beacon\s+for)\b"), "guide for"),
    (
        re.compile(r"(?i)\bnavigating\s+the\s+(?:complex\s+)?landscape\s+of\b"),
        "navigating",
    ),
]


def strip_ai_lexicon(text: str) -> str:
    """
    Strips or replaces AI-style vocabulary, clich? phrases, and filler
    from the provided text using code-based regex blacklists.
    """
    if not text:
        return text

    cleaned = text
    # 1. Strip filler phrases
    for pattern in AI_FILLER_PATTERNS:
        cleaned = pattern.sub("", cleaned)

    # 2. Replace clich? metaphors
    for pattern, replacement in AI_REPLACEMENT_PATTERNS:
        cleaned = pattern.sub(replacement, cleaned)

    # 3. Clean up duplicated whitespace or broken punctuation from removals
    cleaned = re.sub(r"[ \t]+", " ", cleaned)
    cleaned = re.sub(r"^[\s,]+", "", cleaned)
    cleaned = re.sub(r"\n\s*\n\s*\n+", "\n\n", cleaned)
    cleaned = re.sub(r" +([,\.?!;:])", r"\1", cleaned)

    # Capitalize first letter of sentence if a filler was stripped at start of sentence/paragraph
    cleaned = re.sub(
        r"(?:^|\.\s+|\n+)([a-z])", lambda m: m.group(0).upper(), cleaned
    )

    return cleaned.strip()


def compute_accurate_word_count(text: str) -> int:
    """
    Computes an accurate word or character count:
    - Counts alphanumeric words (handling apostrophes, curly quotes, and hyphens without counting standalone punctuation).
    - Counts CJK characters.
    """
    if not text:
        return 0

    stripped = text.strip()
    cjk_chars = len(re.findall(r"[\u4e00-\u9fff]", stripped))
    non_cjk_words = len(
        re.findall(r"[a-zA-Z0-9]+(?:['\u2019\-][a-zA-Z0-9]+)*", stripped)
    )
    return cjk_chars + non_cjk_words
