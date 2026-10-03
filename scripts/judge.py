#!/usr/bin/env python3
"""One command for a judge: is this build sound? (`make judge`).

Runs six checks in order and prints each line as soon as its check ends: `PASS`, `FAIL` or `INFO`, what was
checked and a short detail.

1. environment: backend/.venv has its python, frontend/node_modules exists, and this Python is at least the
   lower bound of backend/pyproject.toml's `requires-python`.
2. keys: SARVAM_API_KEY, GOOGLE_API_KEY and TELEGRAM_BOT_TOKEN as SET or NOT SET, read the way
   `scripts/check_keys.py` reads them (the environment wins over the repo's .env) but offline: no provider is
   called and no value is printed. NOT SET is INFO, never a failure: without keys the demo runs on its
   simulators and labels them SIMULATED.
3. artefacts: premiums.json, backtest/report.json, calibration.json and every file that
   backend/artifacts/MANIFEST.json lists are present, each listed file has the sha256 the manifest records,
   every JSON artefact parses and model/ loads with the backend's own loader. A file on disk that the manifest
   does not list is INFO.
4. demo check: the in-process path of backend/scripts/demo_check.py (no --url): every scenario through the
   HTTP API on the committed artefacts, every golden number compared (SPEC §13.6, §17.2, §22).
5. audit chain: the monsoon scenario replayed to 17:10, after its 17:04 payouts, then GET /api/audit/verify
   must call the hash chain valid (SPEC §11).
6. frontend: `npm run -s typecheck` in frontend/ (no build, no test suite).

The two in-process apps (4, 5) run with every live integration and AI provider off, the demo flags only
(`DEMO_FEATURES`, whatever the shell exports) and a var dir of their own in a temporary directory, so nothing
outside this process is called and a backend serving the console at the same time is never touched.

    backend/.venv/bin/python scripts/judge.py [--env-file PATH]

Exit status 0, with `CHHATRI JUDGE READY ✓` as the last line, when no check failed; 1, with the list of what
failed, otherwise. The top of the module is stdlib only and uses nothing newer than Python 3.10 (the backend
is imported inside the checks that need it), so a missing venv or an old python3 shows up as FAIL lines, not
as a traceback.
"""

from __future__ import annotations

import argparse
import asyncio
import functools
import json
import logging
import os
import re
import secrets
import shutil
import subprocess  # noqa: S404 - npm with a fixed argument list, no shell
import sys
import tempfile
from collections.abc import Callable, Coroutine, Mapping, Sequence
from dataclasses import dataclass
from pathlib import Path
from typing import TYPE_CHECKING, Any, Final, Literal

import check_keys

if TYPE_CHECKING:
    from chhatri.api.demo import CheckRow
    from chhatri.config import Settings

REPO_ROOT: Final = Path(__file__).resolve().parent.parent
BACKEND_DIR: Final = REPO_ROOT / "backend"
FRONTEND_DIR: Final = REPO_ROOT / "frontend"
VENV_PYTHON: Final = BACKEND_DIR / ".venv" / "bin" / "python"
NODE_MODULES: Final = FRONTEND_DIR / "node_modules"
PYPROJECT: Final = BACKEND_DIR / "pyproject.toml"
ARTIFACTS_DIR: Final = BACKEND_DIR / "artifacts"
MANIFEST: Final = "MANIFEST.json"
MODEL_DIR: Final = "model"
REQUIRED_ARTEFACTS: Final = ("premiums.json", "backtest/report.json", "calibration.json")

ENVIRONMENT: Final = "environment"
KEYS: Final = "keys"
ARTEFACTS: Final = "artefacts"
DEMO: Final = "demo check"
AUDIT: Final = "audit chain"
FRONTEND: Final = "frontend"
WHAT_WIDTH: Final = max(len(name) for name in (ENVIRONMENT, KEYS, ARTEFACTS, DEMO, AUDIT, FRONTEND))

READY: Final = "CHHATRI JUDGE READY ✓"
NOT_READY: Final = "CHHATRI JUDGE NOT READY"
EXIT_READY: Final = 0
EXIT_NOT_READY: Final = 1
SETUP_HINT: Final = "run make setup"
SIMULATED_HINT: Final = "the demo runs simulated without it"
REQUIRES_PYTHON: Final = re.compile(r"""^requires-python\s*=\s*["']([^"']+)["']""", re.MULTILINE)
LOWER_BOUND: Final = re.compile(r">=\s*(\d+(?:\.\d+)*)")

