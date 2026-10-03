# ruff: noqa: S105, S106 - test fixtures: dummy keys, never real credentials
"""`make check-keys`: SET / NOT SET for the AI provider keys, Gemini model list; no key is ever printed."""

from __future__ import annotations

import http.client
import io
import json
import re
import subprocess
import sys
import urllib.error
import urllib.request
from collections.abc import Mapping
from email.message import Message
from pathlib import Path
from typing import Any, Self

import pytest

import check_keys as ck

SARVAM = "sarvam-DUMMY-key-5a1c"
GOOGLE = "AIza-DUMMY-key-9f3e"


def ai_not_set(out: str) -> int:
    """NOT SET lines for the two AI keys only (the Telegram line is checked on its own)."""
    return sum(
        1
        for line in out.splitlines()
        if line.startswith(("SARVAM_API_KEY", "GOOGLE_API_KEY")) and line.endswith("NOT SET")
    )


@pytest.fixture(autouse=True)
def no_real_network(monkeypatch: pytest.MonkeyPatch) -> None:
    """Every test is offline unless it installs its own fake `urlopen`."""

    def refuse(*_args: object, **_kwargs: object) -> None:
        raise AssertionError("the unit tests must never reach the network")

    monkeypatch.setattr(urllib.request, "urlopen", refuse)


class FakeResponse:
    def __init__(self, body: bytes) -> None:
        self._body = body

    def read(self) -> bytes:
        return self._body

    def __enter__(self) -> Self:
        return self

    def __exit__(self, *_exc: object) -> None:
        return None


class FakeGemini:
    """A `Fetcher` serving model pages in order and recording every (url, key) it was asked for."""

    def __init__(self, *pages: Mapping[str, Any]) -> None:
        self.pages = list(pages)
        self.calls: list[tuple[str, str]] = []

    def __call__(self, url: str, api_key: str) -> Mapping[str, Any]:
        self.calls.append((url, api_key))
        return self.pages[len(self.calls) - 1]


def model(name: str, display: str, *methods: str) -> dict[str, Any]:
    return {"name": f"models/{name}", "displayName": display, "supportedGenerationMethods": list(methods)}


GENERATE = "generateContent"
PAGE_ONE = {
    "models": [
        model("gemini-2.5-flash", "Gemini 2.5 Flash", GENERATE, "countTokens"),
        model("text-embedding-004", "Text Embedding 004", "embedContent"),
    ],
    "nextPageToken": "tok/2=",
}
PAGE_TWO = {"models": [model("gemini-2.0-flash", "Gemini 2.0 Flash", GENERATE)]}


def http_error(status: int, body: bytes) -> urllib.error.HTTPError:
    return urllib.error.HTTPError(ck.GEMINI_MODELS_URL, status, "error", Message(), io.BytesIO(body))


# ------------------------------------------------------------------ key status


def test_key_status_prefers_the_environment_over_the_env_file() -> None:
    environ = {"SARVAM_API_KEY": "", "OTHER": "x"}
    dotenv = {"SARVAM_API_KEY": SARVAM, "GOOGLE_API_KEY": GOOGLE}
    assert (
        ck.key_value("SARVAM_API_KEY", environ, dotenv) == ""
    )  # an empty variable wins, as in pydantic-settings
    assert ck.key_value("GOOGLE_API_KEY", environ, dotenv) == GOOGLE
    assert ck.key_value("GOOGLE_API_KEY", {"GOOGLE_API_KEY": "from-env"}, dotenv) == "from-env"
    assert ck.key_value("GOOGLE_API_KEY", {}, {}) == ""


@pytest.mark.parametrize(
    ("value", "expected"), [("", False), ("   ", False), ("\t\n", False), ("k", True), (" k ", True)]
)
def test_a_key_is_set_only_when_it_has_a_non_blank_value(value: str, expected: bool) -> None:
    assert ck.is_set(value) is expected


