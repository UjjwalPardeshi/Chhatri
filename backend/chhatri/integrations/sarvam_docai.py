"""Live Sarvam doc-ai slip reader and the slip parsing rules (SPEC §14.1).

`client.doc_ai.extract(file=[(name, bytes, mime)], schema=json.dumps(schema), language="en-IN",
output_format="json")` → `job_id`; poll `client.doc_ai.get_status(job_id)` until
`completed | partially_completed | failed | rejected`; `client.doc_ai.get_results(job_id)` →
`.result` (dict) and `.annotations` (every leaf has `confidence`).

Confidence = min(annotations["patient_name"].confidence, annotations["admission_date"].confidence),
a missing field or confidence counting as 0; a leaf may be a dict with `confidence` or a list of such
dicts (a list counts as its least confident member). The whole read is bounded by 60 s.
"""

from __future__ import annotations

import asyncio
import json
import logging
import time
from collections.abc import Callable, Mapping
from datetime import date
from types import MappingProxyType
from typing import Any

from chhatri.domain.models import SlipExtraction
from chhatri.integrations.base import IntegrationError
from chhatri.integrations.retry import DOC_AI_TIMEOUT_S, Sleep
from chhatri.integrations.sarvam_client import ClientFactory, SarvamCaller, default_client_factory, field_of

logger = logging.getLogger(__name__)

INTEGRATION = "sarvam_vision"
SOURCE = "sarvam-doc-ai"
DOC_LANGUAGE = "en-IN"
OUTPUT_FORMAT = "json"
POLL_INTERVAL_S = 1.0
MAX_POLLS = 50
DONE_STATUSES = frozenset({"completed", "partially_completed"})
FAILED_STATUSES = frozenset({"failed", "rejected"})
DOCUMENT_TYPES = ("admission_slip", "discharge_summary", "prescription", "bill", "other")
OTHER_DOCUMENT = "other"
CONFIDENCE_FIELDS = ("patient_name", "admission_date")

SLIP_SCHEMA: Mapping[str, Any] = MappingProxyType(
    {
        "type": "object",
        "properties": {
            "patient_name": {"type": "string", "description": "Full name of the patient as printed"},
            "admission_date": {"type": "string", "description": "Date of admission, formatted YYYY-MM-DD"},
            "discharge_date": {
                "type": "string",
                "description": "Date of discharge, formatted YYYY-MM-DD; empty if not discharged",
            },
            "hospital_name": {"type": "string", "description": "Name of the hospital or clinic"},
            "document_type": {
                "type": "string",
                "enum": list(DOCUMENT_TYPES),
                "description": "Kind of medical document",
            },
        },
    }
)


def leaf_confidence(leaf: Any) -> float:
    """Confidence of one annotation leaf; anything unreadable counts as 0 (SPEC §14.1)."""
    if isinstance(leaf, Mapping):
        value = leaf.get("confidence")
        if isinstance(value, bool) or not isinstance(value, int | float):
            return 0.0
        return min(max(float(value), 0.0), 1.0)
    if isinstance(leaf, list | tuple):
        return min((leaf_confidence(item) for item in leaf), default=0.0)
    return 0.0


def slip_confidence(annotations: Mapping[str, Any]) -> float:
    return min(leaf_confidence(annotations.get(name)) for name in CONFIDENCE_FIELDS)


def _text(value: Any) -> str | None:
    if not isinstance(value, str):
        return None
    cleaned = " ".join(value.split())
    return cleaned or None


def _iso_date(value: Any) -> date | None:
    text = _text(value)
    if text is None:
        return None
    try:
        return date.fromisoformat(text)
    except ValueError:
        logger.info("slip date %r is not YYYY-MM-DD; treated as missing", text)
        return None


def _document_type(value: Any) -> str | None:
    text = _text(value)
    if text is None:
        return None
    normalised = text.lower().replace(" ", "_")
    return normalised if normalised in DOCUMENT_TYPES else OTHER_DOCUMENT


