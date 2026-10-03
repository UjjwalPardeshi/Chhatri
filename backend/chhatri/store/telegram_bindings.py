"""Which Telegram chat belongs to which demo merchant (the `/start S-0142` deep link binds, `/stop` unbinds).

A chat is a real person's phone, so the binding is live-world state like the WhatsApp `InboundGate`: it is process-wide
and survives a scenario reload (the store is rebuilt on every load, the chat on the presenter's phone is not).
One chat serves one merchant and one merchant has one chat; the newest `/start` wins. Only demo merchants are bound:
`bind` takes the merchant's `is_demo` flag from the caller, which has read it from the synthetic city (ADR 0009).
Thread-safe, in memory, never holds a token or a phone number; chat ids are not logged.

The merchant's choice of Telegram is kept here too (`remember_choice`), for as long as their chat stays linked: a
scenario load makes a new `Store` and would otherwise send the stage phone's messages back to WhatsApp while the console
still shows Telegram (demo-day L5). `sticky_channel` is TELEGRAM only while the choice is remembered and a chat is
bound; choosing WhatsApp, `/stop` (`unbind`) and `clear` forget it, and with no chat linked (the simulator) a load
starts again on the merchant's default.
"""

from __future__ import annotations

import threading
from typing import Final

from chhatri.domain.enums import PreferredChannel

__all__ = ["LIVE_TELEGRAM_BINDINGS", "TelegramBindings"]


class TelegramBindings:
    """Two-way map between Telegram chat ids and merchant ids, plus the bot's username once `getMe` has said it."""

    def __init__(self) -> None:
        self._lock = threading.Lock()
        self._chat_by_merchant: dict[str, int] = {}
        self._merchant_by_chat: dict[int, str] = {}
        self._bot_username: str | None = None
        self._telegram_chosen: set[str] = set()

    def bind(self, chat_id: int, merchant_id: str) -> None:
        """Bind `chat_id` to `merchant_id`, releasing whatever either of them was bound to before."""
        with self._lock:
            self._release_chat(chat_id)
            old_chat = self._chat_by_merchant.pop(merchant_id, None)
            if old_chat is not None:
                self._merchant_by_chat.pop(old_chat, None)
            self._chat_by_merchant[merchant_id] = chat_id
            self._merchant_by_chat[chat_id] = merchant_id

    def unbind(self, chat_id: int) -> str | None:
        """Release `chat_id`; the merchant it served, or None when it was not bound."""
        with self._lock:
            return self._release_chat(chat_id)

    def _release_chat(self, chat_id: int) -> str | None:
        merchant_id = self._merchant_by_chat.pop(chat_id, None)
        if merchant_id is not None:
            self._chat_by_merchant.pop(merchant_id, None)
            self._telegram_chosen.discard(merchant_id)
        return merchant_id

    def remember_choice(self, merchant_id: str, channel: PreferredChannel) -> None:
        """TELEGRAM is remembered across scenario loads (while a chat is bound); WHATSAPP forgets it."""
        with self._lock:
            if PreferredChannel(channel) is PreferredChannel.TELEGRAM:
                self._telegram_chosen.add(merchant_id)
            else:
                self._telegram_chosen.discard(merchant_id)

    def sticky_channel(self, merchant_id: str) -> PreferredChannel | None:
        """TELEGRAM when the merchant chose it and their chat is still linked, else None (the run decides)."""
        with self._lock:
            kept = merchant_id in self._telegram_chosen and merchant_id in self._chat_by_merchant
            return PreferredChannel.TELEGRAM if kept else None

    def merchant_for(self, chat_id: int) -> str | None:
        with self._lock:
            return self._merchant_by_chat.get(chat_id)

    def chat_for(self, merchant_id: str) -> int | None:
        with self._lock:
            return self._chat_by_merchant.get(merchant_id)

    def bound_merchants(self) -> tuple[str, ...]:
        with self._lock:
            return tuple(sorted(self._chat_by_merchant))

    def clear(self) -> None:
        with self._lock:
            self._chat_by_merchant.clear()
            self._merchant_by_chat.clear()
            self._telegram_chosen.clear()
            self._bot_username = None

    @property
    def bot_username(self) -> str | None:
        with self._lock:
            return self._bot_username

    def set_bot_username(self, username: str | None) -> None:
        with self._lock:
            self._bot_username = username

    def deep_link(self, merchant_id: str) -> str | None:
        """`https://t.me/<bot>?start=<merchant>` once the bot's username is known."""
        username = self.bot_username
        return f"https://t.me/{username}?start={merchant_id}" if username else None


LIVE_TELEGRAM_BINDINGS: Final = TelegramBindings()  # process-wide: the chats outlive scenario loads
