"""Sarvam integration facade (SPEC §14.1) — keeps the historical import path stable.

Implementation lives in `sarvam_client` (SDK plumbing), `sarvam_speech` (Saaras STT, Bulbul TTS),
`sarvam_chat` (JSON-schema chat), `sarvam_docai` (doc-ai slip reader) and `sarvam_sim` (offline
simulators).
"""

from __future__ import annotations

from chhatri.integrations.sarvam_chat import LiveSarvamChat
from chhatri.integrations.sarvam_client import SarvamCaller
from chhatri.integrations.sarvam_docai import SLIP_SCHEMA, LiveSarvamSlipReader, parse_results, parse_slip
from chhatri.integrations.sarvam_sim import SimulatedChat, SimulatedSlipReader, SimulatedSTT, SimulatedTTS
from chhatri.integrations.sarvam_speech import LiveSarvamSTT, LiveSarvamTTS

__all__ = [
    "SLIP_SCHEMA",
    "LiveSarvamChat",
    "LiveSarvamSTT",
    "LiveSarvamSlipReader",
    "LiveSarvamTTS",
    "SarvamCaller",
    "SimulatedChat",
    "SimulatedSTT",
    "SimulatedSlipReader",
    "SimulatedTTS",
    "parse_results",
    "parse_slip",
]
