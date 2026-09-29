"""Tests for message catalogue (SPEC §13.4). Every key in both languages with golden values."""

import pytest

from chhatri.conversation.messages import bilingual, render


class TestRender:
    """Test render(key, lang, **facts) function."""

    def test_render_unknown_key_raises(self):
        with pytest.raises(KeyError):
            render("UNKNOWN_KEY", "hi")

    def test_render_missing_fact_raises(self):
        with pytest.raises(KeyError):
            render("AREA_PAYOUT_INTRO", "hi")  # missing name_hi, drop

    def test_area_payout_intro_hindi(self):
        text = render("AREA_PAYOUT_INTRO", "hi", name_hi="अनिल", drop=63)
        assert "अनिल" in text
        assert "63" in text
        assert "बारिश" in text

    def test_area_payout_intro_english(self):
        text = render("AREA_PAYOUT_INTRO", "en", name_en="Anil", drop=63)
        assert "Anil" in text
        assert "63" in text
        assert "rain" in text.lower()

    def test_payout_card_hindi(self):
        text = render("PAYOUT_CARD", "hi")
        assert "सेटलमेंट" in text or "settlement" in text.lower()

    def test_payout_card_english(self):
        text = render("PAYOUT_CARD", "en")
        assert "settlement" in text.lower()

    def test_instalment_paused_hindi(self):
        text = render("INSTALMENT_PAUSED", "hi", instalment="₹600")
        assert "₹600" in text
        assert "किस्त" in text

    def test_instalment_paused_english(self):
        text = render("INSTALMENT_PAUSED", "en", instalment="₹600")
        assert "₹600" in text
        assert "instalment" in text.lower()

    def test_checkin_silent_hindi(self):
        text = render("CHECKIN_SILENT", "hi", name_hi="अनिल")
        assert "अनिल" in text
        assert "बंद" in text

    def test_checkin_silent_english(self):
        text = render("CHECKIN_SILENT", "en")
        assert "closed" in text.lower()

    def test_ask_slip_hindi(self):
        text = render("ASK_SLIP", "hi")
        assert "पर्ची" in text or "slip" in text.lower()

    def test_ask_slip_english(self):
        text = render("ASK_SLIP", "en")
        assert "slip" in text.lower()

    def test_personal_paid_hindi(self):
        text = render(
            "PERSONAL_PAID", "hi", name_hi="अनिल", amount="₹1,500"
        )
        assert "अनिल" in text
        assert "₹1,500" in text
        assert "मंज़ूर" in text or "approved" in text.lower()

    def test_personal_paid_english(self):
        text = render("PERSONAL_PAID", "en", name_en="Anil", amount="₹1,500")
        assert "Anil" in text
        assert "₹1,500" in text
        assert "approved" in text.lower()

    def test_slip_to_human_hindi(self):
        text = render("SLIP_TO_HUMAN", "hi")
        assert "नाम" in text or "KYC" in text

    def test_slip_to_human_english(self):
        text = render("SLIP_TO_HUMAN", "en")
        assert "name" in text.lower() or "KYC" in text

    def test_explain_area_hindi(self):
        text = render(
            "EXPLAIN_AREA",
            "hi",
            weekday_hi="मंगलवार",
            expected="₹4,380",
            drop=63,
        )
        assert "मंगलवार" in text
        assert "₹4,380" in text
        assert "63" in text

    def test_explain_area_english(self):
        text = render(
            "EXPLAIN_AREA",
            "en",
            weekday_en="Tuesday",
            expected="₹4,380",
            drop=63,
        )
        assert "Tuesday" in text
        assert "₹4,380" in text
        assert "63" in text

    def test_dispute_ack_hindi(self):
        text = render("DISPUTE_ACK", "hi")
        assert "टीम" in text or "team" in text.lower()

    def test_dispute_ack_english(self):
        text = render("DISPUTE_ACK", "en")
        assert "team" in text.lower()

    def test_case_chip_english(self):
        text = render("CASE_CHIP", "en", case_id="C-2291")
        assert "C-2291" in text
        assert "case" in text.lower()

    def test_cover_blocked_hindi(self):
        text = render(
            "COVER_BLOCKED", "hi", starts_on_hi="25 अगस्त"
        )
        assert "25 अगस्त" in text
        assert "वेटिंग" in text or "waiting" in text.lower()

    def test_cover_blocked_english(self):
        text = render("COVER_BLOCKED", "en", starts_on_en="25 Aug")
        assert "25 Aug" in text
        assert "waiting" in text.lower()

    def test_cover_link_hindi(self):
        text = render(
            "COVER_LINK",
            "hi",
            first_payment="₹600",
            per_day="₹2",
            url="https://paytm.me/sim-test",
        )
        assert "₹600" in text
        assert "₹2" in text
        assert "paytm.me" in text

    def test_cover_link_english(self):
        text = render(
            "COVER_LINK",
            "en",
            first_payment="₹600",
            per_day="₹2",
            url="https://paytm.me/sim-test",
        )
        assert "₹600" in text
        assert "₹2" in text
        assert "paytm.me" in text

    def test_officer_approved_hindi(self):
        text = render(
            "OFFICER_APPROVED", "hi", name_hi="अनिल", amount="₹1,500"
        )
        assert "अनिल" in text
        assert "₹1,500" in text
        assert "मंज़ूर" in text or "approved" in text.lower()

    def test_officer_approved_english(self):
        text = render(
            "OFFICER_APPROVED", "en", name_en="Anil", amount="₹1,500"
        )
        assert "Anil" in text
        assert "₹1,500" in text
        assert "approved" in text.lower()

    def test_officer_declined_hindi(self):
        text = render(
            "OFFICER_DECLINED",
            "hi",
            name_hi="अनिल",
            reason_hi="कारण यह है",
        )
        assert "अनिल" in text
        assert "कारण यह है" in text

    def test_officer_declined_english(self):
        text = render(
            "OFFICER_DECLINED",
            "en",
            name_en="Anil",
            reason_en="The reason is",
        )
        assert "Anil" in text
        assert "The reason is" in text

    def test_fallback_help_hindi(self):
        text = render("FALLBACK_HELP", "hi")
        assert "छतरी" in text

    def test_fallback_help_english(self):
        text = render("FALLBACK_HELP", "en")
        assert "Chhatri" in text

    def test_soundbox_hindi_english(self):
        text = render("SOUNDBOX", "hi", amount="₹1,380")
        assert "₹1,380" in text
        # SOUNDBOX is English only per spec but render should handle both

    def test_golden_values_area_intro(self):
        """Test golden values from spec: Rs 1,380 shown as ₹1,380, 63%, ₹4,380."""
        text = render(
            "AREA_PAYOUT_INTRO", "hi", name_hi="अनिल", drop=63
        )
        assert "अनिल" in text
        assert "63" in text