REQUEST_TIMEOUT_S: Final = 120.0  # per request, as backend/scripts/demo_check.py
VAR_DIR_PREFIX: Final = "chhatri-judge-"
OFFICER_TOKEN_BYTES: Final = 24
FAILURES_SHOWN: Final = 3
AUDIT_SCENARIO: Final = "monsoon"
AFTER_PAYOUT: Final = "17:10"  # the monsoon payouts are credited at 17:04 (SPEC §17.2, B1)
TYPECHECK: Final = ("run", "-s", "typecheck")
TYPECHECK_TIMEOUT_S: Final = 300.0

Status = Literal["PASS", "FAIL", "INFO"]
Runner = Callable[..., "subprocess.CompletedProcess[str]"]
"""`subprocess.run`, or a fake in the tests."""

logger = logging.getLogger("judge")


@dataclass(frozen=True, slots=True)
class Line:
    """One report line: a status, what was checked and a short detail (never a key or any other secret)."""

    status: Status
    what: str
    detail: str

    def render(self) -> str:
        return f"{self.status}  {self.what:<{WHAT_WIDTH}}  {self.detail}"


Check = Callable[[], Sequence[Line]]


def emit(text: str) -> None:
    """Print and flush, so each line shows as soon as its check ends, even when the output is piped."""
    print(text, flush=True)


def display(path: Path) -> str:
    """`path` relative to the repo when it is inside it (shorter lines), else as given."""
    try:
        return path.relative_to(REPO_ROOT).as_posix()
    except ValueError:
        return str(path)


# ------------------------------------------------------------------ 1. environment


def requires_python(pyproject: Path) -> tuple[str, tuple[int, ...]]:
    """`requires-python` and its lower bound (`">=3.12,<3.13"` -> (3, 12)); ValueError when there is none.

    A regular expression rather than tomllib, which an older python3 does not have."""
    spec = REQUIRES_PYTHON.search(pyproject.read_text(encoding="utf-8"))
    bound = LOWER_BOUND.search(spec.group(1)) if spec else None
    if spec is None or bound is None:
        raise ValueError(f"{display(pyproject)} has no requires-python lower bound")
    return spec.group(1), tuple(int(part) for part in bound.group(1).split("."))


def _present(path: Path, ok: bool) -> Line:
    if ok:
        return Line("PASS", ENVIRONMENT, f"{display(path)} present")
    return Line("FAIL", ENVIRONMENT, f"{display(path)} missing: {SETUP_HINT}")


def _python_line(pyproject: Path, version: tuple[int, ...]) -> Line:
    shown = ".".join(str(part) for part in version)
    try:
        spec, minimum = requires_python(pyproject)
    except (OSError, ValueError) as exc:
        return Line("FAIL", ENVIRONMENT, f"Python {shown}; cannot read requires-python ({exc})")
    if version < minimum:
        return Line("FAIL", ENVIRONMENT, f"Python {shown} is older than {display(pyproject)} allows ({spec})")
    return Line("PASS", ENVIRONMENT, f"Python {shown} ({display(pyproject)}: requires-python {spec})")


def check_environment(
    *,
    venv_python: Path = VENV_PYTHON,
    node_modules: Path = NODE_MODULES,
    pyproject: Path = PYPROJECT,
    version: Sequence[int] | None = None,
) -> list[Line]:
    """backend/.venv's python, frontend/node_modules, and this interpreter against `requires-python`."""
    current = tuple(sys.version_info[:3]) if version is None else tuple(version)
    return [
        _present(venv_python, venv_python.is_file()),
        _present(node_modules, node_modules.is_dir()),
        _python_line(pyproject, current),
    ]


# ------------------------------------------------------------------ 2. keys


def check_keys_offline(env_file: Path, environ: Mapping[str, str]) -> list[Line]:
    """Each provider key as SET (PASS) or NOT SET (INFO), read as check_keys.py reads it; no value leaves."""
    lines: list[Line] = []
    try:
        dotenv = check_keys.read_dotenv(env_file)
    except (OSError, ValueError) as exc:
        dotenv = {}
        reason = getattr(exc, "strerror", None) or type(exc).__name__
        detail = f"could not read {display(env_file)} ({reason}); the environment only"
        lines.append(Line("INFO", KEYS, detail))
    for name in (*check_keys.KEY_NAMES, *check_keys.OPTIONAL_KEY_NAMES):
        if check_keys.is_set(check_keys.key_value(name, environ, dotenv)):
            lines.append(Line("PASS", KEYS, f"{name} SET"))
        else:
            lines.append(Line("INFO", KEYS, f"{name} NOT SET: {SIMULATED_HINT}"))
    return lines


