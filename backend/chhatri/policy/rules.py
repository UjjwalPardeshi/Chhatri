"""Policy rules (SPEC §9.1). Loaded once from rules.yaml into a frozen model; shared by detect + policy."""

from __future__ import annotations

from functools import lru_cache
from pathlib import Path

import yaml
from pydantic import BaseModel, ConfigDict, Field

from chhatri.money import rupees

RULES_PATH = Path(__file__).with_name("rules.yaml")


class _Frozen(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")


class AreaRules(_Frozen):
    index_floor_pct: int = Field(ge=1, le=100)
    consecutive_hours: int = Field(ge=1, le=12)
    min_shops_in_index: int = Field(ge=1)
    daily_cap_rupees: int = Field(gt=0)

    @property
    def daily_cap_paise(self) -> int:
        return rupees(self.daily_cap_rupees)


class PersonalRules(_Frozen):
    daily_cap_rupees: int = Field(gt=0)
    max_auto_days: int = Field(ge=1)
    name_match_min_score: int = Field(ge=0, le=100)
    slip_confidence_min: float = Field(ge=0.0, le=1.0)
    require_doctor_confirmation: bool = False
    doctor_reply_delay_minutes: int = Field(default=2, ge=0)
    doctor_reply_sla_hours: int = Field(default=24, gt=0)

    @property
    def daily_cap_paise(self) -> int:
        return rupees(self.daily_cap_rupees)


class CoverRules(_Frozen):
    waiting_period_days: int = Field(ge=0)
    alert_lookahead_hours: int = Field(ge=0)


class PremiumRules(_Frozen):
    loading: float = Field(ge=0.0, lt=1.0)
    min_per_day_rupees: int = Field(gt=0)
    first_payment_days: int = Field(gt=0)


class PolicyRules(_Frozen):
    version: str
    payout_share: float = Field(gt=0.0, le=1.0)
    area: AreaRules
    personal: PersonalRules
    cover: CoverRules
    annual_limit_rupees: int = Field(gt=0)
    dispute_sla_hours: int = Field(gt=0)
    payout_rail_delay_minutes: int = Field(ge=0)
    instalment_pause_delay_minutes: int = Field(ge=0)
    premium: PremiumRules

    @property
    def annual_limit_paise(self) -> int:
        return rupees(self.annual_limit_rupees)

    @property
    def share_pct(self) -> int:
        return round(self.payout_share * 100)


def load_rules(path: Path | None = None) -> PolicyRules:
    with (path or RULES_PATH).open(encoding="utf-8") as fh:
        raw = yaml.safe_load(fh)
    return PolicyRules.model_validate(raw)


@lru_cache(maxsize=1)
def default_rules() -> PolicyRules:
    return load_rules()
