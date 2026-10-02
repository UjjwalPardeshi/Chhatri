"""AC-EVAL-17: no held-out question, reply or utterance appears in a prompt, a word list, a rule file or a template.

A held-out item pasted into the code that answers it makes its figure meaningless (plan section 9). The scan reads every
Python and YAML file of the packages that build prompts, hold word lists, rules or the message catalogue, normalised
(case-folded, spaces collapsed), and fails on any held-out text found inside them.
"""

from __future__ import annotations

import re
import unicodedata
from pathlib import Path
from typing import Final

import pytest

from chhatri.evals.fixtures import FIXTURE_DIR, HELD_OUT_FILES, load_rows

PACKAGE: Final = Path(__file__).resolve().parents[2] / "chhatri"
# Prompts (ask, integrations), word lists and templates (conversation, ask, precheck), rules (policy).
SCANNED: Final = ("ask", "conversation", "integrations", "policy", "precheck", "ai", "detect")
TEXT_FIELDS: Final = ("text", "reply", "question", "utterance", "transcript")
MIN_CHARS: Final = 12  # shorter strings ("hello", "हाँ") are ordinary words a list may hold on its own


def normalise(text: str) -> str:
    return re.sub(r"\s+", " ", unicodedata.normalize("NFC", text)).strip().casefold()


def held_out_texts() -> list[tuple[str, str]]:
    found: list[tuple[str, str]] = []
    for name in HELD_OUT_FILES:
        if not (FIXTURE_DIR / name).exists():
            continue
        for row in load_rows(name):
            if row["split"] != "held_out":
                continue
            found += [(f"{name}:{row['id']}", normalise(str(row[f]))) for f in TEXT_FIELDS if row.get(f)]
    return [(where, text) for where, text in found if len(text) >= MIN_CHARS]


def corpus() -> str:
    files = [
        p for folder in SCANNED for p in sorted((PACKAGE / folder).rglob("*")) if p.suffix in (".py", ".yaml")
    ]
    return "\n".join(normalise(p.read_text(encoding="utf-8")) for p in files)


def test_there_are_held_out_items_to_protect() -> None:
    assert len(held_out_texts()) >= 10


def test_no_held_out_text_is_in_a_prompt_word_list_rule_or_template() -> None:
    code = corpus()
    leaked = [where for where, text in held_out_texts() if text in code]
    assert leaked == [], f"held-out items found in the code: {leaked}; move them to dev"


@pytest.mark.parametrize("planted", ["planted held-out question text"])
def test_the_scan_finds_a_planted_leak(planted: str) -> None:
    assert normalise(planted) in normalise(f'PROMPT = """Answer: {planted.upper()}"""')
