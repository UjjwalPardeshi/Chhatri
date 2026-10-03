"""Live Sarvam doc-ai slip reader with a fake SDK (SPEC §14.1: extract → poll → results, confidence rule)."""

from __future__ import annotations

import json
from datetime import date
from types import SimpleNamespace

import pytest

from chhatri.domain.models import SlipExtraction
from chhatri.integrations.base import IntegrationError
from chhatri.integrations.sarvam_client import SarvamCaller
from chhatri.integrations.sarvam_docai import (
    SLIP_SCHEMA,
    LiveSarvamSlipReader,
    leaf_confidence,
    parse_results,
    parse_slip,
    slip_confidence,
)

from .conftest import SleepRecorder
from .fake_sarvam import ScriptedCall, api_error, fake_client

RESULT = {
    "patient_name": "Anil R. Jadhav",
    "admission_date": "2025-08-20",
    "discharge_date": "",
    "hospital_name": "KEM Hospital,  Parel",
    "document_type": "Admission Slip",
}
ANNOTATIONS = {
    "patient_name": {"confidence": 0.95, "sources": []},
    "admission_date": [{"confidence": 0.91}, {"confidence": 0.97}],
    "hospital_name": {"confidence": 0.99},
}


class FakeClock:
    def __init__(self) -> None:
        self.now = 0.0

    def __call__(self) -> float:
        return self.now


def reader_with(
    statuses: list[object], results: object, *, clock: FakeClock | None = None, max_polls: int = 5
):  # type: ignore[no-untyped-def]
    extract = ScriptedCall([SimpleNamespace(job_id="job-1", status="Accepted", run_id="r")])
    get_status = ScriptedCall(statuses)
    get_results = ScriptedCall([results])
    client = fake_client(doc_ai={"extract": extract, "get_status": get_status, "get_results": get_results})
    sleeps = SleepRecorder()
    monotonic = clock or FakeClock()

    async def sleep(delay: float) -> None:
        sleeps.delays.append(delay)
        monotonic.now += delay

    reader = LiveSarvamSlipReader(
        "key",
        caller=SarvamCaller("sarvam_vision", lambda: client, timeout_s=60, sleep=sleep),
        sleep=sleep,
        monotonic=monotonic,
        max_polls=max_polls,
    )
    return reader, extract, get_status, get_results, sleeps


def status(value: str) -> SimpleNamespace:
    return SimpleNamespace(job_id="job-1", status=value)


async def test_slip_read_end_to_end_with_exact_calls() -> None:
    results = SimpleNamespace(result=RESULT, annotations=ANNOTATIONS)
    reader, extract, get_status, get_results, sleeps = reader_with(
        [status("Pending"), status("Running"), status("completed")], results
    )
    slip = await reader.read_slip(b"\x89PNG...", "image/png")
    assert slip.patient_name == "Anil R. Jadhav"
    assert slip.admission_date == date(2025, 8, 20) and slip.discharge_date is None
    assert slip.hospital_name == "KEM Hospital, Parel" and slip.document_type == "admission_slip"
    assert slip.confidence == pytest.approx(0.91) and slip.source == "sarvam-doc-ai"
    kwargs = extract.calls[0][1]
    assert kwargs["file"] == [("slip.png", b"\x89PNG...", "image/png")]
    assert kwargs["language"] == "en-IN" and kwargs["output_format"] == "json"
    assert json.loads(kwargs["schema"]) == dict(SLIP_SCHEMA)
    assert [c[0] for c in get_status.calls] == [("job-1",)] * 3
    assert get_results.calls[0][0] == ("job-1",)
    assert sleeps.delays == [1.0, 1.0]


def test_slip_schema_meets_doc_ai_rules() -> None:
    assert SLIP_SCHEMA["type"] == "object"
    for name, spec in SLIP_SCHEMA["properties"].items():
        assert spec["type"] == "string" and spec["description"], name
    assert SLIP_SCHEMA["properties"]["document_type"]["enum"] == [
        "admission_slip",
        "discharge_summary",
        "prescription",
        "bill",
        "other",
    ]


async def test_partially_completed_is_accepted() -> None:
    reader, *_ = reader_with([status("partially_completed")], {"result": RESULT, "annotations": {}})
    slip = await reader.read_slip(b"img", "image/jpeg")
    assert slip.confidence == 0.0 and slip.patient_name == "Anil R. Jadhav"


@pytest.mark.parametrize("terminal", ["failed", "rejected"])
async def test_failed_jobs_raise(terminal: str) -> None:
    reader, *_ = reader_with([status(terminal)], {})
    with pytest.raises(IntegrationError, match=f"document job {terminal}"):
        await reader.read_slip(b"img", "image/jpeg")


async def test_polling_is_bounded_by_count() -> None:
    reader, _, get_status, *_ = reader_with([status("Running")], {}, max_polls=3)
    with pytest.raises(IntegrationError, match="did not finish"):
        await reader.read_slip(b"img", "image/jpeg")
    assert len(get_status.calls) == 3


async def test_polling_is_bounded_by_60_second_deadline() -> None:
    clock = FakeClock()
    reader, _, get_status, *_ = reader_with([status("Running")], {}, clock=clock, max_polls=1000)
    with pytest.raises(IntegrationError, match="timed out"):
        await reader.read_slip(b"img", "image/jpeg")
    assert clock.now == pytest.approx(60.0)
    assert len(get_status.calls) <= 61


