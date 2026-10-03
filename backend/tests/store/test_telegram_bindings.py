"""Chat <-> demo merchant bindings and the per-run preferred channel."""

from __future__ import annotations

import pytest

from chhatri.domain.enums import PreferredChannel
from chhatri.store.repositories import Store
from chhatri.store.telegram_bindings import TelegramBindings
from tests.conversation.conftest import MiniCity


def test_bind_is_two_way_and_unbind_releases_both_sides() -> None:
    bindings = TelegramBindings()
    bindings.bind(10, "S-0142")
    assert (bindings.merchant_for(10), bindings.chat_for("S-0142")) == ("S-0142", 10)
    assert bindings.unbind(10) == "S-0142"
    assert (bindings.merchant_for(10), bindings.chat_for("S-0142")) == (None, None)
    assert bindings.unbind(10) is None


def test_the_newest_start_wins_on_both_sides() -> None:
    bindings = TelegramBindings()
    bindings.bind(10, "S-0142")
    bindings.bind(11, "S-0142")  # a second phone takes over the merchant
    assert bindings.chat_for("S-0142") == 11 and bindings.merchant_for(10) is None
    bindings.bind(11, "S-0907")  # the same phone moves to another merchant
    assert bindings.chat_for("S-0907") == 11 and bindings.chat_for("S-0142") is None
    assert bindings.bound_merchants() == ("S-0907",)


def test_the_deep_link_needs_the_bot_username_and_clear_forgets_everything() -> None:
    bindings = TelegramBindings()
    assert bindings.deep_link("S-0142") is None
    bindings.set_bot_username("ChhatriDemoBot")
    assert bindings.deep_link("S-0142") == "https://t.me/ChhatriDemoBot?start=S-0142"
    bindings.bind(1, "S-0142")
    bindings.clear()
    assert bindings.bound_merchants() == () and bindings.bot_username is None


def test_the_store_defaults_to_whatsapp_and_remembers_a_choice_per_merchant() -> None:
    store = Store(MiniCity())  # type: ignore[arg-type]
    assert store.preferred_channel("S-0142") is PreferredChannel.WHATSAPP
    store.set_preferred_channel("S-0142", PreferredChannel.TELEGRAM)
    assert store.preferred_channel("S-0142") is PreferredChannel.TELEGRAM
    assert store.preferred_channel("S-0907") is PreferredChannel.WHATSAPP  # others are untouched
    store.set_preferred_channel("S-0142", PreferredChannel.WHATSAPP)
    assert store.preferred_channel("S-0142") is PreferredChannel.WHATSAPP


def test_the_store_rejects_an_unknown_merchant() -> None:
    store = Store(MiniCity())  # type: ignore[arg-type]
    with pytest.raises(KeyError):
        store.set_preferred_channel("S-9999", PreferredChannel.TELEGRAM)
    with pytest.raises(KeyError):
        store.preferred_channel("S-9999")
