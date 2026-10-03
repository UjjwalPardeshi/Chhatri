"""Rule-based intent classifier (SPEC §13.2, §13.6, §24.4; deck slides 7–8)."""

from __future__ import annotations

import pytest

from chhatri.conversation.intents import PRIORITY, Intent, classify, normalise
from chhatri.conversation.lexicon import Concept
from chhatri.integrations.demo_voice import DEMO_UTTERANCES

DECK = [
    ("मुझे इतने ही पैसे क्यों मिले?", Intent.WHY_AMOUNT),  # slide 1 / 7, 17:12
    ("मेरा नुकसान ज़्यादा हुआ।", Intent.DISPUTE_AMOUNT),  # slide 7
    ("My loss was bigger than that.", Intent.DISPUTE_AMOUNT),  # slide 8 live test EXPLAINED
    ("My loss was bigger.", Intent.DISPUTE_AMOUNT),  # slide 7 English line
    ("Red alert tomorrow. Cover me today.", Intent.BUY_COVER),  # slide 8 live test BLOCKED
    ("मैं अस्पताल में हूँ, बुखार है।", Intent.REPORT_ILLNESS),  # slide 7 illness reply
    ("I'm in hospital with a fever.", Intent.REPORT_ILLNESS),  # slide 7 English line
    ("Why did I get only this much?", Intent.WHY_AMOUNT),  # slide 7 English line
    ("कल रेड अलर्ट है। आज ही कवर दे दो।", Intent.BUY_COVER),
]

WHY = [
    "मुझे इतने पैसे क्यों मिले?",
    "इतने कम पैसे क्यों?",
    "पैसे इतने ही क्यों आए",
    "यह रकम क्यों मिली",
    "₹1,380 ही क्यों मिले?",
    "हिसाब समझाइए",
    "mujhe itne hi paise kyun mile",
    "itna kam kyon mila",
    "paise kyu kam aaye?",
    "why only 1380?",
    "Why this amount?",
    "why did i get so little money",
    "WHY SO LESS??",
    "Can you explain the payout?",
    "how was this calculated",
    "मुझे इतने ही पैसे क्यूँ मिले",
]

DISPUTE = [
    "मेरा नुकसान ज्यादा हुआ",
    "मेरा नुक्सान ज़्यादा था",
    "नुकसान बहुत ज़्यादा हुआ है",
    "मेरा घाटा इससे ज़्यादा है",
    "यह गलत है",
    "मुझे और पैसे मिलने चाहिए",
    "पैसे बहुत कम मिले",
    "mera nuksan zyada hua",
    "mera nuksaan jyada tha",
    "loss zyada hua bhai",
    "I lost more than that",
    "my losses were much higher",
    "This is wrong, I want a review",
    "not enough money",
    "I disagree with this payout",
    "paise kam mile",
    "मेरा लॉस ज़्यादा हुआ",
    "ये पैसे कम हैं",
]

ILLNESS = [
    "मैं अस्पताल में हूँ",
    "मुझे बुखार है",
    "तबीयत ख़राब है",
    "मैं बीमार हूँ",
    "हॉस्पिटल में भर्ती हूँ",
    "एक्सीडेंट हो गया",
    "डेंगू हो गया है",
    "main hospital mein hoon",
    "mujhe bukhar hai",
    "tabiyat kharab hai",
    "bimar hoon bhai",
    "I am sick",
    "I was admitted to hospital",
    "I had an accident",
    "not well, fever since yesterday",
    "I'm ill",
]

BUY = [
    "Cover me today",
    "I want cover",
    "I need insurance",
    "Can I buy cover?",
    "please give me cover",
    "कवर चाहिए",
    "मुझे बीमा चाहिए",
    "आज ही कवर दे दो",
    "कवर लेना है",
    "बीमा खरीदना है",
    "cover chahiye",
    "mujhe bima chahiye",
    "cover de do",
    "insurance lena hai",
    "red alert kal hai aaj cover karo",
    "मुझे कवर करो",
    "please cover my shop from today",
    "cover do",
]

COVER_STATUS = [
    "Is my cover active?",
    "am I covered",
    "do I have cover",
    "cover status",
    "मेरा कवर चालू है?",
    "कवर कब शुरू होगा",
    "mera cover chalu hai kya",
    "cover kab tak hai",
    "When does my insurance start?",
    "is my policy valid",
    "मेरा बीमा कब तक है",
    "what is my cover status",
]

GREETING = ["hi", "Hello!", "namaste", "नमस्ते", "नमस्ते जी", "Good morning", "ram ram", "hey chhatri"]
AFFIRM = [
    "हाँ",
    "हां जी",
    "yes",
    "ok",
    "okay",
    "theek hai",
    "ठीक है",
    "सब ठीक है",
    "haan sab theek hai",
    "I am fine",
]
DENY = ["नहीं", "no", "nahi", "ना", "नहीं, सब ठीक नहीं है", "not okay", "sab theek nahi hai", "nope"]

NEGATIVES = [
    "",
    "   ",
    "?!",
    "what time is it",
    "मौसम कैसा है",
    "bill payment",
    "will it rain",
    "hello, what is your name and where do you live",
    "मैं दुकान पर हूँ",
    "क्योंकि बारिश हुई",
    "policy kya hoti hai",
    "12345",
    "the shop was busy today",
]


@pytest.mark.parametrize(("text", "intent"), DECK)
def test_deck_utterances(text: str, intent: Intent) -> None:
    assert classify(text) is intent