def test_read_dotenv_ignores_comments_and_a_missing_file(tmp_path: Path) -> None:
    env_file = tmp_path / ".env"
    env_file.write_text(
        "# GOOGLE_API_KEY=commented\nSARVAM_API_KEY='quoted'\nGOOGLE_API_KEY=\n", encoding="utf-8"
    )
    assert ck.read_dotenv(env_file) == {"SARVAM_API_KEY": "quoted", "GOOGLE_API_KEY": ""}
    assert ck.read_dotenv(tmp_path / "missing.env") == {}


def test_an_unreadable_env_file_is_reported_not_fatal(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    code = ck.main(["--env-file", str(tmp_path)], environ={})  # a directory cannot be read as a file
    out = capsys.readouterr().out
    assert code == 0
    assert "could not read" in out and "SARVAM_API_KEY" in out and "NOT SET" in out


# ------------------------------------------------------------------ report


def test_report_marks_each_key_and_never_prints_a_value(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    fetch = FakeGemini(PAGE_TWO)
    environ = {"SARVAM_API_KEY": SARVAM, "GOOGLE_API_KEY": GOOGLE}
    assert ck.main(["--env-file", str(tmp_path / "none")], environ=environ, fetch=fetch) == 0
    out = capsys.readouterr().out
    assert "SARVAM_API_KEY" in out and "GOOGLE_API_KEY" in out
    assert ai_not_set(out) == 0 and out.count("SET") >= 2
    for secret in (
        SARVAM,
        GOOGLE,
        SARVAM[:8],
        GOOGLE[:8],
        SARVAM[-4:],
        GOOGLE[-4:],
    ):  # not even a prefix or a tail
        assert secret not in out


def test_keys_that_are_not_set_make_no_network_call(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    fetch = FakeGemini()
    assert ck.main(["--env-file", str(tmp_path / "none")], environ={}, fetch=fetch) == 0
    out = capsys.readouterr().out
    assert ai_not_set(out) == 2
    assert fetch.calls == []


def test_strict_fails_when_a_key_is_not_set(tmp_path: Path, capsys: pytest.CaptureFixture[str]) -> None:
    fetch = FakeGemini(PAGE_TWO)
    only_google = {"GOOGLE_API_KEY": GOOGLE}
    assert ck.main(["--strict", "--env-file", str(tmp_path / "none")], environ=only_google, fetch=fetch) == 1
    assert "SARVAM_API_KEY" in capsys.readouterr().out
    both = {"SARVAM_API_KEY": SARVAM, "GOOGLE_API_KEY": GOOGLE}
    assert (
        ck.main(["--strict", "--env-file", str(tmp_path / "none")], environ=both, fetch=FakeGemini(PAGE_TWO))
        == 0
    )


def test_keys_come_from_the_env_file_when_the_environment_has_none(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    env_file = tmp_path / ".env"
    env_file.write_text(f"GOOGLE_API_KEY={GOOGLE}\nSARVAM_API_KEY=\n", encoding="utf-8")
    fetch = FakeGemini(PAGE_TWO)
    assert ck.main(["--env-file", str(env_file)], environ={}, fetch=fetch) == 0
    out = capsys.readouterr().out
    assert ai_not_set(out) == 1 and GOOGLE not in out
    assert fetch.calls and fetch.calls[0][1] == GOOGLE


# ------------------------------------------------------------------ Gemini model list


def test_lists_models_that_can_generate_across_pages_and_keeps_the_key_out_of_the_url() -> None:
    fetch = FakeGemini(PAGE_ONE, PAGE_TWO)
    models, total = ck.list_gemini_models(GOOGLE, fetch)
    assert total == 3
    assert [m.name for m in models] == ["gemini-2.0-flash", "gemini-2.5-flash"]
    assert [m.display_name for m in models] == ["Gemini 2.0 Flash", "Gemini 2.5 Flash"]
    first, second = (url for url, _ in fetch.calls)
    assert first == f"{ck.GEMINI_MODELS_URL}?pageSize={ck.PAGE_SIZE}"
    assert second == f"{ck.GEMINI_MODELS_URL}?pageSize={ck.PAGE_SIZE}&pageToken=tok%2F2%3D"
    assert all(key == GOOGLE and GOOGLE not in url for url, key in fetch.calls)


def test_report_lists_the_models_with_their_counts(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    fetch = FakeGemini(PAGE_ONE, PAGE_TWO)
    assert (
        ck.main(["--env-file", str(tmp_path / "none")], environ={"GOOGLE_API_KEY": GOOGLE}, fetch=fetch) == 0
    )
    out = capsys.readouterr().out
    assert "gemini-2.5-flash" in out and "Gemini 2.0 Flash" in out
    assert "text-embedding-004" not in out
    assert "2 of 3" in out


def test_a_runaway_page_token_loop_stops_at_the_page_limit() -> None:
    endless = {"models": [model("gemini-x", "X", GENERATE)], "nextPageToken": "again"}
    fetch = FakeGemini(*([endless] * (ck.MAX_PAGES + 5)))
    ck.list_gemini_models(GOOGLE, fetch)
    assert len(fetch.calls) == ck.MAX_PAGES


def test_a_key_with_no_generating_models_says_so(tmp_path: Path, capsys: pytest.CaptureFixture[str]) -> None:
    fetch = FakeGemini({"models": [model("text-embedding-004", "Embedding", "embedContent")]})
    assert (
        ck.main(["--env-file", str(tmp_path / "none")], environ={"GOOGLE_API_KEY": GOOGLE}, fetch=fetch) == 0
    )
    assert "no model" in capsys.readouterr().out.lower()


def test_malformed_model_entries_are_skipped() -> None:
    fetch = FakeGemini(
        {
            "models": [
                "junk",
                {"name": 7},
                {"displayName": "no name", "supportedGenerationMethods": [GENERATE]},
                model("ok", "OK", GENERATE),
            ]
        }
    )
    models, total = ck.list_gemini_models(GOOGLE, fetch)
    assert ([m.name for m in models], total) == (["ok"], 1)


def test_a_failing_model_list_is_reported_safely_and_fails_the_run(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    def refuse(_url: str, _key: str) -> Mapping[str, Any]:
        raise ck.KeyCheckError("HTTP 400 INVALID_ARGUMENT")

    assert (
        ck.main(["--env-file", str(tmp_path / "none")], environ={"GOOGLE_API_KEY": GOOGLE}, fetch=refuse) == 1
    )
    out = capsys.readouterr().out
    assert "HTTP 400 INVALID_ARGUMENT" in out and GOOGLE not in out


# ------------------------------------------------------------------ the real fetcher, with urlopen faked


def test_fetch_json_sends_the_key_in_a_header_and_parses_the_answer(monkeypatch: pytest.MonkeyPatch) -> None:
    seen: list[tuple[urllib.request.Request, float]] = []

    def fake_urlopen(request: urllib.request.Request, timeout: float) -> FakeResponse:
        seen.append((request, timeout))
        return FakeResponse(json.dumps({"models": []}).encode())

    monkeypatch.setattr(urllib.request, "urlopen", fake_urlopen)
    assert ck.fetch_json(f"{ck.GEMINI_MODELS_URL}?pageSize=5", GOOGLE) == {"models": []}
    request, timeout = seen[0]
    assert request.get_header(ck.API_KEY_HEADER.capitalize()) == GOOGLE
    assert GOOGLE not in request.full_url
    assert request.get_method() == "GET" and request.data is None
    assert timeout == ck.TIMEOUT_S


def test_fetch_json_refuses_a_plain_http_url() -> None:
    with pytest.raises(ck.KeyCheckError, match="https"):
        ck.fetch_json("http://generativelanguage.googleapis.com/v1beta/models", GOOGLE)


def test_an_http_error_is_reported_by_status_without_the_response_text(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    body = json.dumps(
        {"error": {"code": 400, "status": "INVALID_ARGUMENT", "message": f"API key not valid: {GOOGLE}"}}
    ).encode()

    def failing(_request: urllib.request.Request, timeout: float) -> FakeResponse:
        raise http_error(400, body)

    monkeypatch.setattr(urllib.request, "urlopen", failing)
    with pytest.raises(ck.KeyCheckError) as caught:
        ck.fetch_json(ck.GEMINI_MODELS_URL, GOOGLE)
    assert str(caught.value) == "HTTP 400 INVALID_ARGUMENT"
    assert GOOGLE not in str(caught.value)


@pytest.mark.parametrize(
    "body", [b"<html>nope</html>", b"[]", json.dumps({"error": {"status": "not an enum!"}}).encode()]
)
def test_an_http_error_with_an_unusable_body_still_reports_the_status(
    monkeypatch: pytest.MonkeyPatch, body: bytes
) -> None:
    def failing(_request: urllib.request.Request, timeout: float) -> FakeResponse:
        raise http_error(503, body)

    monkeypatch.setattr(urllib.request, "urlopen", failing)
    with pytest.raises(ck.KeyCheckError) as caught:
        ck.fetch_json(ck.GEMINI_MODELS_URL, GOOGLE)
    assert str(caught.value) == "HTTP 503"


@pytest.mark.parametrize(
    "failure", [urllib.error.URLError("dns"), TimeoutError("slow"), ConnectionResetError("reset")]
)
def test_a_network_failure_is_reported_by_kind(monkeypatch: pytest.MonkeyPatch, failure: Exception) -> None:
    def failing(_request: urllib.request.Request, timeout: float) -> FakeResponse:
        raise failure

    monkeypatch.setattr(urllib.request, "urlopen", failing)
    with pytest.raises(ck.KeyCheckError, match="network error"):
        ck.fetch_json(ck.GEMINI_MODELS_URL, GOOGLE)


BAD_KEY = "AIza-DUMMY-key\nsecond-line"  # a pasted second line: http.client refuses it as a header value


@pytest.mark.parametrize(
    ("failure", "message"),
    [
        # http.client's own words for an illegal header value, which quote the value: the key itself
        (ValueError(f"Invalid header value {BAD_KEY.encode()!r}"), "cannot be sent"),
        (UnicodeEncodeError("latin-1", "AIza“key", 4, 5, "ordinal not in range(256)"), "cannot be sent"),
        (http.client.IncompleteRead(b"partial"), "network error (IncompleteRead)"),
    ],
)
def test_a_request_that_cannot_be_sent_or_read_is_reported_without_the_key(
    monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str], failure: Exception, message: str
) -> None:
    def failing(_request: urllib.request.Request, timeout: float) -> FakeResponse:
        raise failure

    monkeypatch.setattr(urllib.request, "urlopen", failing)
    with pytest.raises(ck.KeyCheckError, match=re.escape(message)) as caught:
        ck.fetch_json(ck.GEMINI_MODELS_URL, BAD_KEY)
    assert "AIza" not in str(caught.value) and caught.value.__cause__ is None
    assert ck.main(["--env-file", "/nonexistent/.env"], environ={ck.GOOGLE_KEY: BAD_KEY}) == 1
    assert "AIza" not in capsys.readouterr().out


@pytest.mark.parametrize("body", [b"<html>", b"[1, 2]", b"\xff\xfe"])
def test_an_unreadable_answer_is_reported(monkeypatch: pytest.MonkeyPatch, body: bytes) -> None:
    monkeypatch.setattr(urllib.request, "urlopen", lambda _request, timeout: FakeResponse(body))
    with pytest.raises(ck.KeyCheckError, match="unreadable"):
        ck.fetch_json(ck.GEMINI_MODELS_URL, GOOGLE)


# ------------------------------------------------------------------ the command line


def test_the_script_runs_end_to_end_without_keys(repo_root: Path, tmp_path: Path) -> None:
    env_file = tmp_path / ".env"
    env_file.write_text("COGNEE_ENABLED=false\n", encoding="utf-8")
    result = subprocess.run(  # noqa: S603 - fixed argv
        [sys.executable, str(repo_root / "scripts" / "check_keys.py"), "--env-file", str(env_file)],
        env={"PATH": "/usr/bin:/bin"},
        capture_output=True,
        text=True,
        timeout=30,
        check=False,
    )
    assert result.returncode == 0, result.stderr
    assert ai_not_set(result.stdout) == 2 and "TELEGRAM_BOT_TOKEN  NOT SET" in result.stdout
