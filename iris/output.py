"""Bounded Slack-message rendering."""
from __future__ import annotations


def split_for_slack(text: str, *, max_chars: int = 3000, max_messages: int = 3) -> tuple[str, ...]:
    """Split readable text at whitespace; cap burst size without mid-word cuts."""
    if not isinstance(text, str):
        raise TypeError("text must be a string")
    if max_chars < 1 or max_messages < 1:
        raise ValueError("message limits must be positive")
    words = text.split()
    if not words:
        return ()
    messages: list[str] = []
    current: list[str] = []
    current_size = 0
    for word in words:
        if len(word) > max_chars:
            raise ValueError("one word exceeds the Slack message limit")
        next_size = current_size + (1 if current else 0) + len(word)
        if current and next_size > max_chars:
            messages.append(" ".join(current))
            current, current_size = [word], len(word)
        else:
            current.append(word)
            current_size = next_size
    if current:
        messages.append(" ".join(current))
    if len(messages) > max_messages:
        return tuple(messages[:max_messages - 1] + ["Output truncated; ask Iris to narrow the request."])
    return tuple(messages)