async def test_missing_job_id_and_bad_results_raise() -> None:
    client = fake_client(doc_ai={"extract": ScriptedCall([{"job_id": ""}])})
    reader = LiveSarvamSlipReader("key", caller=SarvamCaller("v", lambda: client))
    with pytest.raises(IntegrationError, match="no job id"):
        await reader.read_slip(b"img", "image/png")
    with pytest.raises(IntegrationError, match="empty image"):
        await reader.read_slip(b"", "image/png")
    with pytest.raises(IntegrationError, match="no extracted fields"):
        parse_results({"result": None})


async def test_extract_errors_map_safely() -> None:
    client = fake_client(doc_ai={"extract": ScriptedCall([api_error(403)])})
    reader = LiveSarvamSlipReader("key", caller=SarvamCaller("sarvam_vision", lambda: client))
    with pytest.raises(IntegrationError, match="authentication failed"):
        await reader.read_slip(b"img", "image/png")


def test_constructor_bounds() -> None:
    with pytest.raises(ValueError):
        LiveSarvamSlipReader("key", timeout_s=0)
    with pytest.raises(ValueError):
        LiveSarvamSlipReader("key", max_polls=0)


@pytest.mark.parametrize(
    ("leaf", "expected"),
    [
        ({"confidence": 0.8}, 0.8),
        ({"confidence": 1.7}, 1.0),
        ({"confidence": True}, 0.0),
        ({"confidence": "high"}, 0.0),
        ([{"confidence": 0.9}, {"confidence": 0.6}], 0.6),
        ([], 0.0),
        ([{"x": 1}], 0.0),
        (None, 0.0),
        ("0.9", 0.0),
    ],
)
def test_leaf_confidence_is_defensive(leaf: object, expected: float) -> None:
    assert leaf_confidence(leaf) == expected


def test_confidence_is_min_of_name_and_admission_date() -> None:
    assert (
        slip_confidence({"patient_name": {"confidence": 0.7}, "admission_date": {"confidence": 0.9}}) == 0.7
    )
    assert slip_confidence({"patient_name": {"confidence": 0.7}}) == 0.0


def test_parse_slip_normalises_fields() -> None:
    slip = parse_slip(
        {"patient_name": "  ", "admission_date": "20/08/2025", "document_type": "X-ray", 3: "ignored"},
        0.5,
        source="t",
    )
    assert slip.patient_name is None and slip.admission_date is None
    assert slip.document_type == "other" and 3 not in slip.raw
    assert parse_slip({"document_type": None}, 2.0, source="t").confidence == 1.0


def test_non_mapping_annotations_count_as_zero_confidence() -> None:
    assert parse_results({"result": RESULT, "annotations": ["x"]}).confidence == 0.0


def test_parse_slip_reads_the_treating_doctor() -> None:
    slip = parse_slip(
        RESULT | {"doctor_name": "  Dr  S. Rao ", "doctor_registration_no": "MMC-2011-45817"}, 0.9, source="t"
    )
    assert (slip.doctor_name, slip.doctor_registration_no) == ("Dr S. Rao", "MMC-2011-45817")
    bare = parse_slip(RESULT, 0.9, source="t")
    assert bare.doctor_name is None and bare.doctor_registration_no is None


@pytest.mark.parametrize(
    ("printed", "expected"),
    [
        ("Reg. No: MMC-2011-45817", "MMC-2011-45817"),
        ("reg no MMC-2011-45817", "MMC-2011-45817"),
        ("Registration Number - MMC 2011  45817", "MMC 2011 45817"),
        ("Reg.No.:mmc-2011-45817", "mmc-2011-45817"),  # case is kept as printed
        ("  MMC-2011-45817 ", "MMC-2011-45817"),
        ("Reg. No:", None),  # only a label
        ("MMC-ABCD", None),  # no digit
        ("M" * 30 + "-123", None),  # over 32 characters
        ("+91 98200 12345", None),  # a phone number is never a registration number
        ("9820012345", None),
        ("022-2410-7000", None),
        (12345, None),
        (None, None),
    ],
)
def test_registration_number_rules(printed: object, expected: str | None) -> None:
    slip = parse_slip({"doctor_registration_no": printed}, 0.5, source="t")
    assert slip.doctor_registration_no == expected


def test_slip_extraction_has_no_contact_field() -> None:
    """The contact used to reach a doctor comes from the directory, never from a slip a claimant supplied."""
    fields = set(SlipExtraction.model_fields)
    assert {"doctor_name", "doctor_registration_no"} <= fields
    assert not {
        f for f in fields if any(word in f for word in ("phone", "chat", "contact", "email", "mobile"))
    }
    assert set(parse_slip(RESULT, 0.5, source="t").model_dump()) == fields


def test_slip_schema_asks_for_the_doctor_and_never_a_contact() -> None:
    properties = SLIP_SCHEMA["properties"]
    assert {"doctor_name", "doctor_registration_no"} <= set(properties)
    assert "phone number" in properties["doctor_registration_no"]["description"].lower()
    assert not [k for k in properties if any(w in k for w in ("phone", "chat", "contact", "email", "mobile"))]
