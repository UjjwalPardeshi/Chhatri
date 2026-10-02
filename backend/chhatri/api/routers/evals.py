"""Results of the evaluation suites (H25; data-model-and-api section 5.10, ai-evaluation-plan section 7.2).

Behind the flag ``h25_evals``: while it is off the route answers the ordinary 404 ``not_found``. Read-only: it reads
``backend/artifacts/evals/summary.json`` and nothing else, calls no provider, needs no scenario, and has no rate
group. With no stored run the answer is 200 with every suite NOT_MEASURED, because that is a state the page shows.
"""

from __future__ import annotations

from typing import Any

from fastapi import APIRouter, Depends

from chhatri.api.deps import require_feature
from chhatri.api.envelope import ok
from chhatri.evals import summary as evals_summary

router = APIRouter(prefix="/api/evals", tags=["evals"], dependencies=[Depends(require_feature("h25_evals"))])


@router.get("/summary")
async def get_evals_summary() -> dict[str, Any]:
    """The stored run, or the no-run answer. A file that fails the schema reads as no run (``result file unreadable``)."""
    return ok(evals_summary.load_summary(evals_summary.SUMMARY_PATH))
