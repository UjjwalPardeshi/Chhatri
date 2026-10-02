"""Errors that tell the chain what kind of failure a link had (H26 reasons)."""

from __future__ import annotations

from chhatri.integrations.base import IntegrationError


class InvalidReply(IntegrationError):
    """The provider answered, but not with a usable reply: not JSON, the wrong shape, blocked or cut off.

    The chain reports it as INVALID_REPLY and tries the next link. The safe message never holds the reply text.
    """
