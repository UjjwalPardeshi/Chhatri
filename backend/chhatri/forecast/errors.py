"""Errors raised by the expected-sales model (SPEC §7).

The model never degrades silently: training on too little data, predicting without the history the
features need, or loading an incomplete artefact directory raises one of these, with a message that
says exactly what is missing.
"""

from __future__ import annotations


class ForecastError(Exception):
    """Base class for expected-sales model errors."""


class InsufficientDataError(ForecastError, ValueError):
    """Training data does not cover the window or leaves too few usable rows (SPEC §7.2)."""


class InsufficientHistoryError(ForecastError, ValueError):
    """A merchant has no normal day before the prediction date, so `shop_level` is undefined (SPEC §7.1)."""


class ModelArtifactError(ForecastError):
    """A saved model directory is missing files or holds inconsistent metadata (SPEC §7.4)."""
