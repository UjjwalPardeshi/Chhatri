"""Errors raised by the data pipeline (SPEC §17.4, §23). The pipeline never falls back silently."""

from __future__ import annotations

__all__ = ["CalibrationError", "PipelineError"]


class PipelineError(RuntimeError):
    """A pipeline step cannot produce its artefact (bad inputs, missing prerequisites)."""


class CalibrationError(PipelineError):
    """The calibration cannot hit a SPEC §17.2 golden number, or did not reach a fixed point."""
