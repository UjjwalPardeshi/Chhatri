"""H19: the scam check (fs-05 section 8, AC-ASK-19)."""

from __future__ import annotations

import pytest

from chhatri.ask.scam import check_scam

SCAMS = [
    "Your Paytm KYC will expire today. Share the OTP to continue.",
    "Claim ₹50,000 now, 100% guaranteed! Pay ₹500 fee: bit.ly/x",
    "आपका क्लेम पास हो गया है। पैसे पाने के लिए ₹200 फीस भेजें।",
    "Install AnyDesk and call 98xxxxxxxx to fix your claim",
    "Kya mujhe claim ke liye OTP dena padega?",
    "Send your UPI PIN to get the payout",
    "आपको लॉटरी में इनाम मिला है, तुरंत क्लिक करें",
    "Urgent: download claim.apk and call this number to get your cashback",
]
BENIGN = [
    "Anil ji, do you have cover today?",
    "Is the link in the payment message safe?",
    "I pinned the shop location on the map",
    "Why did I get this amount?",
    "मुझे इतने ही पैसे क्यों मिले?",
    "What is the yearly limit?",
    "My loss was bigger than that",
    "क्या यह केवल बारिश के लिए है?",
]


@pytest.mark.parametrize("text", SCAMS)
def test_scam_like_text_is_flagged(text: str) -> None:
    result = check_scam(text)
    assert result.flagged and result.signals


@pytest.mark.parametrize("text", BENIGN)
def test_benign_text_is_not_flagged(text: str) -> None:
    assert not check_scam(text).flagged


def test_one_weak_signal_is_not_enough_and_two_are() -> None:
    assert not check_scam("this is urgent").flagged
    assert check_scam("urgent: guaranteed cashback").flagged


def test_the_result_holds_codes_and_never_the_text() -> None:
    result = check_scam("Share the OTP 123456")
    assert result.signals == ("CREDENTIAL_REQUEST",)
