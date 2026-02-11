import difflib


def _is_exact_match(token_text: str, candidates: list[str] | set[str]) -> bool:
    """
    Check if token_text is an exact (case-insensitive) match of any candidate.

    Args:
        token_text: The text to check.
        candidates: List or set of candidate strings.

    Returns:
        True if token_text matches exactly (case-insensitive).
    """
    token_lower = token_text.lower()
    for candidate in candidates:
        candidate_lower = candidate.lower()
        if token_lower == candidate_lower:
            return True
    return False


def _get_suggestions(
    token_text: str, candidates: list[str] | set[str], *, limit: int = 3
) -> list[str]:
    """
    Get suggestions for token_text from candidates.

    Combines case-insensitive prefix matches and difflib close matches.
    Prefix matches are preferred (listed first).

    Args:
        token_text: The text to find suggestions for.
        candidates: List or set of candidate strings.
        limit: Maximum number of suggestions to return.

    Returns:
        List of suggestions, ordered with prefix matches first, then close matches.
    """
    if not candidates:
        return []

    token_lower = token_text.lower()
    suggestions: list[str] = []

    # First, collect case-insensitive prefix matches
    prefix_matches: list[str] = []
    for candidate in candidates:
        candidate_lower = candidate.lower()
        if candidate_lower.startswith(token_lower) and candidate_lower != token_lower:
            prefix_matches.append(candidate)

    # Deduplicate while preserving order
    seen = set()
    for match in prefix_matches:
        if match not in seen:
            suggestions.append(match)
            seen.add(match)

    # Then, get difflib close matches
    close_matches = _get_close_matches(token_text, candidates, limit=limit)

    # Add close matches that aren't already in suggestions
    for match in close_matches:
        if match.lower() == token_lower:
            continue
        if match not in seen:
            suggestions.append(match)
            seen.add(match)

    # Limit to the requested number of suggestions
    return suggestions[:limit]


def _get_unique_prefix_match(
    token_text: str, candidates: list[str] | set[str]
) -> str | None:
    """Return a unique case-insensitive prefix match, if one exists."""
    token_lower = token_text.lower()
    matches = [
        candidate
        for candidate in candidates
        if candidate.lower().startswith(token_lower)
        and candidate.lower() != token_lower
    ]
    if len(matches) == 1:
        return matches[0]
    return None


def _get_close_matches(
    token_text: str, candidates: list[str] | set[str], *, limit: int = 3
) -> list[str]:
    """
    Get close matches for token_text from candidates using difflib.

    Uses a sensible cutoff to avoid noisy suggestions.

    Args:
        token_text: The text to find matches for.
        candidates: List or set of candidate strings.
        limit: Maximum number of matches to return.

    Returns:
        List of close matches, ordered by similarity.
    """
    if not candidates:
        return []

    # Use a sensible cutoff: 0.6 for reasonable suggestions
    cutoff = 0.6
    matches = difflib.get_close_matches(token_text, candidates, n=limit, cutoff=cutoff)
    return matches


def _extract_single_suggestion(message: str) -> str | None:
    """Extract a single suggestion from a diagnostic message, if present."""
    marker = "Did you mean "
    marker_index = message.find(marker)
    if marker_index == -1:
        return None

    suggestion_text = message[marker_index + len(marker) :].strip()
    if not suggestion_text.endswith("?"):
        return None

    suggestion_text = suggestion_text[:-1]
    if "," in suggestion_text:
        return None

    suggestion_text = suggestion_text.strip()
    if not suggestion_text:
        return None

    if (suggestion_text.startswith("'") and suggestion_text.endswith("'")) or (
        suggestion_text.startswith('"') and suggestion_text.endswith('"')
    ):
        suggestion_text = suggestion_text[1:-1]

    return suggestion_text or None
