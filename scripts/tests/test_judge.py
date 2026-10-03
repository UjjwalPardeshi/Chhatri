# ruff: noqa: S105, S106 - test fixtures: dummy keys, never real credentials
"""`make judge`: six checks in order, then `CHHATRI JUDGE READY ✓` or the list of failures.

The slow parts (the in-process app, the demo rehearsal, npm) are fakes here; `make judge` runs them for real.
"""

from __future__ import annotations

import hashlib
import json
import shutil
import subprocess
import sys
import urllib.request
from collections.abc import AsyncIterator, Callable, Coroutine, Mapping
from contextlib import asynccontextmanager
from pathlib import Path
from types import MappingProxyType
from typing import Any, Final

import httpx
import pytest
from chhatri.api.demo import GOLDEN, CheckRow, DemoApi, ScenarioRun, expectations
from chhatri.forecast.errors import ModelArtifactError

import judge

MAKE = shutil.which("make") or "make"
SARVAM = "sarvam-DUMMY-key-5a1c"
GOOGLE = "AIza-DUMMY-key-9f3e"
TELEGRAM = "123456:DUMMY-telegram-token"
NPM = "/opt/node/bin/npm"
AT_1710 = "(monsoon at 17:10)"
ARTEFACTS: Final = MappingProxyType(
    {
        "premiums.json": '{"Z7": 300}',
        "calibration.json": '{"z9_slow_depth": 0.39}',
        "backtest/report.json": '{"zones": []}',
        "backtest/report.md": "# Backtest\n",
        "model/manifest.json": '{"seed": 20251019}',
        "model/p50.txt": "tree\nversion=v4\n",
    }
)
TS_ERRORS = (
    "src/a.ts(3,7): error TS2322: Type 'string' is not assignable to type 'number'.\n"
    "src/b.ts(1,1): error TS2304: Cannot find name 'x'.\n"
)


@pytest.fixture(autouse=True)
def no_real_network(monkeypatch: pytest.MonkeyPatch) -> None:
    """The judge checks keys offline: no test may reach a provider."""

    def refuse(*_args: object, **_kwargs: object) -> None:
        raise AssertionError("the judge must never call a provider")

    monkeypatch.setattr(urllib.request, "urlopen", refuse)


def statuses(lines: list[judge.Line]) -> list[str]:
    return [line.status for line in lines]


def report(lines: list[judge.Line]) -> list[tuple[str, str]]:
    return [(line.status, line.detail) for line in lines]


def test_a_line_shows_status_what_and_detail_in_columns() -> None:
    assert (
        judge.Line("PASS", "keys", "GOOGLE_API_KEY SET").render() == "PASS  keys         GOOGLE_API_KEY SET"
    )
    assert judge.Line("FAIL", "environment", "x").render() == "FAIL  environment  x"


# ------------------------------------------------------------------ 1. environment


def pyproject(tmp_path: Path, text: str = 'requires-python = ">=3.12,<3.13"') -> Path:
    path = tmp_path / "pyproject.toml"
    path.write_text(f'[project]\nname = "chhatri"\n{text}\n', encoding="utf-8")
    return path


def test_the_environment_passes_with_the_venv_node_modules_and_a_new_enough_python(tmp_path: Path) -> None:
    python, modules = tmp_path / "python", tmp_path / "node_modules"
    python.write_text("", encoding="utf-8")
    modules.mkdir()
    lines = judge.check_environment(
        venv_python=python, node_modules=modules, pyproject=pyproject(tmp_path), version=(3, 12, 3)
    )
    assert statuses(lines) == ["PASS", "PASS", "PASS"]
    assert lines[2].detail == f"Python 3.12.3 ({tmp_path / 'pyproject.toml'}: requires-python >=3.12,<3.13)"


def test_the_environment_names_what_is_missing_and_a_python_too_old(tmp_path: Path) -> None:
    lines = judge.check_environment(
        venv_python=tmp_path / "python",
        node_modules=tmp_path / "node_modules",
        pyproject=pyproject(tmp_path),
        version=(3, 11, 9),
    )
    assert statuses(lines) == ["FAIL", "FAIL", "FAIL"]
    assert lines[0].detail == f"{tmp_path / 'python'} missing: run make setup"
    assert lines[1].detail == f"{tmp_path / 'node_modules'} missing: run make setup"
    assert lines[2].detail.startswith("Python 3.11.9 is older than")
    assert lines[2].detail.endswith("(>=3.12,<3.13)")


