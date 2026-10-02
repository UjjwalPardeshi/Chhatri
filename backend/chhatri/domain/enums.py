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
    PASS = "PASS"  # noqa: S105 - a check status, not a password
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


class HolidayStatus(StrEnum):
    """Where an EDI holiday request stands (X4, fs-03 section 7.5). Only a grant creates a pause."""

    REQUESTED = "REQUESTED"
    GRANTED = "GRANTED"
    REFUSED = "REFUSED"
    NO_RESPONSE = "NO_RESPONSE"


class HolidayReason(StrEnum):
    """Why the lender refused, in the order it checks (fs-03 section 7.2): L4, L1, L2, L3."""

    FLAG_OFF = "FLAG_OFF"
    NOT_ACTIVE = "NOT_ACTIVE"
    IN_ARREARS = "IN_ARREARS"
    NO_ALLOWANCE = "NO_ALLOWANCE"


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
    FALLBACK = "FALLBACK"  # a configured live adapter is forced off (X6); a simulator or template answers


class SourceKind(StrEnum):
    """What a Source points at (H13, fs-09 section 8.3)."""

    RULES = "RULES"
    CLAUSE = "CLAUSE"
    ALERT = "ALERT"
    SALES_INDEX = "SALES_INDEX"
    FORECAST = "FORECAST"
    ZONE_BOUND = "ZONE_BOUND"
    COVER = "COVER"
    PREMIUM = "PREMIUM"
    KYC = "KYC"
    SLIP = "SLIP"
    SALES_DAY = "SALES_DAY"
    PAYOUT_HISTORY = "PAYOUT_HISTORY"
    LENDER = "LENDER"


class SourceOrigin(StrEnum):
    """Where the underlying record comes from; the chip always shows SIMULATED (fs-09 section 8.2)."""

    LIVE = "LIVE"
    SIMULATED = "SIMULATED"
    FALLBACK = "FALLBACK"  # a configured live adapter is forced off (X6); a simulator or template answers
    CONFIG = "CONFIG"


class CounterfactualKind(StrEnum):
    """What a counterfactual says (H14, fs-09 section 9.1)."""

    FLIP_FROM_DECLINED = "FLIP_FROM_DECLINED"
    FLIP_FROM_REFERRED = "FLIP_FROM_REFERRED"
    AMOUNT_SENSITIVITY = "AMOUNT_SENSITIVITY"
    ZONE_NO_TRIGGER = "ZONE_NO_TRIGGER"
    EXPLAIN_ONLY = "EXPLAIN_ONLY"
