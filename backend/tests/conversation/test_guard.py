"""Tests for guard function (SPEC §13.3). Reject digit sequences and false promises."""

import pytest

from chhatri.conversation.guard import grounded


class TestGuarded:
    """Test grounded(reply, allowed_numbers) function."""

    def test_grounded_no_numbers_is_safe(self):
        # Safe text without numbers
        reply = "Thank you for this help"
        assert grounded(reply, []) is True
        assert grounded(reply, ["1000", "2000"]) is True

    def test_grounded_allowed_number(self):
        # Digit sequence in allowed list
        reply = "I got ₹1,380"
        assert grounded(reply, ["1380", "1,380"]) is True

    def test_grounded_disallowed_number(self):
        # Digit sequence NOT in allowed list
        reply = "I got ₹5,000"
        assert grounded(reply, ["1380", "2000"]) is False

    def test_grounded_digit_sequence_normalization(self):
        # "₹1,380" should match "1380" (digits only)
        reply = "I got ₹1,380"
        assert grounded(reply, ["1380"]) is True
        # But not if the digit sequence is not in the list
        assert grounded(reply, ["138"]) is False

    def test_grounded_rejects_money_promises(self):
        # Promises of money not grounded in facts
        reply = "I'll give you ₹5,000 tomorrow"
        assert grounded(reply, []) is False

    def test_grounded_rejects_approval_promises(self):
        # False promises of approval
        reply = "Your claim is approved!"
        assert grounded(reply, []) is False

        reply = "You're definitely getting paid"
        assert grounded(reply, []) is False

    def test_grounded_rejects_assurances_not_facts(self):
        # Assurances that go beyond facts
        reply = "I promise you'll get money"
        assert grounded(reply, []) is False

    def test_grounded_rejects_guarantees(self):
        reply = "I guarantee this will work"
        assert grounded(reply, []) is False

    def test_grounded_true_when_empty_reply(self):
        # Empty or whitespace-only reply
        assert grounded("", []) is True
        assert grounded("   ", []) is True

    def test_grounded_allows_template_text(self):
        # Template text from the system should be allowed
        reply = "Your usual Tuesday: ₹4,380. Your area fell 63%. Chhatri pays half the lost sales."
        allowed = ["4380", "4,380", "63"]
        assert grounded(reply, allowed) is True

    def test_grounded_rejects_multiple_disallowed_numbers(self):
        reply = "You got ₹5,000 and then ₹3,000"
        assert grounded(reply, ["1000"]) is False

    def test_grounded_hindi_promises(self):
        # Hindi: "मैं आपको पैसे दूंगा"
        reply = "मैं आपको ₹5,000 दूंगा"
        assert grounded(reply, []) is False

    def test_grounded_mixed_hindi_english(self):
        reply = "Your claim is मंज़ूर (approved)"
        assert grounded(reply, []) is False