def test_the_environment_defaults_to_this_checkout_and_this_interpreter() -> None:
    lines = judge.check_environment()
    assert "backend/.venv/bin/python" in lines[0].detail and "frontend/node_modules" in lines[1].detail
    major, minor = sys.version_info[:2]
    assert lines[2].detail.startswith(f"Python {major}.{minor}.")
    assert "backend/pyproject.toml" in lines[2].detail


@pytest.mark.parametrize(
    ("text", "expected"),
    [
        ('requires-python = ">=3.12,<3.13"', (">=3.12,<3.13", (3, 12))),
        ("requires-python = '>= 3.10'", (">= 3.10", (3, 10))),
        ('requires-python = "<3.14,>=3.12.4"', ("<3.14,>=3.12.4", (3, 12, 4))),
    ],
)
def test_requires_python_reads_the_lower_bound(
    tmp_path: Path, text: str, expected: tuple[str, tuple[int, ...]]
) -> None:
    assert judge.requires_python(pyproject(tmp_path, text)) == expected


def test_the_backend_asks_for_python_3_12(repo_root: Path) -> None:
    assert judge.requires_python(repo_root / "backend" / "pyproject.toml")[1] == (3, 12)


@pytest.mark.parametrize("text", ["", 'requires-python = "<3.13"'])
def test_a_pyproject_without_a_lower_bound_fails_the_python_line(tmp_path: Path, text: str) -> None:
    path = pyproject(tmp_path, text)
    with pytest.raises(ValueError, match="no requires-python lower bound"):
        judge.requires_python(path)
    for broken in (path, tmp_path / "missing.toml"):
        line = judge.check_environment(pyproject=broken, version=(3, 12, 3))[2]
        assert line.status == "FAIL" and line.detail.startswith("Python 3.12.3; cannot read requires-python")


# ------------------------------------------------------------------ 2. keys


def test_keys_are_set_or_not_set_never_a_failure_and_never_shown(tmp_path: Path) -> None:
    env_file = tmp_path / ".env"
    env_file.write_text(f"GOOGLE_API_KEY={GOOGLE}\nTELEGRAM_BOT_TOKEN={TELEGRAM}\n", encoding="utf-8")
    environ = {"SARVAM_API_KEY": SARVAM, "TELEGRAM_BOT_TOKEN": ""}  # an empty variable wins over .env
    lines = judge.check_keys_offline(env_file, environ)
    assert report(lines) == [
        ("PASS", "SARVAM_API_KEY SET"),
        ("PASS", "GOOGLE_API_KEY SET"),
        ("INFO", "TELEGRAM_BOT_TOKEN NOT SET: the demo runs simulated without it"),
    ]
    text = "\n".join(line.render() for line in lines)
    for secret in (SARVAM, GOOGLE, TELEGRAM, SARVAM[:8], GOOGLE[-4:], TELEGRAM[:6]):
        assert secret not in text


def test_an_unreadable_env_file_is_info_and_the_environment_still_counts(tmp_path: Path) -> None:
    lines = judge.check_keys_offline(tmp_path, {"GOOGLE_API_KEY": GOOGLE})  # a directory cannot be read
    assert lines[0].status == "INFO" and lines[0].detail.startswith(f"could not read {tmp_path}")
    assert "FAIL" not in statuses(lines) and ("PASS", "GOOGLE_API_KEY SET") in report(lines)


# ------------------------------------------------------------------ 3. artefacts


def sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def artefacts(root: Path, files: Mapping[str, str] = ARTEFACTS) -> Path:
    """An artefacts directory holding `files` and a MANIFEST.json that lists each with its sha256."""
    for name, text in files.items():
        (root / name).parent.mkdir(parents=True, exist_ok=True)
        (root / name).write_text(text, encoding="utf-8")
    listed = {name: sha256(root / name) for name in sorted(files)}
    (root / "MANIFEST.json").write_text(json.dumps({"artifacts": listed, "seed": 1}), encoding="utf-8")
    return root


