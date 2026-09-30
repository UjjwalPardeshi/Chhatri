"""The console's live event feed (SPEC §19.2 FeedItem, §20 "live event feed").

One `FeedLog` per scenario load (ids restart at 1, SPEC §3). Items are frozen and appended in the
order things happen; `latest` returns the newest first, as the console lists them. Texts are short
English sentences written by the orchestrator; money inside them is formatted with ``format_inr``.
"""

from __future__ import annotations

import threading
from dataclasses import dataclass
from datetime import datetime
from typing import Final

from chhatri.clock import require_aware

__all__ = ["FEED_LIMIT", "FeedItem", "FeedLog"]

FEED_LIMIT: Final = 60  # items in a StateSnapshot (SPEC §19.2); older ones stay in the log


@dataclass(frozen=True, slots=True)
class FeedItem:
    """One feed line (SPEC §19.2 FeedItem)."""

    id: int
    at: datetime
    type: str
    text_en: str
    zone_id: str | None = None
    merchant_id: str | None = None


class FeedLog:
    """Append-only feed of one runtime; thread-safe."""

    def __init__(self) -> None:
        self._lock = threading.Lock()
        self._items: tuple[FeedItem, ...] = ()

    def add(
        self,
        at: datetime,
        type_: str,
        text_en: str,
        *,
        zone_id: str | None = None,
        merchant_id: str | None = None,
    ) -> FeedItem:
        """Append an item at simulated time `at`; ValueError for an empty type or text."""
        if not type_.strip() or not text_en.strip():
            raise ValueError("a feed item needs a type and a text")
        when = require_aware(at)
        with self._lock:
            item = FeedItem(len(self._items) + 1, when, type_, text_en, zone_id, merchant_id)
            self._items = (*self._items, item)
        return item

    def items(self) -> tuple[FeedItem, ...]:
        """Every item, oldest first."""
        with self._lock:
            return self._items

    def latest(self, limit: int = FEED_LIMIT) -> tuple[FeedItem, ...]:
        """The newest `limit` items, newest first."""
        if limit < 1:
            raise ValueError("limit must be at least 1")
        with self._lock:
            return tuple(reversed(self._items[-limit:]))
