"""Tests for slip rendering and extraction (SPEC §17.2, §24.1)."""

from datetime import date

import pytest

from chhatri.sim.slips import render_slip, read_embedded_slip


def test_render_anil_slip():
    """Test rendering Anil's admission slip (SPEC §17.2)."""
    slip = render_slip(
        patient_name="Anil R. Jadhav",
        admitted=date(2025, 8, 20),
        hospital="KEM Hospital, Parel",
        diagnosis="Viral fever",
        confidence=0.94
    )

    assert isinstance(slip, bytes)
    assert len(slip) > 0
    assert slip.startswith(b"\x89PNG")  # PNG signature


def test_render_mismatch_slip():
    """Test rendering slip with different name (SPEC §17.2)."""
    slip = render_slip(
        patient_name="Sunil Pawar",
        admitted=date(2025, 8, 20),
        hospital="KEM Hospital, Parel",
        diagnosis="Viral fever",
        confidence=0.93
    )

    assert isinstance(slip, bytes)
    assert len(slip) > 0
    assert slip.startswith(b"\x89PNG")


def test_render_blurry_slip():
    """Test rendering blurry slip with low confidence (SPEC §17.2)."""
    slip = render_slip(
        patient_name="Anil R. Jadhav",
        admitted=date(2025, 8, 20),
        hospital="KEM Hospital, Parel",
        diagnosis="Viral fever",
        confidence=0.55
    )

    assert isinstance(slip, bytes)
    assert len(slip) > 0
    assert slip.startswith(b"\x89PNG")


def test_read_embedded_slip_anil():
    """Test reading Anil's slip metadata (SPEC §17.2)."""
    slip = render_slip(
        patient_name="Anil R. Jadhav",
        admitted=date(2025, 8, 20),
        hospital="KEM Hospital, Parel",
        diagnosis="Viral fever",
        confidence=0.94
    )

    metadata = read_embedded_slip(slip)
    assert metadata is not None
    assert metadata["patient_name"] == "Anil R. Jadhav"
    assert metadata["admission_date"] == "2025-08-20"
    assert metadata["hospital_name"] == "KEM Hospital, Parel"
    assert metadata["document_type"] == "admission_slip"
    assert metadata["confidence"] == 0.94


def test_read_embedded_slip_mismatch():
    """Test reading mismatch slip metadata."""
    slip = render_slip(
        patient_name="Sunil Pawar",
        admitted=date(2025, 8, 20),
        hospital="KEM Hospital, Parel",
        diagnosis="Viral fever",
        confidence=0.93
    )

    metadata = read_embedded_slip(slip)
    assert metadata is not None
    assert metadata["patient_name"] == "Sunil Pawar"
    assert metadata["confidence"] == 0.93


def test_read_embedded_slip_blurry():
    """Test reading blurry slip with low confidence."""
    slip = render_slip(
        patient_name="Anil R. Jadhav",
        admitted=date(2025, 8, 20),
        hospital="KEM Hospital, Parel",
        diagnosis="Viral fever",
        confidence=0.55
    )

    metadata = read_embedded_slip(slip)
    assert metadata is not None
    assert metadata["confidence"] == 0.55


def test_read_invalid_slip():
    """Test reading non-slip PNG returns None."""
    # Random bytes that aren't a valid slip
    invalid_png = b"\x89PNG\r\n\x1a\n" + b"x" * 100

    metadata = read_embedded_slip(invalid_png)
    # Should return None because metadata isn't embedded
    # (or raise an exception, depending on implementation)
    assert metadata is None


def test_slip_round_trip():
    """Test that rendering and reading a slip preserves data."""
    original_name = "Anil R. Jadhav"
    original_admitted = date(2025, 8, 20)
    original_hospital = "KEM Hospital, Parel"
    original_diagnosis = "Viral fever"
    original_confidence = 0.94

    slip = render_slip(
        patient_name=original_name,
        admitted=original_admitted,
        hospital=original_hospital,
        diagnosis=original_diagnosis,
        confidence=original_confidence
    )

    metadata = read_embedded_slip(slip)
    assert metadata["patient_name"] == original_name
    assert metadata["admission_date"] == original_admitted.isoformat()
    assert metadata["hospital_name"] == original_hospital
    assert metadata["confidence"] == original_confidence
