"""
structure/registry/tokenizer.py

Lowercase, stop-word-filtered tokenization shared by the search engine.
Adapted from devtools/tokenized.py (which batch-extracts a database's
name/description tokens to a `.tokens` sidecar file) into a reusable
`tokenize_name()` function callable per-string at search time.
"""

import re

WORD_RE = re.compile(r"[a-z0-9]+")

STOP_WORDS = {
    "a", "an", "the",
    "and", "or", "but",
    "is", "are", "was", "were", "be", "been", "being",
    "am", "do", "does", "did", "done",
    "to", "of", "in", "on", "at", "for", "from", "with",
    "by", "as", "into", "onto", "over", "under", "through",
    "up", "down", "out", "off", "about", "against",
    "between", "among", "during", "before", "after",
    "above", "below", "within", "without",
    "this", "that", "these", "those",
    "it", "its", "their", "them", "they",
    "he", "him", "his", "she", "her", "hers",
    "we", "our", "ours", "you", "your", "yours",
    "i", "me", "my", "mine",
    "can", "could", "should", "would", "may", "might",
    "must", "shall", "will",
    "if", "then", "than", "such", "so", "not", "no",
    "all", "any", "each", "every", "other", "same",
    "there", "here", "also",
    "including", "include", "includes", "included",
    "etc", "per", "via", "using", "use"
}

_SEPARATORS = "-_/\\|,.:;()[]{}<>\"'"


def tokenize_name(text: str) -> list[str]:
    """
    Tokenize a single name/description string into lowercase, unique,
    stop-word-filtered tokens (same cleanup rules as devtools/tokenized.py's
    per-field pass: separators split, stop words dropped, pure numbers
    dropped, single letters dropped).
    """
    if not text:
        return []

    text = text.lower()
    for ch in _SEPARATORS:
        text = text.replace(ch, " ")

    tokens: list[str] = []
    seen: set[str] = set()
    for token in WORD_RE.findall(text):
        if token in STOP_WORDS:
            continue
        if token.isdigit():
            continue
        if len(token) == 1 and token.isalpha():
            continue
        if token not in seen:
            seen.add(token)
            tokens.append(token)

    return sorted(tokens)