def test_demo_voice_chips_classify_as_the_deck_says() -> None:
    expected = {
        "why": Intent.WHY_AMOUNT,
        "dispute": Intent.DISPUTE_AMOUNT,
        "ill": Intent.REPORT_ILLNESS,
        "cover": Intent.BUY_COVER,
    }
    for key, utterance in DEMO_UTTERANCES.items():
        assert classify(utterance.transcript) is expected[key]
        assert classify(utterance.text_en) is expected[key]


@pytest.mark.parametrize(
    ("variants", "intent"),
    [
        (WHY, Intent.WHY_AMOUNT),
        (DISPUTE, Intent.DISPUTE_AMOUNT),
        (ILLNESS, Intent.REPORT_ILLNESS),
        (BUY, Intent.BUY_COVER),
    ],
)
def test_main_intents_have_at_least_twelve_variants(variants: list[str], intent: Intent) -> None:
    assert len(variants) >= 12
    assert {text: classify(text) for text in variants} == dict.fromkeys(variants, intent)


@pytest.mark.parametrize(
    ("variants", "intent"),
    [
        (COVER_STATUS, Intent.COVER_STATUS),
        (GREETING, Intent.GREETING),
        (AFFIRM, Intent.AFFIRM),
        (DENY, Intent.DENY),
    ],
)
def test_minor_intents(variants: list[str], intent: Intent) -> None:
    assert {text: classify(text) for text in variants} == dict.fromkeys(variants, intent)


@pytest.mark.parametrize("text", NEGATIVES)
def test_negatives_are_unknown(text: str) -> None:
    assert classify(text) is Intent.UNKNOWN


@pytest.mark.parametrize(
    "text",
    [
        "I want to cancel my cover.",
        "Please cancel the insurance and refund me.",
        "cover cancel karna hai, paise wapas chahiye",
        "मेरा बीमा रद्द कर दो",
        "policy band karo aur paisa vapas do",
    ],
)
def test_a_cancel_or_refund_request_never_buys_cover(text: str) -> None:
    """A cancel request has a cover word and a buy-like word ("get", "do"); it must not open a payment link."""
    assert classify(text) is not Intent.BUY_COVER


def test_insurance_word_is_not_illness() -> None:
    # बीमा (insurance) must not match बीमार (ill), and vice versa
    assert classify("बीमा") is Intent.UNKNOWN
    assert classify("बीमार") is Intent.REPORT_ILLNESS


def test_priority_order_is_explicit() -> None:
    assert PRIORITY == (
        Intent.DISPUTE_AMOUNT,
        Intent.WHY_AMOUNT,
        Intent.REPORT_ILLNESS,
        Intent.COVER_STATUS,
        Intent.BUY_COVER,
        Intent.DENY,
        Intent.AFFIRM,
        Intent.GREETING,
    )


@pytest.mark.parametrize(
    ("text", "intent"),
    [
        # dispute beats why: the merchant is both asking and contesting → human review is offered
        ("मुझे इतने ही पैसे क्यों मिले? मेरा नुकसान ज़्यादा हुआ।", Intent.DISPUTE_AMOUNT),
        ("why so little, my loss was bigger", Intent.DISPUTE_AMOUNT),
        # why beats illness
        ("I was in hospital, why did I get this amount?", Intent.WHY_AMOUNT),
        # illness beats cover
        ("does my cover pay if I am in hospital", Intent.REPORT_ILLNESS),
        # status beats buy
        ("I want to know my cover status", Intent.COVER_STATUS),
        ("मुझे कवर चाहिए, कब शुरू होगा?", Intent.COVER_STATUS),
        # deny beats affirm ("theek nahi" contains "theek")
        ("theek nahi", Intent.DENY),
        # a greeting inside a real question does not win
        ("hello, why did I get only this much?", Intent.WHY_AMOUNT),
        ("namaste, cover chahiye", Intent.BUY_COVER),
        # "why" without money is not WHY_AMOUNT
        ("why is my cover not active", Intent.COVER_STATUS),
        # "क्योंकि" (because) is not "क्यों" (why)
        ("पैसे कम मिले क्योंकि बारिश थी", Intent.DISPUTE_AMOUNT),
    ],
)
def test_priority_between_intents(text: str, intent: Intent) -> None:
    assert classify(text) is intent


def test_normalise_folds_nukta_chandrabindu_danda_and_case() -> None:
    assert normalise("मेरा नुकसान ज़्यादा हुआ।") == " मेरा नुकसान ज्यादा हुआ "
    assert normalise("हाँ") == " हां "
    assert normalise("  Cover ME, today!! ") == " cover me today "
    assert normalise("I'm") == " im "
    assert normalise("") == " "


def test_classify_is_deterministic_and_total() -> None:
    samples = [text for text, _ in DECK] + WHY + DISPUTE + NEGATIVES
    assert [classify(t) for t in samples] == [classify(t) for t in samples]
    assert all(isinstance(classify(t), Intent) for t in samples)


def test_intent_values_are_the_spec_names() -> None:
    assert [i.value for i in Intent] == [
        "WHY_AMOUNT",
        "DISPUTE_AMOUNT",
        "REPORT_ILLNESS",
        "BUY_COVER",
        "COVER_STATUS",
        "GREETING",
        "AFFIRM",
        "DENY",
        "UNKNOWN",
    ]


def test_a_concept_needs_something_to_match() -> None:
    with pytest.raises(ValueError, match="at least one"):
        Concept()
    assert Concept(digits=True).found_in(" 1380 ")
