"""The docs quote the product exactly: catalogue strings, golden numbers, make targets, paths."""

from __future__ import annotations

import re
from pathlib import Path

import pytest
from chhatri.conversation.messages import bilingual, render

DOCS = (
    "README.md",
    "docs/ARCHITECTURE.md",
    "docs/DEMO.md",
    "docs/INTEGRATIONS.md",
    "docs/SECURITY.md",
)
ANIL = {"name_hi": "अनिल", "name_en": "Anil"}
DEMO_MESSAGES = [
    ("AREA_PAYOUT_INTRO", {**ANIL, "drop": 63}),
    ("HOLIDAY_GRANTED", {"instalment": "₹600"}),
    ("HOLIDAY_GRANTED_TODAY", {"instalment": "₹600"}),
    ("SOUNDBOX", {"amount": "₹1,380"}),
    (
        "EXPLAIN_AREA",
        {
            "weekday_hi": "मंगलवार",
            "weekday_en": "Tuesday",
            "expected": "₹4,380",
            "drop": 63,
        },
    ),
    ("DISPUTE_ACK", {}),
    ("CHECKIN_SILENT", {"name_hi": "अनिल"}),
    ("ASK_SLIP", {}),
    ("PERSONAL_PAID", {**ANIL, "amount": "₹1,500"}),
    ("SLIP_TO_HUMAN", {}),
    ("OFFICER_APPROVED", {**ANIL, "amount": "₹1,500"}),
    ("COVER_BLOCKED", {"starts_on_hi": "25 अगस्त", "starts_on_en": "25 August"}),
]
SPEC_172_STRINGS = (
    "Red alert from 14:00",
    "37% of expected for 3 hours",
    "46 of 46 prepaid",
    "17:04, with the settlement",
    "₹58,900 · instalments paused",
    "Why Zone 9 got nothing: its sales fell to 61% on a day with no weather alert. That's a slow day, "
    "not a loss event, so Chhatri doesn't pay.",
    "Z7 · 37% · 46 shops",
    "½ × ₹4,380 × 63% = ₹1,380",
    "₹4,380 का 63% = ₹2,759.40; उसका आधा = ₹1,380",
    "Sent to a claims officer · case C-2291",
)


def _read(repo_root: Path, name: str) -> str:
    return (repo_root / name).read_text(encoding="utf-8")


def _flat(text: str) -> str:
    """Markdown text with line wraps and quote markers removed, for phrase matching."""
    return re.sub(r"\s+", " ", re.sub(r"\n\s*(?:>\s*)?", " ", text))


@pytest.mark.parametrize(("key", "facts"), DEMO_MESSAGES, ids=[k for k, _ in DEMO_MESSAGES])
def test_demo_quotes_the_catalogue_exactly(repo_root: Path, key: str, facts: dict[str, object]) -> None:
    demo = _flat(_read(repo_root, "docs/DEMO.md"))
    hindi, english = bilingual(key, **facts)
    assert hindi in demo, hindi
    assert english in demo, english


def test_demo_quotes_the_spec_golden_strings(repo_root: Path) -> None:
    demo = _flat(_read(repo_root, "docs/DEMO.md"))
    for text in SPEC_172_STRINGS:
        assert text in demo, text
    assert render("CASE_CHIP", "en", case_id="C-2291") in demo
    for number in (
        "312",
        "₹1,380",
        "₹4,380",
        "₹1,500",
        "₹600",
        "A-20250818-01",
        "S-0142",
        "S-0907",
    ):
        assert number in demo


def test_whatsapp_templates_match_the_catalogue(repo_root: Path) -> None:
    text = _read(repo_root, "docs/INTEGRATIONS.md")
    intro = render("AREA_PAYOUT_INTRO", "hi", name_hi="{{1}}", name_en="x", drop="{{2}}")
    card = render("PAYOUT_CARD", "hi")
    assert f"नमस्ते {intro} {{{{3}}}} {card}।" in text
    assert "नमस्ते " + render("CHECKIN_SILENT", "hi", name_hi="{{1}}") in text
    assert "`chhatri_area_payout`" in text and "`chhatri_checkin`" in text


def test_every_make_target_named_in_docs_exists(repo_root: Path) -> None:
    makefile = _read(repo_root, "Makefile")
    targets = set(re.findall(r"^([a-z0-9-]+):", makefile, flags=re.M))
    for name in DOCS:
        for target in re.findall(r"`make ([a-z0-9-]+)", _read(repo_root, name)):
            assert target in targets, f"{name}: make {target}"


@pytest.mark.parametrize(
    "path",
    [
        "backend/scripts/build_data.py",
        "backend/scripts/demo_check.py",
        "backend/data/weather",
        "backend/chhatri/workflows/definitions.py",
        "backend/chhatri/integrations/whatsapp_payloads.py",
        "backend/chhatri/conversation/notifications.py",
        "scripts/n8n_workflows.py",
        "scripts/n8n_selftest.py",
        "scripts/init_env.py",
        "n8n/entrypoint.sh",
        "n8n/workflows/chhatri-payout.json",
        "frontend/nginx.conf",
        ".github/workflows/ci.yml",
    ],
)
def test_paths_named_in_docs_exist(repo_root: Path, path: str) -> None:
    assert (repo_root / path).exists()
    stem = Path(path).name.split(".")[0].removeprefix("chhatri-")
    assert any(stem in _read(repo_root, name) for name in DOCS), f"{path} is not mentioned in the docs"
