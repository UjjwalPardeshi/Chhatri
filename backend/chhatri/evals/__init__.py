"""H25: the offline evaluation harness (docs/04-engineering/ai-evaluation-plan.md).

``python -m chhatri.evals`` (``make evals``) scores the suites that need no network and no key, writes
``backend/artifacts/evals/summary.json``, and ``GET /api/evals/summary`` serves that file and nothing else.
A result exists only when a stored run produced it; a suite that needs a live provider reads NOT_MEASURED.
"""

from __future__ import annotations
