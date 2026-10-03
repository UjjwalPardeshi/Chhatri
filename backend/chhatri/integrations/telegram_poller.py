"""Background long polling of Telegram's `getUpdates` (no webhook, no public URL).

`TelegramPoller` runs one asyncio task for the life of the app. Each cycle asks for updates from `offset` (the last seen
`update_id` + 1, kept in memory) and waits up to `poll_timeout_s` seconds for the first one; the updates are parsed into
events and handed, in order, to the handler. The offset moves on before the handler runs, so one bad message can never be
delivered twice; a handler failure is logged (error type only) and the next batch is still polled.

Failures never crash the app: any error from Telegram (no network, 401, 409 from a second poller, 5xx) is logged with its
safe message, the poller sleeps `backoff` (1 s, doubling to 30 s, reset by the next good poll) and tries again. `stop()`
cancels the task and waits for it, so shutdown never leaves a request open. The token is never logged.
"""

from __future__ import annotations

import asyncio
import logging
from collections.abc import Awaitable, Callable, Sequence
from dataclasses import dataclass
from typing import Any, Final, Protocol

from chhatri.integrations.base import IntegrationError
from chhatri.integrations.retry import Sleep
from chhatri.integrations.telegram_updates import TgEvent, parse_updates

logger = logging.getLogger(__name__)

__all__ = ["DEFAULT_POLL_TIMEOUT_S", "Backoff", "TelegramPoller", "UpdatesSource"]

DEFAULT_POLL_TIMEOUT_S: Final = 25  # Telegram long-poll wait; the HTTP timeout is this plus a margin
Handler = Callable[[Sequence[TgEvent]], Awaitable[None]]


class UpdatesSource(Protocol):
    """What the poller needs from the Bot API client (`TelegramBotClient`; tests pass a fake)."""

    async def get_updates(self, *, offset: int | None, timeout_s: int) -> list[dict[str, Any]]: ...

    async def delete_webhook(self) -> None: ...


@dataclass(frozen=True, slots=True)
class Backoff:
    """Wait `base_s` after the first failure in a row, doubling up to `max_s`."""

    base_s: float = 1.0
    max_s: float = 30.0

    def __post_init__(self) -> None:
        if self.base_s <= 0 or self.max_s < self.base_s:
            raise ValueError("backoff needs 0 < base_s <= max_s")

    def delay(self, failures: int) -> float:
        return min(self.max_s, self.base_s * 2 ** max(failures - 1, 0))


class TelegramPoller:
    """One long-polling task; `start()` and `await stop()` bracket the app's life."""

    def __init__(
        self,
        source: UpdatesSource,
        handler: Handler,
        *,
        poll_timeout_s: int = DEFAULT_POLL_TIMEOUT_S,
        backoff: Backoff | None = None,
        sleep: Sleep = asyncio.sleep,
    ) -> None:
        self._source = source
        self._handler = handler
        self._poll_timeout_s = poll_timeout_s
        self._backoff = backoff or Backoff()
        self._sleep = sleep
        self._offset: int | None = None
        self._failures = 0
        self._task: asyncio.Task[None] | None = None

    @property
    def offset(self) -> int | None:
        """The next `offset` to ask for: the last handled `update_id` + 1, None before the first update."""
        return self._offset

    @property
    def failures(self) -> int:
        """Polls that failed in a row (0 after a good one)."""
        return self._failures

    @property
    def running(self) -> bool:
        return self._task is not None and not self._task.done()

    def start(self) -> None:
        """Start polling in the background (a second call while running does nothing)."""
        if not self.running:
            self._task = asyncio.create_task(self._run(), name="telegram-poller")

    async def stop(self) -> None:
        """Cancel the poll loop and wait for it; safe to call twice."""
        task, self._task = self._task, None
        if task is not None and not task.done():
            task.cancel()
            await asyncio.gather(task, return_exceptions=True)

    async def poll_once(self) -> int:
        """One poll cycle: fetch, advance the offset, hand the events over. Returns the number of updates received.

        Raises what the source raises (the loop turns that into a backoff)."""
        updates = await self._source.get_updates(offset=self._offset, timeout_s=self._poll_timeout_s)
        self._failures = 0
        if not updates:
            return 0
        ids = [item["update_id"] for item in updates if isinstance(item.get("update_id"), int)]
        if ids:
            self._offset = max(ids) + 1
        events = parse_updates(updates)
        if events:
            await self._deliver(events)
        return len(updates)

    async def _deliver(self, events: Sequence[TgEvent]) -> None:
        try:
            await self._handler(events)
        except Exception as exc:  # the handler is the app's code: it must never stop the polling
            logger.error(
                "telegram: handling %d update(s) failed: %s", len(events), type(exc).__name__, exc_info=exc
            )

    async def _run(self) -> None:
        await self._clear_webhook()
        while True:
            try:
                await self.poll_once()
            except asyncio.CancelledError:
                raise
            except Exception as exc:  # never crash the app: back off and poll again
                self._failures += 1
                delay = self._backoff.delay(self._failures)
                reason = exc.safe_message if isinstance(exc, IntegrationError) else type(exc).__name__
                logger.warning(
                    "telegram: poll failed (%s); failure %d in a row, retrying in %.1fs",
                    reason,
                    self._failures,
                    delay,
                )
                await self._sleep(delay)

    async def _clear_webhook(self) -> None:
        """A webhook left on the bot would make every `getUpdates` answer 409; clearing it is harmless."""
        try:
            await self._source.delete_webhook()
        except asyncio.CancelledError:
            raise
        except Exception as exc:
            reason = exc.safe_message if isinstance(exc, IntegrationError) else type(exc).__name__
            logger.warning("telegram: could not clear a webhook (%s); polling anyway", reason)