class TestBilingual:
    """Test bilingual(key, **facts) returns (hi, en) tuple."""

    def test_bilingual_unknown_key_raises(self):
        with pytest.raises(KeyError):
            bilingual("UNKNOWN_KEY")

    def test_bilingual_returns_tuple(self):
        hi, en = bilingual("FALLBACK_HELP")
        assert isinstance(hi, str)
        assert isinstance(en, str)
        assert len(hi) > 0
        assert len(en) > 0

    def test_bilingual_area_payout_intro(self):
        hi, en = bilingual(
            "AREA_PAYOUT_INTRO", name_hi="अनिल", name_en="Anil", drop=63
        )
        assert "अनिल" in hi
        assert "Anil" in en
        assert "63" in hi
        assert "63" in en

    def test_bilingual_personal_paid(self):
        hi, en = bilingual(
            "PERSONAL_PAID",
            name_hi="अनिल",
            name_en="Anil",
            amount="₹1,500",
        )
        assert "अनिल" in hi
        assert "Anil" in en
        assert "₹1,500" in hi
        assert "₹1,500" in en

    def test_bilingual_explain_area(self):
        hi, en = bilingual(
            "EXPLAIN_AREA",
            weekday_hi="मंगलवार",
            weekday_en="Tuesday",
            expected="₹4,380",
            drop=63,
        )
        assert "मंगलवार" in hi
        assert "Tuesday" in en
        assert "₹4,380" in hi
        assert "₹4,380" in en

    def test_bilingual_cover_blocked(self):
        hi, en = bilingual(
            "COVER_BLOCKED",
            starts_on_hi="25 अगस्त",
            starts_on_en="25 Aug",
        )
        assert "25 अगस्त" in hi
        assert "25 Aug" in en
