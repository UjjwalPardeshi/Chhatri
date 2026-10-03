"""The long-polling loop: offset, timeout, error backoff, handler failures and a clean shutdown."""

from __future__ import annotations

import asyncio
import logging
from collections.abc import Sequence
from typing import Any

import pytest

from chhatri.integrations.base import IntegrationError
from chhatri.integrations.telegram_api import TelegramBotClient
from chhatri.integrations.telegram_poller import Backoff, TelegramPoller
from chhatri.integrations.telegram_updates import TgEvent, TgText
from tests.fake_telegram import TOKEN, FakeBotApi, text_update
from tests.integrations.conftest import SleepRecorder


class ScriptedSource:
    """UpdatesSource that answers from a script: a list of updates, or an exception to raise."""

    def __init__(self, *script: list[dict[str, Any]] | Exception) -> None:
        self.script = list(script)
        self.asked: list[tuple[int | None, int]] = []
        self.webhook_cleared = 0
        self.webhook_error: Exception | None = None
        self.drained = asyncio.Event()

    async def get_updates(self, *, offset: int | None, timeout_s: int) -> list[dict[str, Any]]:
        self.asked.append((offset, timeout_s))
        if not self.script:
            self.drained.set()
            await asyncio.Event().wait()  # an idle long poll: waits until cancelled
        step = self.script.pop(0)
        if isinstance(step, Exception):
            raise step
        return step

    async def delete_webhook(self) -> None:
        self.webhook_cleared += 1
        if self.webhook_error is not None:
            raise self.webhook_error


class Collector:
    def __init__(self, *, fail_on: int | None = None) -> None:
        self.batches: list[list[int]] = []
        self.fail_on = fail_on

    async def __call__(self, events: Sequence[TgEvent]) -> None:
        self.batches.append([e.update_id for e in events])
        if self.fail_on is not None and self.fail_on in self.batches[-1]:
            raise RuntimeError("boom")


async def run_until_idle(poller: TelegramPoller, source: ScriptedSource) -> None:
    poller.start()
    await asyncio.wait_for(source.drained.wait(), 5)


async def test_offset_moves_past_the_last_update_and_the_timeout_is_passed_on() -> None:
    source = ScriptedSource([text_update(10, 1, "a"), text_update(11, 1, "b")], [text_update(12, 1, "c")])
    handler = Collector()
    poller = TelegramPoller(source, handler, poll_timeout_s=17, sleep=SleepRecorder())
    await run_until_idle(poller, source)
    assert source.asked == [(None, 17), (12, 17), (13, 17)]
    assert handler.batches == [[10, 11], [12]] and poller.offset == 13
    await poller.stop()


async def test_the_offset_survives_a_failed_poll() -> None:
    source = ScriptedSource(
        [text_update(3, 1, "a")], IntegrationError("telegram", "provider error (HTTP 502)"), []
    )
    poller = TelegramPoller(source, Collector(), sleep=SleepRecorder())
    await run_until_idle(poller, source)
    assert [offset for offset, _ in source.asked] == [None, 4, 4, 4]
    await poller.stop()


async def test_errors_back_off_exponentially_up_to_the_cap_and_reset_after_a_good_poll() -> None:
    errors = [IntegrationError("telegram", "could not connect")] * 7
    source = ScriptedSource(*errors, [], IntegrationError("telegram", "x"))
    sleeps = SleepRecorder()
    poller = TelegramPoller(source, Collector(), backoff=Backoff(base_s=1.0, max_s=30.0), sleep=sleeps)
    await run_until_idle(poller, source)
    assert sleeps.delays == [1.0, 2.0, 4.0, 8.0, 16.0, 30.0, 30.0, 1.0]  # the good poll reset the streak
    await poller.stop()


async def test_a_failure_is_logged_with_its_safe_message_and_never_the_token(
    caplog: pytest.LogCaptureFixture,
) -> None:
    api = FakeBotApi()
    api.fail("getUpdates", 401)
    client = TelegramBotClient(TOKEN, transport=api.transport(), sleep=SleepRecorder())
    delays: list[float] = []
    parked = asyncio.Event()

    async def sleep(delay: float) -> None:
        delays.append(delay)
        parked.set()
        await asyncio.Event().wait()  # park the poller in its backoff: the in-memory fake never suspends

    poller = TelegramPoller(client, Collector(), backoff=Backoff(0.5, 4.0), sleep=sleep)
    with caplog.at_level(logging.DEBUG):
        poller.start()
        await asyncio.wait_for(parked.wait(), 5)
        await poller.stop()
    assert delays == [0.5] and poller.failures == 1
    assert "authentication failed" in caplog.text and TOKEN not in caplog.text


