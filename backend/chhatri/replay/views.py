"""The only place domain objects become SPEC §19.2 JSON (SPEC §24.6).

Every function returns plain JSON-ready dicts: money as integer ``*_paise`` with a ``*_label`` from
``chhatri.money.format_inr``, timestamps ISO-8601 in IST (``+05:30``), dates ``YYYY-MM-DD``. The
implementations are split by area: `view_live` (clock, zones, KPIs, snapshot), `view_panel` (the
§17.2 zone card), `view_records` (records and merchants), `view_meta` (policy, integrations), `view_ops`
(the H8 ops strip), `view_whatif` (the H24 what-if call) and `view_cover` and `view_claims` (the mini-app's cover
card and claim tracker) and `view_receipt` (the decision receipt).
"""

from __future__ import annotations

from chhatri.replay.view_claims import claims_view
from chhatri.replay.view_cover import cover_view
from chhatri.replay.view_live import clock_view, feed_view, kpis_view, snapshot, zone_snapshot
from chhatri.replay.view_meta import integrations_view, policy_view
from chhatri.replay.view_ops import ops_summary
from chhatri.replay.view_panel import zone_panel
from chhatri.replay.view_receipt import receipt_view
from chhatri.replay.view_records import (
    alert_view,
    audit_view,
    case_view,
    decision_view,
    holiday_request_view,
    merchant_detail,
    merchant_summary,
    message_view,
    pause_view,
    payout_view,
    trigger_view,
)
from chhatri.replay.view_whatif import whatif_view

__all__ = [
    "alert_view",
    "audit_view",
    "case_view",
    "claims_view",
    "clock_view",
    "cover_view",
    "decision_view",
    "feed_view",
    "holiday_request_view",
    "integrations_view",
    "kpis_view",
    "merchant_detail",
    "merchant_summary",
    "message_view",
    "ops_summary",
    "pause_view",
    "payout_view",
    "policy_view",
    "receipt_view",
    "snapshot",
    "trigger_view",
    "whatif_view",
    "zone_panel",
    "zone_snapshot",
]