# ------------------------------------------------------------------ 3. artefacts


@dataclass(frozen=True, slots=True)
class ManifestDiff:
    """How the artefacts on disk differ from MANIFEST.json's `artifacts` map (posix paths, sorted)."""

    missing: tuple[str, ...]  # listed, not on disk
    changed: tuple[str, ...]  # listed, on disk with another sha256
    unlisted: tuple[str, ...]  # on disk, not listed


def compare_manifest(listed: Mapping[str, str], on_disk: Mapping[str, str]) -> ManifestDiff:
    """Compare two `{posix path: sha256}` maps: what MANIFEST.json lists and what is on disk."""
    changed = (path for path, sha in listed.items() if path in on_disk and on_disk[path] != sha)
    return ManifestDiff(
        missing=tuple(sorted(set(listed) - set(on_disk))),
        changed=tuple(sorted(changed)),
        unlisted=tuple(sorted(set(on_disk) - set(listed))),
    )


def listed_artefacts(manifest_path: Path) -> dict[str, str]:
    """MANIFEST.json's `artifacts` map; ValueError (safe to print) when missing, unreadable or odd."""
    try:
        document = json.loads(manifest_path.read_text(encoding="utf-8"))
    except FileNotFoundError:
        raise ValueError(f"{MANIFEST} missing") from None
    except (OSError, ValueError) as exc:
        raise ValueError(f"{MANIFEST} unreadable ({exc})") from None
    listed = document.get("artifacts") if isinstance(document, dict) else None
    if not isinstance(listed, dict) or not all(isinstance(sha, str) for sha in listed.values()):
        raise ValueError(f"{MANIFEST} has no artifacts map of path -> sha256")
    return dict(listed)


def _json_problem(path: Path) -> str | None:
    """Why `path` is not a JSON object, or None when it is one."""
    try:
        parsed = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, ValueError) as exc:  # JSONDecodeError and UnicodeDecodeError are ValueErrors
        return str(exc)
    return None if isinstance(parsed, dict) else "not a JSON object"


def unparseable_artefacts(artifacts_dir: Path, present: Sequence[str]) -> list[str]:
    """`path (reason)` for each present JSON file that is not an object, and for model/ if it won't load."""
    from chhatri.forecast.errors import ModelArtifactError
    from chhatri.forecast.persistence import load_model

    bad = []
    for path in present:
        problem = _json_problem(artifacts_dir / path) if path.endswith(".json") else None
        if problem is not None:
            bad.append(f"{path} ({problem})")
    try:  # whatever the manifest lists: the replay cannot run without a model
        load_model(artifacts_dir / MODEL_DIR)
    except (ModelArtifactError, OSError, ValueError) as exc:
        bad.append(f"{MODEL_DIR}/ ({exc})")
    return bad


def check_artefacts(artifacts_dir: Path = ARTIFACTS_DIR) -> list[Line]:
    """Committed artefacts present, parseable and as MANIFEST.json records them; unlisted files are INFO."""
    from chhatri.pipeline.manifest import artifact_hashes  # the manifest writer's own file set and digest

    lines: list[Line] = []
    try:
        listed = listed_artefacts(artifacts_dir / MANIFEST)
    except ValueError as exc:
        listed = {}
        lines.append(Line("FAIL", ARTEFACTS, str(exc)))
    on_disk = artifact_hashes(artifacts_dir)
    diff = compare_manifest(listed, on_disk)
    missing = sorted({*diff.missing, *(path for path in REQUIRED_ARTEFACTS if path not in on_disk)})
    present = sorted(path for path in {*REQUIRED_ARTEFACTS, *listed} if path in on_disk)
    unparseable = unparseable_artefacts(artifacts_dir, present)
    for label, paths in (
        ("missing", missing),
        (f"sha256 differs from {MANIFEST}", diff.changed),
        ("does not parse", unparseable),
    ):
        if paths:
            lines.append(Line("FAIL", ARTEFACTS, f"{label}: {', '.join(paths)}"))
    if not lines:
        detail = f"{len(listed)} files match {MANIFEST} (sha256); the JSON files parse and {MODEL_DIR}/ loads"
        lines.append(Line("PASS", ARTEFACTS, detail))
    if diff.unlisted:
        lines.append(Line("INFO", ARTEFACTS, f"on disk, not in {MANIFEST}: {', '.join(diff.unlisted)}"))
    return lines


