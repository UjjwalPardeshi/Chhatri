"""The policy clauses C1 to C12 and C4.1 to C4.4 as a table (fs-05 section 5.2, H17).

`backend/data/policy/clauses.json` is a committed extract of `docs/02-product/policy-wording-and-cis.md`; a test
fails when the two differ. `parse_clauses` is the extractor. Valid citation ids are exactly the ids in the table.
"""

from __future__ import annotations

import json
import re
from collections.abc import Mapping
from dataclasses import dataclass
from functools import lru_cache
from pathlib import Path
from types import MappingProxyType
from typing import Final

__all__ = ["CLAUSES_PATH", "Clause", "clause_table", "is_clause_id", "parse_clauses"]

CLAUSES_PATH: Final = Path(__file__).resolve().parents[2] / "data" / "policy" / "clauses.json"
_HEADING: Final = re.compile(r"^(#{2,3}) (C\d{1,2}(?:\.\d)?)[.:]? (.+?)\s*$")
_ANY_HEADING: Final = re.compile(r"^#{1,3} ")
_RULE: Final = "---"


@dataclass(frozen=True, slots=True)
class Clause:
    id: str
    title: str
    text: str


def parse_clauses(markdown: str) -> tuple[Clause, ...]:
    """Every `## Cn.` and `### Cn.m` section of the policy wording, in document order."""
    found: list[tuple[str, str, list[str]]] = []
    current: list[str] | None = None
    for line in markdown.splitlines():
        match = _HEADING.match(line)
        if match:
            current = []
            found.append((match.group(2), match.group(3), current))
        elif _ANY_HEADING.match(line):
            current = None
        elif current is not None and line.strip() != _RULE:
            current.append(line)
    return tuple(Clause(cid, title, "\n".join(body).strip()) for cid, title, body in found)


@lru_cache(maxsize=1)
def clause_table() -> Mapping[str, Clause]:
    """The committed extract, by clause id."""
    raw = json.loads(CLAUSES_PATH.read_text(encoding="utf-8"))
    return MappingProxyType({row["id"]: Clause(row["id"], row["title"], row["text"]) for row in raw})


def is_clause_id(value: str) -> bool:
    return value in clause_table()
