"""Domain enums (SPEC §3). String values are part of the HTTP contract — do not rename."""

from __future__ import annotations

from enum import StrEnum


class ShopType(StrEnum):
    TEA_STALL = "TEA_STALL"
    STREET_FOOD = "STREET_FOOD"
    FRUIT_VEG = "FRUIT_VEG"
    KIRANA = "KIRANA"
    PHARMACY = "PHARMACY"
    SALON = "SALON"
    MOBILE_RECHARGE = "MOBILE_RECHARGE"


class Language(StrEnum):
    HI = "hi"
    EN = "en"
    MR = "mr"


class AlertKind(StrEnum):
    RAIN = "RAIN"
    HEATWAVE = "HEATWAVE"
    CIVIC = "CIVIC"  # bandh / shutdown


class AlertLevel(StrEnum):
    YELLOW = "YELLOW"
    ORANGE = "ORANGE"
    RED = "RED"


class CoverStatus(StrEnum):
    PENDING_PAYMENT = "PENDING_PAYMENT"
    WAITING = "WAITING"  # bought, inside the waiting period
    ACTIVE = "ACTIVE"
    LAPSED = "LAPSED"
    CANCELLED = "CANCELLED"


class ClaimKind(StrEnum):
    AREA = "AREA"
    PERSONAL = "PERSONAL"


class CheckCode(StrEnum):
    COVER_IN_FORCE = "COVER_IN_FORCE"
    PREMIUM_PREPAID = "PREMIUM_PREPAID"
    COVER_BEFORE_ALERT = "COVER_BEFORE_ALERT"
    ALERT_ACTIVE = "ALERT_ACTIVE"
    INDEX_QUORUM = "INDEX_QUORUM"
    BELOW_FLOOR = "BELOW_FLOOR"
    BELOW_MODEL_RANGE = "BELOW_MODEL_RANGE"
    SILENCE_VERIFIED = "SILENCE_VERIFIED"
    SLIP_READABLE = "SLIP_READABLE"
    NAME_MATCHES_KYC = "NAME_MATCHES_KYC"
    DATES_MATCH = "DATES_MATCH"
    WITHIN_AUTO_LIMIT = "WITHIN_AUTO_LIMIT"
    NOT_ALREADY_PAID = "NOT_ALREADY_PAID"
    WITHIN_ANNUAL_LIMIT = "WITHIN_ANNUAL_LIMIT"


class CheckStatus(StrEnum):
    PASS = "PASS"
    FAIL = "FAIL"
    UNSURE = "UNSURE"
    NOT_APPLICABLE = "NOT_APPLICABLE"
    WAIVED_BY_OFFICER = "WAIVED_BY_OFFICER"


class Severity(StrEnum):
    HARD = "HARD"  # failure ⇒ DECLINED, never overridable
    SOFT = "SOFT"  # failure ⇒ REFERRED to a human


class DecisionOutcome(StrEnum):
    APPROVED = "APPROVED"
    REFERRED = "REFERRED"
    DECLINED = "DECLINED"


class CoverQuoteOutcome(StrEnum):
    OK = "OK"
    BLOCKED = "BLOCKED"


class PayoutStatus(StrEnum):
    PENDING = "PENDING"
    CREDITED = "CREDITED"
    FAILED = "FAILED"


class PremiumMethod(StrEnum):
    SETTLEMENT_DEDUCTION = "SETTLEMENT_DEDUCTION"
    PAYMENT_LINK = "PAYMENT_LINK"


class PremiumStatus(StrEnum):
    PENDING = "PENDING"
    PAID = "PAID"
    FAILED = "FAILED"
    EXPIRED = "EXPIRED"


class CaseKind(StrEnum):
    PERSONAL_CLAIM_REVIEW = "PERSONAL_CLAIM_REVIEW"
    DISPUTE = "DISPUTE"
    AREA_REVIEW = "AREA_REVIEW"


class CaseStatus(StrEnum):
    OPEN = "OPEN"
    APPROVED = "APPROVED"
    DECLINED = "DECLINED"
    CLOSED = "CLOSED"  # dispute answered without a new payout


class Direction(StrEnum):
    INBOUND = "INBOUND"
    OUTBOUND = "OUTBOUND"


class Channel(StrEnum):
    WHATSAPP = "WHATSAPP"
    SIMULATOR = "SIMULATOR"  # console phone view
    SOUNDBOX = "SOUNDBOX"


class MessageKind(StrEnum):
    TEXT = "TEXT"
    VOICE = "VOICE"
    IMAGE = "IMAGE"
    PAYOUT_CARD = "PAYOUT_CARD"
    CASE_CHIP = "CASE_CHIP"
    SOUNDBOX = "SOUNDBOX"
    TEMPLATE = "TEMPLATE"
    BUTTONS = "BUTTONS"


class IntegrationMode(StrEnum):
    LIVE = "LIVE"
    SIMULATED = "SIMULATED"
