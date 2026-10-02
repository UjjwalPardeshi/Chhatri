"""What one loaded scenario remembers about asks and speech results (fs-05 section 12, data-model 5.11).

Only the answer of an earlier ask can be voiced, and a voice question must name the `ST-` id it came from, so the app
keeps a small in-memory record of each, per scenario load (the id factory is new on every load, so the ledger is too).
A record never holds a question or a transcript; it holds the answer texts, which the merchant already saw. Each map
is bounded so a long session cannot grow it without limit.
"""

from __future__ import annotations

import weakref
from collections import OrderedDict
from dataclasses import dataclass
from typing import Final

from chhatri.ids import IdFactory

__all__ = ["AskLedger", "AskRecord", "SttRecord", "ledger_for"]

MAX_RECORDS: Final = 1000


@dataclass(frozen=True, slots=True)
class AskRecord:
    ask_id: str
    merchant_id: str
    answer_hi: str
    answer_en: str


@dataclass(frozen=True, slots=True)
class SttRecord:
    stt_id: str
    merchant_id: str
    provider: str


class AskLedger:
    def __init__(self) -> None:
        self._asks: OrderedDict[str, AskRecord] = OrderedDict()
        self._stts: OrderedDict[str, SttRecord] = OrderedDict()

    def add_ask(self, record: AskRecord) -> None:
        self._put(self._asks, record.ask_id, record)

    def add_stt(self, record: SttRecord) -> None:
        self._put(self._stts, record.stt_id, record)

    def ask(self, ask_id: str) -> AskRecord | None:
        return self._asks.get(ask_id)

    def stt(self, stt_id: str) -> SttRecord | None:
        return self._stts.get(stt_id)

    @staticmethod
    def _put[T](store: OrderedDict[str, T], key: str, value: T) -> None:
        store[key] = value
        while len(store) > MAX_RECORDS:
            store.popitem(last=False)


_LEDGERS: weakref.WeakKeyDictionary[IdFactory, AskLedger] = weakref.WeakKeyDictionary()


def ledger_for(ids: IdFactory) -> AskLedger:
    """The ledger of the scenario load that owns `ids` (a new load has a new id factory, so a new ledger)."""
    ledger = _LEDGERS.get(ids)
    if ledger is None:
        ledger = AskLedger()
        _LEDGERS[ids] = ledger
    return ledger