def parse_slip(result: Mapping[str, Any], confidence: float, *, source: str) -> SlipExtraction:
    """Build a SlipExtraction from extracted fields (shared by live and simulated readers)."""
    return SlipExtraction(
        patient_name=_text(result.get("patient_name")),
        admission_date=_iso_date(result.get("admission_date")),
        discharge_date=_iso_date(result.get("discharge_date")),
        hospital_name=_text(result.get("hospital_name")),
        document_type=_document_type(result.get("document_type")),
        confidence=min(max(confidence, 0.0), 1.0),
        source=source,
        raw={key: value for key, value in result.items() if isinstance(key, str)},
    )


def parse_results(response: Any) -> SlipExtraction:
    """Parse `get_results` output (SDK model or mapping) into a SlipExtraction."""
    result = field_of(response, "result")
    annotations = field_of(response, "annotations")
    if not isinstance(result, Mapping):
        raise IntegrationError(INTEGRATION, "results had no extracted fields")
    if not isinstance(annotations, Mapping):
        annotations = {}
    return parse_slip(result, slip_confidence(annotations), source=SOURCE)


class LiveSarvamSlipReader:
    """SlipReader backed by Sarvam doc-ai extraction (SPEC §14.1)."""

    def __init__(
        self,
        api_key: str,
        *,
        timeout_s: float = DOC_AI_TIMEOUT_S,
        poll_interval_s: float = POLL_INTERVAL_S,
        max_polls: int = MAX_POLLS,
        caller: SarvamCaller | None = None,
        client_factory: ClientFactory | None = None,
        sleep: Sleep = asyncio.sleep,
        monotonic: Callable[[], float] = time.monotonic,
    ) -> None:
        if not api_key:
            raise ValueError("api_key is required for live Sarvam doc-ai")
        if timeout_s <= 0 or poll_interval_s < 0 or max_polls < 1:
            raise ValueError("invalid doc-ai polling bounds")
        self.timeout_s = timeout_s
        self.poll_interval_s = poll_interval_s
        self.max_polls = max_polls
        self._sleep = sleep
        self._monotonic = monotonic
        self._caller = caller or SarvamCaller(
            INTEGRATION,
            client_factory or default_client_factory(api_key, timeout_s),
            timeout_s=timeout_s,
            sleep=sleep,
        )

    async def read_slip(self, image: bytes, mime_type: str) -> SlipExtraction:
        if not image:
            raise IntegrationError(INTEGRATION, "empty image")
        deadline = self._monotonic() + self.timeout_s
        job_id = await self._start_job(image, mime_type, deadline)
        await self._wait_until_done(job_id, deadline)
        results = await self._caller.call(
            lambda client: client.doc_ai.get_results(job_id, request_options=self._options(deadline)),
            timeout_s=self._remaining(deadline),
        )
        return parse_results(results)

    def _remaining(self, deadline: float) -> float:
        remaining = deadline - self._monotonic()
        if remaining <= 0:
            raise IntegrationError(INTEGRATION, "slip reading timed out")
        return remaining

    def _options(self, deadline: float) -> dict[str, int]:
        return self._caller.request_options(self._remaining(deadline))

    async def _start_job(self, image: bytes, mime_type: str, deadline: float) -> str:
        schema = json.dumps(SLIP_SCHEMA, default=dict)
        extension = mime_type.split("/")[-1].split(";")[0] or "img"
        options = self._options(deadline)

        def run(client: Any) -> Any:
            return client.doc_ai.extract(
                file=[(f"slip.{extension}", image, mime_type)],
                schema=schema,
                language=DOC_LANGUAGE,
                output_format=OUTPUT_FORMAT,
                request_options=options,
            )

        response = await self._caller.call(run, timeout_s=self._remaining(deadline))
        job_id = field_of(response, "job_id")
        if not isinstance(job_id, str) or not job_id:
            raise IntegrationError(INTEGRATION, "extract returned no job id")
        return job_id

    async def _wait_until_done(self, job_id: str, deadline: float) -> None:
        for _ in range(self.max_polls):
            status_response = await self._caller.call(
                lambda client: client.doc_ai.get_status(job_id, request_options=self._options(deadline)),
                timeout_s=self._remaining(deadline),
            )
            status = str(field_of(status_response, "status") or "").lower()
            if status in DONE_STATUSES:
                return
            if status in FAILED_STATUSES:
                raise IntegrationError(INTEGRATION, f"document job {status}")
            await self._sleep(min(self.poll_interval_s, self._remaining(deadline)))
        raise IntegrationError(INTEGRATION, "document job did not finish in time")
