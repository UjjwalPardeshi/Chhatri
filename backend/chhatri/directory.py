"""The independent hospital and doctor directory (SPEC §9.2). Pure lookup, no I/O beyond the load.

Why this module exists at all: a hospital slip is supplied by the person claiming on it. Reading a
doctor's phone number off that slip and ringing it verifies nothing — a forged slip carries a
friend's number. So the slip is only ever used to say *which* hospital and *which* doctor, by
registration number, and the way to reach that doctor comes from here.

A doctor resolves only within the hospital named on the slip, so a real registration number quoted
against the wrong hospital does not identify anybody.
"""

from __future__ import annotations

from functools import lru_cache
from pathlib import Path

import yaml
from pydantic import BaseModel, ConfigDict, Field

from chhatri.domain.models import Doctor, Hospital
from chhatri.policy.names import normalise_name

DIRECTORY_PATH = Path(__file__).with_name("directory.yaml")

__all__ = ["Directory", "DirectoryHospital", "default_directory", "load_directory"]


class _Frozen(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")


class DirectoryHospital(_Frozen):
    """A hospital plus the other names slips write it under."""

    id: str
    name: str
    city: str
    aliases: tuple[str, ...] = ()

    def as_hospital(self) -> Hospital:
        return Hospital(id=self.id, name=self.name, city=self.city)

    @property
    def match_keys(self) -> tuple[str, ...]:
        return tuple(normalise_name(n) for n in (self.name, *self.aliases))


class DirectoryDoctor(_Frozen):
    registration_no: str
    name: str
    hospital_id: str
    verify_chat_id: str | None = None

    def as_doctor(self) -> Doctor:
        return Doctor(
            registration_no=self.registration_no,
            name=self.name,
            hospital_id=self.hospital_id,
            verify_chat_id=self.verify_chat_id,
        )


class Directory(_Frozen):
    version: str
    hospitals: tuple[DirectoryHospital, ...] = Field(default=())
    doctors: tuple[DirectoryDoctor, ...] = Field(default=())

    def find_hospital(self, named: str | None) -> Hospital | None:
        """The hospital a slip names, matched on the registered name or a known alias."""
        if named is None or not named.strip():
            return None
        key = normalise_name(named)
        for row in self.hospitals:
            if key in row.match_keys:
                return row.as_hospital()
        return None

    def find_doctor(self, hospital: Hospital | None, registration_no: str | None) -> Doctor | None:
        """The doctor with this registration number *on that hospital's register*, or None."""
        if hospital is None or registration_no is None or not registration_no.strip():
            return None
        key = registration_no.strip().upper()
        for row in self.doctors:
            if row.registration_no.upper() == key and row.hospital_id == hospital.id:
                return row.as_doctor()
        return None


def load_directory(path: Path | None = None) -> Directory:
    with (path or DIRECTORY_PATH).open(encoding="utf-8") as fh:
        return Directory.model_validate(yaml.safe_load(fh))


@lru_cache(maxsize=1)
def default_directory() -> Directory:
    return load_directory()