@pytest.fixture
def model_loads(monkeypatch: pytest.MonkeyPatch) -> list[Path]:
    """The backend's model loader, replaced by one that accepts any directory and records it."""
    loaded: list[Path] = []
    monkeypatch.setattr("chhatri.forecast.persistence.load_model", loaded.append)
    return loaded


def test_compare_manifest_sorts_missing_changed_and_unlisted_paths() -> None:
    listed = {"b.json": "1", "a.json": "2", "model/p10.txt": "3", "gone.md": "4"}
    on_disk = {"a.json": "2", "b.json": "9", "model/p10.txt": "3", "zz/new.json": "5", "evals/x.json": "6"}
    assert judge.compare_manifest(listed, on_disk) == judge.ManifestDiff(
        missing=("gone.md",), changed=("b.json",), unlisted=("evals/x.json", "zz/new.json")
    )
    assert judge.compare_manifest(on_disk, on_disk) == judge.ManifestDiff((), (), ())


@pytest.mark.parametrize(
    ("content", "message"),
    [
        (None, "MANIFEST.json missing"),
        ("{not json", "MANIFEST.json unreadable"),
        ("[]", "no artifacts map"),
        ('{"artifacts": ["premiums.json"]}', "no artifacts map"),
        ('{"artifacts": {"premiums.json": 1}}', "no artifacts map"),
    ],
)
def test_a_missing_unreadable_or_odd_manifest_is_refused(
    tmp_path: Path, content: str | None, message: str
) -> None:
    path = tmp_path / "MANIFEST.json"
    if content is not None:
        path.write_text(content, encoding="utf-8")
    with pytest.raises(ValueError, match=message):
        judge.listed_artefacts(path)


def test_artefacts_that_match_the_manifest_pass_and_extra_files_are_info(
    tmp_path: Path, model_loads: list[Path]
) -> None:
    root = artefacts(tmp_path)
    (root / "evals").mkdir()
    (root / "evals" / "summary.json").write_text("{}", encoding="utf-8")
    (root / ".model-staging").mkdir()  # hidden, skipped as the manifest writer skips it
    (root / ".model-staging" / "p50.txt").write_text("half written", encoding="utf-8")
    assert report(judge.check_artefacts(root)) == [
        ("PASS", "6 files match MANIFEST.json (sha256); the JSON files parse and model/ loads"),
        ("INFO", "on disk, not in MANIFEST.json: evals/summary.json"),
    ]
    assert model_loads == [root / "model"]


def test_missing_changed_and_unparseable_artefacts_each_fail(tmp_path: Path, model_loads: list[Path]) -> None:
    root = artefacts(tmp_path)
    (root / "premiums.json").unlink()
    (root / "backtest" / "report.md").write_text("# edited by hand\n", encoding="utf-8")
    (root / "calibration.json").write_text("[0.39]", encoding="utf-8")
    (root / "model" / "manifest.json").write_text("{oops", encoding="utf-8")
    lines = judge.check_artefacts(root)
    assert statuses(lines) == ["FAIL", "FAIL", "FAIL"]
    assert lines[0].detail == "missing: premiums.json"
    assert lines[1].detail == (
        "sha256 differs from MANIFEST.json: backtest/report.md, calibration.json, model/manifest.json"
    )
    assert lines[2].detail.startswith(
        "does not parse: calibration.json (not a JSON object), model/manifest.json ("
    )


def test_without_a_manifest_the_required_files_are_still_checked(
    tmp_path: Path, model_loads: list[Path]
) -> None:
    root = artefacts(tmp_path)
    (root / "MANIFEST.json").unlink()
    (root / "premiums.json").unlink()
    lines = judge.check_artefacts(root)
    assert [line.detail for line in lines if line.status == "FAIL"] == [
        "MANIFEST.json missing",
        "missing: premiums.json",
    ]
    assert lines[-1].status == "INFO" and "model/p50.txt" in lines[-1].detail  # every file is now unlisted