async def test_an_unexpected_exception_does_not_crash_the_loop() -> None:
    source = ScriptedSource(ValueError("surprise"), [text_update(1, 1, "a")])
    handler = Collector()
    poller = TelegramPoller(source, handler, sleep=SleepRecorder())
    await run_until_idle(poller, source)
    assert handler.batches == [[1]] and poller.running
    await poller.stop()


async def test_a_handler_failure_is_logged_and_the_batch_is_not_delivered_twice(
    caplog: pytest.LogCaptureFixture,
) -> None:
    source = ScriptedSource([text_update(1, 1, "a")], [text_update(2, 1, "b")])
    handler = Collector(fail_on=1)
    poller = TelegramPoller(source, handler, sleep=SleepRecorder())
    with caplog.at_level(logging.ERROR):
        await run_until_idle(poller, source)
    assert handler.batches == [[1], [2]] and "RuntimeError" in caplog.text
    assert source.asked[1][0] == 2  # moved on despite the failure: no poison loop
    await poller.stop()


async def test_updates_nobody_handles_still_move_the_offset() -> None:
    sticker = {
        "update_id": 5,
        "message": {"chat": {"id": 1, "type": "private"}, "date": 1_760_000_000, "sticker": {}},
    }
    group = {
        "update_id": 6,
        "message": {"chat": {"id": -1, "type": "group"}, "date": 1_760_000_000, "text": "x"},
    }
    source = ScriptedSource([group, {"update_id": 7, "weird": True}], [])
    poller = TelegramPoller(source, Collector(), sleep=SleepRecorder())
    await run_until_idle(poller, source)
    assert poller.offset == 8
    del sticker
    await poller.stop()


async def test_a_webhook_is_cleared_first_and_a_failure_there_is_only_a_warning() -> None:
    source = ScriptedSource([])
    source.webhook_error = IntegrationError("telegram", "provider error (HTTP 500)")
    poller = TelegramPoller(source, Collector(), sleep=SleepRecorder())
    await run_until_idle(poller, source)
    assert source.webhook_cleared == 1 and source.asked  # polling went ahead
    await poller.stop()


async def test_stop_cancels_an_idle_long_poll_and_is_safe_twice() -> None:
    source = ScriptedSource()
    poller = TelegramPoller(source, Collector(), sleep=SleepRecorder())
    await run_until_idle(poller, source)
    assert poller.running
    await asyncio.wait_for(poller.stop(), 2)
    assert not poller.running
    await poller.stop()  # nothing to stop: no error


async def test_start_twice_runs_one_task_and_the_poller_can_start_again_after_stop() -> None:
    source = ScriptedSource()
    poller = TelegramPoller(source, Collector(), sleep=SleepRecorder())
    poller.start()
    first = poller._task
    poller.start()
    assert poller._task is first
    await poller.stop()
    poller.start()
    assert poller.running and poller._task is not first
    await poller.stop()


async def test_end_to_end_with_the_real_client_and_the_fake_bot_api() -> None:
    api = FakeBotApi()
    api.queue(text_update(40, 9, "hello"))
    client = TelegramBotClient(TOKEN, transport=api.transport(), sleep=SleepRecorder())
    seen: list[TgEvent] = []
    done = asyncio.Event()

    async def handler(events: Sequence[TgEvent]) -> None:
        seen.extend(events)
        done.set()
        await asyncio.sleep(
            0
        )  # the in-memory fake never suspends: hand the loop back so the test can stop us

    poller = TelegramPoller(client, handler, poll_timeout_s=0, sleep=SleepRecorder())
    poller.start()
    await asyncio.wait_for(done.wait(), 5)
    await poller.stop()
    assert isinstance(seen[0], TgText) and seen[0].text == "hello"
    assert api.sent("deleteWebhook") and poller.offset == 41


def test_backoff_validates_and_caps() -> None:
    assert [Backoff(1, 4).delay(n) for n in (1, 2, 3, 4)] == [1, 2, 4, 4]
    with pytest.raises(ValueError, match="backoff"):
        Backoff(0, 1)
    with pytest.raises(ValueError, match="backoff"):
        Backoff(5, 1)


def test_the_text_event_type_is_exported_for_handlers() -> None:
    assert issubclass(TgText, TgEvent)
