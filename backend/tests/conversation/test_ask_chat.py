"""5.12: with `n2_ask_chhatri` on, UNKNOWN chat text goes through the Ask service; known intents are untouched (N2.9, N2.15)."""

from __future__ import annotations

from types import SimpleNamespace
from typing import Any

from chhatri.ask.chat import ChatAsk, unknown_answerer
from chhatri.config import Settings
from chhatri.policy.rules import default_rules
from tests.api.fakes import FakeCity
from tests.ask.fakes import GOOD_REPLY, Rig, ScriptedChat, make_rig
from tests.conversation.conftest import ANIL, World, make_world


class IntentChat:
    """A chat model that always picks one intent (what a prompt-injected model might do)."""

    def __init__(self, intent: str) -> None:
        self.intent = intent

    async def complete_json(
        self, system: str, user: str, schema: dict[str, Any], *, schema_name: str
    ) -> dict[str, Any]:
        return {"intent": self.intent}


def with_ask(world: World, rig: Rig) -> None:
    runtime = SimpleNamespace(
        store=rig.store,
        orchestrator=rig.claims,
        audit=world.audit,
        ids=world.ids,
        clock=world.clock,
        integrations=SimpleNamespace(chat_chain=rig.service._chain),
        static=SimpleNamespace(city=FakeCity(), rules=default_rules()),
    )
    world.service._unknown = lambda: ChatAsk(runtime, Settings(_env_file=None))  # type: ignore[call-arg]


async def test_with_the_flag_off_unknown_text_gets_the_built_help() -> None:
    world = make_world()
    messages = await world.service.handle_text(ANIL.id, "What is the yearly limit?")
    assert messages[-1].text_en is not None and messages[-1].text_en.startswith("I'm Chhatri.")
    assert "mode" not in messages[-1].meta


async def test_with_the_flag_on_unknown_text_is_answered_by_the_ask_service() -> None:
    world, rig = make_world(), make_rig(ScriptedChat(GOOD_REPLY))
    with_ask(world, rig)
    messages = await world.service.handle_text(ANIL.id, "What is the yearly limit?")
    reply = messages[-1]
    assert (
        len(messages) == 2
        and reply.text_en == GOOD_REPLY["answer_en"]
        and reply.text_hi == GOOD_REPLY["answer_hi"]
    )
    assert (
        reply.meta["provider"] == "gemini"
        and reply.meta["mode"] == "LIVE"
        and reply.meta["model"] == "test-gemini"
    )
    assert reply.meta["clauses"] == ["C4.3"] and reply.meta["next_action"] == "SEE_CLAIM"
    assert reply.meta["scam_warning"] is False and reply.meta["fallback_reason"] is None
    assert "ask.answered" in world.actions()


async def test_known_intents_behave_as_before_with_the_flag_on() -> None:
    world, rig = make_world(), make_rig(ScriptedChat(GOOD_REPLY))
    with_ask(world, rig)
    messages = await world.service.handle_text(ANIL.id, "मेरा नुकसान ज़्यादा हुआ")
    assert "ask.answered" not in world.actions() and "mode" not in messages[-1].meta
    assert rig.gemini is not None and rig.gemini.calls == []


async def test_with_the_flag_on_a_question_about_a_rule_is_grounded_not_a_payment_link() -> None:
    """N2.7 (AC-ASK-03): "Can I buy cover during an alert?" makes no quote and no link with N2 on."""
    world, rig = make_world(), make_rig(ScriptedChat(GOOD_REPLY))
    with_ask(world, rig)
    messages = await world.service.handle_text(ANIL.id, "Can I buy cover during an alert?")
    assert messages[-1].text_en == GOOD_REPLY["answer_en"] and messages[-1].meta["provider"] == "gemini"
    assert "ask.answered" in world.actions() and "cover.quoted" not in world.actions()


async def test_with_the_flag_off_the_same_question_keeps_the_built_reply() -> None:
    world = make_world()
    await world.service.handle_text(ANIL.id, "Will hospital bills be covered?")
    assert "ask.answered" not in world.actions()


async def test_with_the_flag_on_a_model_never_chooses_the_intent() -> None:
    world, rig = make_world(chat=IntentChat("BUY_COVER")), make_rig(ScriptedChat(GOOD_REPLY))
    with_ask(world, rig)
    await world.service.handle_text(ANIL.id, "What is the yearly limit?")
    entry = next(e for e in world.audit.entries(limit=5000) if e.action == "intent.detected")
    assert entry.data["source"] == "rules" and entry.data["intent"] == "UNKNOWN"
    assert rig.claims.quotes == 0


async def test_with_the_flag_off_a_model_chosen_write_intent_runs_no_handler() -> None:
    world = make_world(chat=IntentChat("BUY_COVER"))
    messages = await world.service.handle_text(ANIL.id, "xyzzy plugh")
    assert messages[-1].text_en is not None and messages[-1].text_en.startswith("I'm Chhatri.")


async def test_a_model_chosen_read_intent_still_runs() -> None:
    world = make_world(chat=IntentChat("COVER_STATUS"))
    messages = await world.service.handle_text(ANIL.id, "xyzzy plugh")
    assert messages[-1].text_en is not None and "cover" in messages[-1].text_en.lower()


async def test_a_question_over_500_characters_gets_ask_too_long() -> None:
    world, rig = make_world(), make_rig(ScriptedChat(GOOD_REPLY))
    with_ask(world, rig)
    messages = await world.service.handle_text(ANIL.id, "w" * 600)
    assert (
        messages[-1].text_en == "Please keep the question shorter."
        and rig.gemini is not None
        and rig.gemini.calls == []
    )


def test_the_resolver_is_off_while_the_flag_is_off_and_on_when_it_is_on() -> None:
    rt = SimpleNamespace()
    assert unknown_answerer(rt, Settings(_env_file=None, chhatri_features="")) is None  # type: ignore[call-arg]
    assert isinstance(
        unknown_answerer(rt, Settings(_env_file=None, chhatri_features="n2_ask_chhatri")), ChatAsk
    )  # type: ignore[call-arg]