def test_a_model_that_does_not_load_fails_the_artefacts(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    def broken(directory: Path) -> None:
        raise ModelArtifactError(f"missing model file {directory / 'p10.txt'}")

    monkeypatch.setattr("chhatri.forecast.persistence.load_model", broken)
    lines = judge.check_artefacts(artefacts(tmp_path))
    assert report(lines) == [
        ("FAIL", f"does not parse: model/ (missing model file {tmp_path / 'model' / 'p10.txt'})")
    ]


# ------------------------------------------------------------------ 4, 5. in process


def test_each_in_process_run_gets_a_temporary_var_dir_removed_afterwards() -> None:
    seen: list[Path] = []

    async def run(var_dir: Path) -> str:
        seen.append(var_dir)
        assert var_dir.is_dir()
        return "done"

    assert judge.run_in_temp_var_dir(run) == "done"
    assert seen[0].name.startswith("chhatri-judge-") and not seen[0].exists()


def test_the_in_process_settings_call_no_provider_and_touch_no_running_backend(tmp_path: Path) -> None:
    settings = judge.judge_settings(tmp_path)
    assert settings.chhatri_var_dir == tmp_path and settings.chhatri_demo_mode
    assert settings.chhatri_features == "x4_lender_request"  # the demo flags only, whatever the shell exports
    live = (settings.sarvam_live, settings.gemini_key_set, settings.whatsapp_live, settings.telegram_live)
    assert live == (False, False, False, False) and not settings.chhatri_data_is_synthetic
    assert (settings.paytm_mode, settings.n8n_live, settings.cognee_enabled) == ("simulated", False, False)
    assert "chhatri_officer_token" in settings.model_fields_set  # so the app never logs a generated token


def row(status: str, check: str = "KPI shops paid") -> CheckRow:
    return CheckRow("monsoon", check, 312, 312 if status == "PASS" else 311, status)  # type: ignore[arg-type]


def rehearsal(*rows: CheckRow) -> Callable[[Path], Coroutine[Any, Any, tuple[CheckRow, ...]]]:
    async def rehearse(var_dir: Path) -> tuple[CheckRow, ...]:
        assert var_dir.is_dir()
        return rows

    return rehearse


def test_the_demo_check_passes_when_no_row_failed() -> None:
    assert report(judge.check_demo(rehearsal(row("PASS"), row("PASS"), row("SKIP")))) == [
        ("PASS", "2 of 3 checks passed, 1 skipped (in process, every live integration off)")
    ]


def test_the_demo_check_names_the_first_failures() -> None:
    failed = [row("FAIL", f"check {n}") for n in range(5)]
    assert report(judge.check_demo(rehearsal(row("PASS"), *failed))) == [
        (
            "FAIL",
            "5 of 6 checks failed: monsoon · check 0, monsoon · check 1, monsoon · check 2 and 2 more "
            "(make demo-check prints them all)",
        )
    ]
    assert report(judge.check_demo(rehearsal())) == [("FAIL", "the rehearsal produced no checks")]


def test_the_rehearsal_runs_on_an_in_process_app_of_its_own(monkeypatch: pytest.MonkeyPatch) -> None:
    seen: dict[str, Any] = {}

    @asynccontextmanager
    async def fake_client(settings: Any, *, timeout_s: float) -> AsyncIterator[str]:
        seen.update(settings=settings, timeout_s=timeout_s, var_dir_existed=settings.chhatri_var_dir.is_dir())
        yield "the in-process client"

    async def fake_rehearse(api: DemoApi) -> tuple[ScenarioRun, ...]:
        seen["api"] = api
        return tuple(ScenarioRun(name, dict(checks)) for name, checks in expectations(GOLDEN).items())

    monkeypatch.setattr("chhatri.api.demo.local.in_process_client", fake_client)
    monkeypatch.setattr("chhatri.api.demo.rehearse", fake_rehearse)
    total = sum(len(checks) for checks in expectations(GOLDEN).values())
    assert report(judge.check_demo()) == [
        ("PASS", f"{total} of {total} checks passed (in process, every live integration off)")
    ]
    assert isinstance(seen["api"], DemoApi) and seen["timeout_s"] == judge.REQUEST_TIMEOUT_S
    assert seen["var_dir_existed"] and not seen["settings"].chhatri_var_dir.exists()
    assert seen["settings"].chhatri_features == "x4_lender_request"


@pytest.mark.parametrize(
    ("chain", "expected"),
    [
        (judge.ChainReport(True, 4210, None, 312), ("PASS", "valid: 4210 entries, 312 payouts credited")),
        (judge.ChainReport(False, 4210, 17, 312), ("FAIL", "chain broken at seq 17 of 4210 entries")),
        (judge.ChainReport(True, 0, None, 0), ("FAIL", "nothing to verify: 0 entries, 0 payouts credited")),
        (judge.ChainReport(True, 90, None, 0), ("FAIL", "nothing to verify: 90 entries, 0 payouts credited")),
    ],
)
def test_the_audit_check_wants_a_valid_chain_after_money_moved(
    chain: judge.ChainReport, expected: tuple[str, str]
) -> None:
    async def verify(var_dir: Path) -> judge.ChainReport:
        assert var_dir.is_dir()
        return chain

    status, detail = expected
    assert report(judge.check_audit(verify)) == [(status, f"{detail} {AT_1710}")]


def test_the_audit_run_loads_monsoon_seeks_past_the_payout_then_verifies(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    calls: list[tuple[str, str, Any]] = []

    def backend(request: httpx.Request) -> httpx.Response:
        body = json.loads(request.content) if request.content else None
        calls.append((request.method, request.url.path, body))
        if request.url.path == "/api/payouts":
            items = [{"status": "CREDITED"}, {"status": "CREDITED"}, {"status": "FAILED"}]
            meta = {"total": len(items), "limit": 500, "offset": 0}
            return httpx.Response(200, json={"ok": True, "data": items, "meta": meta})
        if request.url.path == "/api/audit/verify":
            chain = {"valid": True, "entries": 57, "head_hash": "ab12", "first_bad_seq": None}
            return httpx.Response(200, json={"ok": True, "data": chain})
        return httpx.Response(200, json={"ok": True, "data": {"label": "17:10"}})

    @asynccontextmanager
    async def fake_client(settings: Any, *, timeout_s: float) -> AsyncIterator[httpx.AsyncClient]:
        transport = httpx.MockTransport(backend)
        async with httpx.AsyncClient(transport=transport, base_url="http://judge.test") as client:
            yield client

    monkeypatch.setattr("chhatri.api.demo.local.in_process_client", fake_client)
    assert report(judge.check_audit()) == [("PASS", f"valid: 57 entries, 2 payouts credited {AT_1710}")]
    assert calls == [
        ("POST", "/api/replay/load", {"scenario": "monsoon"}),
        ("POST", "/api/replay/seek", {"to": "17:10"}),
        ("GET", "/api/payouts", None),
        ("GET", "/api/audit/verify", None),
    ]


# ------------------------------------------------------------------ 6. frontend


class FakeNpm:
    """`subprocess.run` for npm: records each call and answers with a fixed result, or raises."""

    def __init__(self, code: int = 0, stdout: str = "", stderr: str = "", raises: Exception | None = None):
        self.result = (code, stdout, stderr)
        self.raises = raises
        self.calls: list[tuple[list[str], dict[str, Any]]] = []

    def __call__(self, argv: list[str], **kwargs: Any) -> subprocess.CompletedProcess[str]:
        self.calls.append((argv, kwargs))
        if self.raises is not None:
            raise self.raises
        return subprocess.CompletedProcess(argv, *self.result)


def npm_on_path(name: str) -> str | None:
    return NPM if name == "npm" else None


def test_the_frontend_check_runs_only_the_typecheck_script(tmp_path: Path) -> None:
    npm = FakeNpm()
    assert report(judge.check_frontend(tmp_path, run=npm, which=npm_on_path)) == [
        ("PASS", "npm run typecheck: no type errors")
    ]
    [(argv, kwargs)] = npm.calls
    assert argv == [NPM, "run", "-s", "typecheck"]
    assert (kwargs["cwd"], kwargs["timeout"], kwargs["check"]) == (tmp_path, judge.TYPECHECK_TIMEOUT_S, False)


@pytest.mark.parametrize(
    ("npm", "detail"),
    [
        (
            FakeNpm(2, stdout=TS_ERRORS),
            "exited 2: 2 type errors, the first: "
            "src/a.ts(3,7): error TS2322: Type 'string' is not assignable to type 'number'.",
        ),
        (
            FakeNpm(1, stderr='npm error Missing script: "typecheck"\n'),
            'exited 1: npm error Missing script: "typecheck"',
        ),
        (FakeNpm(1), "exited 1: no output"),
        (FakeNpm(raises=subprocess.TimeoutExpired([NPM], 300)), "did not finish in 300 s"),
    ],
)
def test_a_failing_typecheck_says_why(tmp_path: Path, npm: FakeNpm, detail: str) -> None:
    lines = judge.check_frontend(tmp_path, run=npm, which=npm_on_path)
    assert report(lines) == [("FAIL", f"npm run typecheck {detail}")]


def test_without_npm_nothing_runs_and_the_frontend_fails(tmp_path: Path) -> None:
    npm = FakeNpm()
    lines = judge.check_frontend(tmp_path, run=npm, which=lambda _name: None)
    assert report(lines) == [("FAIL", "npm is not on PATH (Node 22, see README.md)")] and npm.calls == []


# ------------------------------------------------------------------ report and exit status


def passing() -> list[judge.Line]:
    return [
        judge.Line("PASS", "environment", "present"),
        judge.Line("INFO", "keys", "GOOGLE_API_KEY NOT SET"),
    ]


def failing() -> list[judge.Line]:
    return [
        judge.Line("FAIL", "artefacts", "missing: premiums.json"),
        judge.Line("FAIL", "artefacts", "sha256 differs from MANIFEST.json: model/p10.txt"),
    ]


def test_every_line_is_printed_in_order_and_a_broken_check_is_one_fail() -> None:
    def no_backend() -> list[judge.Line]:
        raise ModuleNotFoundError("No module named 'pydantic'")

    def broken() -> list[judge.Line]:
        raise RuntimeError("the app did not start")

    printed: list[str] = []
    checks = [("environment", passing), ("artefacts", no_backend), ("demo check", broken)]
    lines = judge.run_checks(checks, out=printed.append)
    assert printed == [line.render() for line in lines]
    assert [(line.status, line.what) for line in lines] == [
        ("PASS", "environment"),
        ("INFO", "keys"),
        ("FAIL", "artefacts"),
        ("FAIL", "demo check"),
    ]
    assert lines[2].detail == "the backend does not import (No module named 'pydantic'): run make setup"
    assert lines[3].detail == "RuntimeError: the app did not start"


def test_nothing_failed_ends_with_ready_and_exit_0(capsys: pytest.CaptureFixture[str]) -> None:
    assert judge.main([], checks=[("environment", passing)]) == 0
    out = capsys.readouterr().out.splitlines()
    assert out == [*(line.render() for line in passing()), "CHHATRI JUDGE READY ✓"]


def test_a_failure_lists_every_failed_line_and_exits_1(capsys: pytest.CaptureFixture[str]) -> None:
    assert judge.main([], checks=[("environment", passing), ("artefacts", failing)]) == 1
    out = capsys.readouterr().out.splitlines()
    assert "CHHATRI JUDGE READY ✓" not in out
    assert out[-3:] == [
        "CHHATRI JUDGE NOT READY: 2 failed",
        "  - artefacts: missing: premiums.json",
        "  - artefacts: sha256 differs from MANIFEST.json: model/p10.txt",
    ]


def test_the_default_checks_are_the_six_in_order(tmp_path: Path) -> None:
    checks = judge.default_checks(tmp_path / ".env", {"GOOGLE_API_KEY": GOOGLE})
    names = ["environment", "keys", "artefacts", "demo check", "audit chain", "frontend"]
    assert [name for name, _ in checks] == names
    assert ("PASS", "GOOGLE_API_KEY SET") in report(list(dict(checks)["keys"]()))


def test_make_judge_falls_back_to_python3_without_the_venv(repo_root: Path) -> None:
    dry_run = subprocess.run(  # noqa: S603 - fixed argv
        [MAKE, "--no-print-directory", "-n", "-C", str(repo_root), "judge", "VENV=/nonexistent"],
        capture_output=True,
        text=True,
        timeout=30,
        check=True,
    )
    assert dry_run.stdout.strip().endswith("&& python3 scripts/judge.py")


def test_the_script_runs_as_a_file(repo_root: Path) -> None:
    result = subprocess.run(  # noqa: S603 - fixed argv
        [sys.executable, str(repo_root / "scripts" / "judge.py"), "--help"],
        capture_output=True,
        text=True,
        timeout=60,
        check=False,
    )
    assert result.returncode == 0 and "--env-file" in result.stdout
