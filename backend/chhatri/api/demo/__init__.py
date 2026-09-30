"""Demo rehearsal over the HTTP API (SPEC §13.6, §17.2, §22; ``scripts/demo_check.py``).

`flows` drives the deck's four scenarios and three live tests through the §19 routes, `golden` says
what they must show, `report` runs them and prints the pass/fail table.
"""

from chhatri.api.demo.client import DemoApi, DemoHttpError
from chhatri.api.demo.flows import FLOWS
from chhatri.api.demo.golden import GOLDEN, DemoNumbers, expectations
from chhatri.api.demo.report import CheckRow, ScenarioRun, all_passed, compare, rehearse, render_json, render_table

__all__ = [
    "FLOWS",
    "GOLDEN",
    "CheckRow",
    "DemoApi",
    "DemoHttpError",
    "DemoNumbers",
    "ScenarioRun",
    "all_passed",
    "compare",
    "expectations",
    "rehearse",
    "render_json",
    "render_table",
]