# ------------------------------------------------------------------ 4, 5. in process: demo check, audit chain


def judge_settings(var_dir: Path) -> Settings:
    """`offline_settings` (every live integration off, demo mode on), the demo flags only, its own var dir.

    `OFFLINE_OVERRIDES` blanks every provider key; the Gemini key is blanked here again and the free-tier
    data gate is closed (ADR 0009), so no AI provider can be called whatever the shell exports. The officer
    token is set here (random, never printed) so the app has no generated token to announce in its log."""
    from chhatri.api.demo.local import DEMO_FEATURES, offline_settings

    return offline_settings(
        chhatri_var_dir=var_dir,
        chhatri_features=",".join(DEMO_FEATURES),
        chhatri_officer_token=secrets.token_urlsafe(OFFICER_TOKEN_BYTES),
        google_api_key=None,
        chhatri_data_is_synthetic=False,
    )


def run_in_temp_var_dir(run: Callable[[Path], Coroutine[Any, Any, Any]]) -> Any:
    """`run(var_dir)` to its end in a fresh temporary directory, removed afterwards."""
    with tempfile.TemporaryDirectory(prefix=VAR_DIR_PREFIX) as var_dir:
        return asyncio.run(run(Path(var_dir)))


async def rehearse_in_process(var_dir: Path) -> tuple[CheckRow, ...]:
    """demo_check.py without --url: the rehearsal on the app in this process, rows compared with GOLDEN."""
    from chhatri.api.demo import GOLDEN, DemoApi, compare, expectations, rehearse
    from chhatri.api.demo.local import in_process_client

    async with in_process_client(judge_settings(var_dir), timeout_s=REQUEST_TIMEOUT_S) as client:
        return compare(await rehearse(DemoApi(client)), expectations(GOLDEN))


def check_demo(
    rehearse: Callable[[Path], Coroutine[Any, Any, Sequence[CheckRow]]] = rehearse_in_process,
) -> list[Line]:
    """Every rehearsal row must pass (SKIP is not a failure, as in demo_check.py); failures are named."""
    rows = run_in_temp_var_dir(rehearse)
    if not rows:
        return [Line("FAIL", DEMO, "the rehearsal produced no checks")]
    failed = [row for row in rows if row.status == "FAIL"]
    if failed:
        names = ", ".join(f"{row.scenario} · {row.check}" for row in failed[:FAILURES_SHOWN])
        more = f" and {len(failed) - FAILURES_SHOWN} more" if len(failed) > FAILURES_SHOWN else ""
        detail = f"{len(failed)} of {len(rows)} checks failed: {names}{more}"
        return [Line("FAIL", DEMO, f"{detail} (make demo-check prints them all)")]
    skipped = sum(row.status == "SKIP" for row in rows)
    counts = f"{len(rows) - skipped} of {len(rows)} checks passed"
    tail = f", {skipped} skipped" if skipped else ""
    return [Line("PASS", DEMO, f"{counts}{tail} (in process, every live integration off)")]


@dataclass(frozen=True, slots=True)
class ChainReport:
    """What GET /api/audit/verify answered after the payout, and how many payouts were credited by then."""

    valid: bool
    entries: int
    first_bad_seq: int | None
    credited: int


async def audit_after_payout(var_dir: Path) -> ChainReport:
    """Monsoon in a fresh in-process app, replayed past its payout, then the chain recomputed (SPEC §11)."""
    from chhatri.api.demo import DemoApi
    from chhatri.api.demo.local import in_process_client

    async with in_process_client(judge_settings(var_dir), timeout_s=REQUEST_TIMEOUT_S) as client:
        api = DemoApi(client)
        await api.post("/api/replay/load", {"scenario": AUDIT_SCENARIO})
        await api.post("/api/replay/seek", {"to": AFTER_PAYOUT})
        payouts = await api.get_all("/api/payouts")
        chain = await api.get("/api/audit/verify")
    return ChainReport(
        valid=chain["valid"] is True,
        entries=int(chain["entries"]),
        first_bad_seq=chain["first_bad_seq"],
        credited=sum(payout["status"] == "CREDITED" for payout in payouts),
    )


