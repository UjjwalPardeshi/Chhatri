"""Guard function (SPEC §13.3). Reject LLM replies that make false claims or disallowed numbers."""

from __future__ import annotations

import re
from collections.abc import Iterable


def grounded(reply: str, allowed_numbers: Iterable[str]) -> bool:
    """Check if a reply is grounded in facts.

    Rejects:
    - Digit sequences not in allowed_numbers (except those in formats like ₹1,380)
    - Promises of money/approval not in the facts
    - Guarantees or assurances beyond facts

    Args:
        reply: The text to check
        allowed_numbers: List of allowed digit sequences (e.g. ["1380", "63"])

    Returns:
        True if reply is grounded; False if it contains disallowed claims
    """
    if not reply or not reply.strip():
        return True

    allowed_set = set(allowed_numbers)

    # Check for direct approval/payment claims
    # If the reply claims something is approved, paid, or guaranteed, it must be grounded in facts
    if re.search(
        r"\b(approved|approve|paid|pay|guarantee|promised)\b",
        reply,
        re.IGNORECASE,
    ):
        # This is a claim that needs to be grounded
        # For now, we reject it unless it's clearly from a template we generated
        # (templates would have come from facts, so any number should be allowed)
        # If there are NO allowed numbers and we're making approval claims, reject it
        if not allowed_set:
            # No allowed facts to ground the approval claim
            return False

    # Check for strong promises of money/approval
    promise_keywords = re.compile(
        r"\b(will|guarantee|promise|definitely|must|assure|ensure)\b.*"
        r"\b(money|rupee|paise|paisa|payment|paid|approved|approve)\b",
        re.IGNORECASE,
    )
    if promise_keywords.search(reply):
        return False

    # Extract all digit sequences from the reply
    # Match patterns like: 123, 1,234, ₹1,380, etc.
    digit_pattern = re.compile(r"[\d,]+")
    found_digits = []

    for match in digit_pattern.finditer(reply):
        digit_str = match.group(0)
        # Normalize: remove commas
        normalized = digit_str.replace(",", "")
        if normalized and normalized.isdigit():
            found_digits.append(normalized)

    # Check if all found digits are in the allowed list
    for digit in found_digits:
        if digit not in allowed_set:
            # Check if it's a single digit or very small number (likely not a currency amount)
            if len(digit) > 1 or digit not in "0123456789":
                return False

    return True
