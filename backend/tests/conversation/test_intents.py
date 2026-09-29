"""Tests for intent classification (SPEC §13.2). Deterministic, robust to variants."""

import pytest

from chhatri.conversation.intents import Intent, classify


class TestIntentClassification:
    """Test classify(text) → Intent enum."""

    def test_unknown_intent(self):
        assert classify("random garbage text") == Intent.UNKNOWN
        assert classify("xyz") == Intent.UNKNOWN
        assert classify("") == Intent.UNKNOWN

    # WHY_AMOUNT tests
    def test_why_amount_hindi_devanagari(self):
        # From deck slide 1: "मुझे इतने ही पैसे क्यों मिले?"
        assert (
            classify("मुझे इतने ही पैसे क्यों मिले?") == Intent.WHY_AMOUNT
        )
        assert classify("मुझे इतने ही पैसे क्यों मिले") == Intent.WHY_AMOUNT

    def test_why_amount_hindi_case_insensitive(self):
        assert (
            classify("मुझे इतने ही पैसे क्यों मिले?".upper())
            == Intent.WHY_AMOUNT
        )

    def test_why_amount_hindi_variants(self):
        # kyon/kyun/kyu variants
        assert classify("मुझे इतने ही पैसे क्यून मिले") == Intent.WHY_AMOUNT
        assert classify("मुझे इतने ही पैसे क्यु मिले") == Intent.WHY_AMOUNT

    def test_why_amount_english(self):
        assert (
            classify("Why did I get only this much?") == Intent.WHY_AMOUNT
        )
        assert classify("Why so little money?") == Intent.WHY_AMOUNT
        assert classify("why did I only get this") == Intent.WHY_AMOUNT

    def test_why_amount_hinglish(self):
        assert classify("mujhe itne hi paise kyun mile") == Intent.WHY_AMOUNT
        assert classify("Mujhe kyun itna kam mila") == Intent.WHY_AMOUNT

    def test_why_amount_with_punctuation_and_spaces(self):
        assert (
            classify("  मुझे  इतने ही पैसे क्यों मिले ?  ")
            == Intent.WHY_AMOUNT
        )

    # DISPUTE_AMOUNT tests
    def test_dispute_amount_hindi_devanagari(self):
        # From deck slide 1: "मेरा नुकसान ज़्यादा हुआ।"
        assert (
            classify("मेरा नुकसान ज़्यादा हुआ") == Intent.DISPUTE_AMOUNT
        )
        assert (
            classify("मेरा नुकसान ज़्यादा हुआ।") == Intent.DISPUTE_AMOUNT
        )

    def test_dispute_amount_hindi_variants(self):
        # nuksan/nuksaan variants
        assert (
            classify("मेरा नुक्सान ज़्यादा हुआ") == Intent.DISPUTE_AMOUNT
        )
        # zyada/jyada variants
        assert classify("मेरा नुकसान जयादा हुआ") == Intent.DISPUTE_AMOUNT
        assert classify("मेरा नुकसान जादा हुआ") == Intent.DISPUTE_AMOUNT

    def test_dispute_amount_english(self):
        assert classify("My loss was bigger") == Intent.DISPUTE_AMOUNT
        assert classify("My loss was much more") == Intent.DISPUTE_AMOUNT
        assert classify("I lost more money") == Intent.DISPUTE_AMOUNT

    def test_dispute_amount_hinglish(self):
        assert classify("mera nuksan zyada hua") == Intent.DISPUTE_AMOUNT
        assert classify("mere ko loss zyada hua") == Intent.DISPUTE_AMOUNT

    # REPORT_ILLNESS tests
    def test_report_illness_hindi_fever(self):
        assert classify("मुझे बुखार है") == Intent.REPORT_ILLNESS
        assert classify("मुझे तेज़ बुखार है") == Intent.REPORT_ILLNESS

    def test_report_illness_hindi_hospital(self):
        assert classify("मैं अस्पताल में हूँ") == Intent.REPORT_ILLNESS
        assert classify("अस्पताल जाना पड़ा") == Intent.REPORT_ILLNESS

    def test_report_illness_hindi_variants(self):
        # bukhaar/bukhar variants
        assert classify("मुझे बुखार है") == Intent.REPORT_ILLNESS
        # hospital/aspatal variants
        assert classify("मैं हॉस्पिटल में हूँ") == Intent.REPORT_ILLNESS

    def test_report_illness_english(self):
        assert classify("I have a fever") == Intent.REPORT_ILLNESS
        assert classify("I'm ill") == Intent.REPORT_ILLNESS
        assert classify("I'm in the hospital") == Intent.REPORT_ILLNESS
        assert classify("I'm sick") == Intent.REPORT_ILLNESS

    def test_report_illness_hinglish(self):
        assert classify("mujhe bukhaar hai") == Intent.REPORT_ILLNESS
        assert classify("I'm fever se pareshaan") == Intent.REPORT_ILLNESS

    # BUY_COVER tests
    def test_buy_cover_hindi_cover(self):
        # "Red alert tomorrow. Cover me today."
        assert classify("मुझे कवर दे") == Intent.BUY_COVER
        assert classify("कवर लेना है") == Intent.BUY_COVER

    def test_buy_cover_hindi_bima(self):
        assert classify("बीमा चाहिए") == Intent.BUY_COVER
        assert classify("मुझे बीमा दे दो") == Intent.BUY_COVER

    def test_buy_cover_english(self):
        assert classify("Cover me") == Intent.BUY_COVER
        assert classify("Buy cover") == Intent.BUY_COVER
        assert classify("I need insurance") == Intent.BUY_COVER
        assert classify("Get me a policy") == Intent.BUY_COVER

    def test_buy_cover_hinglish(self):
        assert classify("mujhe cover do") == Intent.BUY_COVER
        assert classify("insurance chaiye") == Intent.BUY_COVER

    # COVER_STATUS tests
    def test_cover_status_hindi(self):
        assert (
            classify("मेरा कवर कब शुरू होगा?") == Intent.COVER_STATUS
        )
        assert classify("कवर के बारे में बताओ") == Intent.COVER_STATUS

    def test_cover_status_english(self):
        assert (
            classify("When does my cover start?")
            == Intent.COVER_STATUS
        )
        assert classify("Tell me about my coverage") == Intent.COVER_STATUS

    # AFFIRM and DENY tests
    def test_affirm_hindi(self):
        assert classify("हाँ") == Intent.AFFIRM
        assert classify("जी") == Intent.AFFIRM
        assert classify("ठीक है") == Intent.AFFIRM

    def test_affirm_english(self):
        assert classify("Yes") == Intent.AFFIRM
        assert classify("OK") == Intent.AFFIRM
        assert classify("Okay") == Intent.AFFIRM
        assert classify("Sure") == Intent.AFFIRM

    def test_deny_hindi(self):
        assert classify("नहीं") == Intent.DENY
        assert classify("ना") == Intent.DENY

    def test_deny_english(self):
        assert classify("No") == Intent.DENY
        assert classify("Nope") == Intent.DENY

    # GREETING tests
    def test_greeting_hindi(self):
        assert classify("नमस्ते") == Intent.GREETING
        assert classify("सलाम") == Intent.GREETING

    def test_greeting_english(self):
        assert classify("Hello") == Intent.GREETING
        assert classify("Hi") == Intent.GREETING
        assert classify("Hey") == Intent.GREETING

    # Priorities for mixed messages
    def test_priority_why_amount_over_others(self):
        # WHY_AMOUNT should take priority if "kyun"/"why" is present
        text = "मेरा नुकसान ज़्यादा हुआ लेकिन मुझे इतने ही पैसे क्यों मिले"
        assert classify(text) == Intent.WHY_AMOUNT

    def test_priority_dispute_over_general(self):
        text = "मेरा नुकसान ज़्यादा हुआ"
        assert classify(text) == Intent.DISPUTE_AMOUNT

    # Robustness
    def test_robustness_extra_spaces(self):
        assert classify("  हाँ  ") == Intent.AFFIRM
        assert classify("   नहीं   ") == Intent.DENY

    def test_robustness_mixed_case_english(self):
        assert classify("YES") == Intent.AFFIRM
        assert classify("No") == Intent.DENY
        assert classify("HELLO") == Intent.GREETING
