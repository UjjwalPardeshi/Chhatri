"""§5.2: the clause table is a committed extract of the policy wording, and it fails when the two drift apart."""

from __future__ import annotations

from pathlib import Path

from chhatri.ask.clauses import clause_table, is_clause_id, parse_clauses

WORDING = Path(__file__).resolve().parents[3] / "docs" / "02-product" / "policy-wording-and-cis.md"
EXPECTED_IDS = [
    "C1",
    "C2",
    "C3",
    "C4",
    "C4.1",
    "C4.2",
    "C4.3",
    "C4.4",
    "C5",
    "C6",
    "C7",
    "C8",
    "C9",
    "C10",
    "C11",
    "C12",
]


def test_the_extract_equals_the_policy_wording() -> None:
    extracted = parse_clauses(WORDING.read_text(encoding="utf-8"))
    table = clause_table()
    assert [c.id for c in extracted] == list(table) == EXPECTED_IDS
    assert all(table[c.id] == c for c in extracted), "run the extractor again: clauses.json is out of date"


def test_titles_are_the_wording_headings() -> None:
    table = clause_table()
    assert table["C2"].title == "Coverage: Area income loss"
    assert table["C4.1"].title == "Payout formula" and table["C4.3"].title == "Annual limit"


def test_every_clause_has_text_except_the_chapter_head_that_only_holds_sub_clauses() -> None:
    empty = [c.id for c in clause_table().values() if not c.text]
    assert empty == ["C4"]


def test_only_the_table_ids_are_valid_citations() -> None:
    assert is_clause_id("C4.3") and is_clause_id("C12")
    assert not is_clause_id("C20") and not is_clause_id("C-2291") and not is_clause_id("C4.5")