def check_audit(
    verify: Callable[[Path], Coroutine[Any, Any, ChainReport]] = audit_after_payout,
) -> list[Line]:
    """The chain must verify after money moved: valid, not empty, and at least one payout credited."""
    report = run_in_temp_var_dir(verify)
    where = f"({AUDIT_SCENARIO} at {AFTER_PAYOUT})"
    if not report.valid:
        detail = f"chain broken at seq {report.first_bad_seq} of {report.entries} entries {where}"
        return [Line("FAIL", AUDIT, detail)]
    counts = f"{report.entries} entries, {report.credited} payouts credited {where}"
    if report.entries == 0 or report.credited == 0:
        return [Line("FAIL", AUDIT, f"nothing to verify: {counts}")]
    return [Line("PASS", AUDIT, f"valid: {counts}")]


# ------------------------------------------------------------------ 6. frontend


def check_frontend(
    frontend_dir: Path = FRONTEND_DIR,
    *,
    run: Runner = subprocess.run,
    which: Callable[[str], str | None] = shutil.which,
) -> list[Line]:
    """`npm run -s typecheck` in frontend/: PASS on exit 0, else how many TypeScript errors and the first."""
    npm = which("npm")
    if npm is None:
        return [Line("FAIL", FRONTEND, "npm is not on PATH (Node 22, see README.md)")]
    try:
        done = run(
            [npm, *TYPECHECK],
            cwd=frontend_dir,
            capture_output=True,
            text=True,
            timeout=TYPECHECK_TIMEOUT_S,
            check=False,
        )
    except subprocess.TimeoutExpired:
        return [Line("FAIL", FRONTEND, f"npm run typecheck did not finish in {TYPECHECK_TIMEOUT_S:.0f} s")]
    if done.returncode == 0:
        return [Line("PASS", FRONTEND, "npm run typecheck: no type errors")]
    output = [text.strip() for text in f"{done.stdout}\n{done.stderr}".splitlines() if text.strip()]
    errors = [text for text in output if "error TS" in text]
    first = errors[0] if errors else (output[-1] if output else "no output")
    count = f"{len(errors)} type errors, the first: " if errors else ""
    return [Line("FAIL", FRONTEND, f"npm run typecheck exited {done.returncode}: {count}{first}")]


# ------------------------------------------------------------------ report


def default_checks(env_file: Path, environ: Mapping[str, str]) -> tuple[tuple[str, Check], ...]:
    """The six checks of the module docstring, in order."""
    return (
        (ENVIRONMENT, check_environment),
        (KEYS, functools.partial(check_keys_offline, env_file, environ)),
        (ARTEFACTS, check_artefacts),
        (DEMO, check_demo),
        (AUDIT, check_audit),
        (FRONTEND, check_frontend),
    )


def run_checks(checks: Sequence[tuple[str, Check]], *, out: Callable[[str], None] = emit) -> list[Line]:
    """Every check in order, printed as soon as it ends; a check that raises becomes one FAIL line."""
    lines: list[Line] = []
    for what, check in checks:
        try:
            produced = list(check())
        except ImportError as exc:
            produced = [Line("FAIL", what, f"the backend does not import ({exc}): {SETUP_HINT}")]
        except Exception as exc:  # one broken check must not hide the others; the traceback goes to stderr
            logger.exception("judge: the %s check stopped", what)
            produced = [Line("FAIL", what, f"{type(exc).__name__}: {exc}")]
        for line in produced:
            out(line.render())
        lines.extend(produced)
    return lines


def verdict(lines: Sequence[Line]) -> tuple[int, list[str]]:
    """The exit status and the closing lines: READY alone, or NOT READY followed by every FAIL line."""
    failed = [line for line in lines if line.status == "FAIL"]
    if not failed:
        return EXIT_READY, [READY]
    listed = [f"  - {line.what}: {line.detail}" for line in failed]
    return EXIT_NOT_READY, [f"{NOT_READY}: {len(failed)} failed", *listed]


def main(argv: Sequence[str] | None = None, *, checks: Sequence[tuple[str, Check]] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Is this Chhatri build sound? Six checks, then READY or not")
    parser.add_argument("--env-file", type=Path, default=REPO_ROOT / ".env", help="default: the repo's .env")
    args = parser.parse_args(argv)
    logging.basicConfig(level=logging.WARNING, format="%(levelname)s %(name)s: %(message)s")
    if str(BACKEND_DIR) not in sys.path:  # the venv's editable install provides it too
        sys.path.insert(0, str(BACKEND_DIR))
    lines = run_checks(checks if checks is not None else default_checks(args.env_file, os.environ))
    code, closing = verdict(lines)
    for text in closing:
        emit(text)
    return code


if __name__ == "__main__":
    sys.exit(main())
