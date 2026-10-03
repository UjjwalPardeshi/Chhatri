#!/usr/bin/env python3
"""Report whether the AI provider keys are set, without ever printing them (`make check-keys`).

Reads SARVAM_API_KEY and GOOGLE_API_KEY from the process environment, falling back to the repo's `.env`
(the file the backend reads; the environment wins, as in pydantic-settings), and prints each as `SET` or
`NOT SET`. TELEGRAM_BOT_TOKEN is reported the same way; it is optional, so NOT SET is never a failure, even with --strict.
When it is set the bot is asked who it is (`getMe`, free, sends nothing) and its username is printed; the token is not. When GOOGLE_API_KEY is set it also lists the Gemini models that key can call, through the free
models-list endpoint (`GET /v1beta/models`): no generation call is made, so no quota or content is used.
The key travels in the `x-goog-api-key` header, never in a URL. The output never contains a key, a prefix,
a length or a raw provider answer.

    python3 scripts/check_keys.py [--env-file PATH] [--strict]

Exit status 0 when every check ran; 1 when a key is set but the model list could not be read (a rejected
key, no network) and, with --strict, also when a key is NOT SET (the app falls back to its simulators
without keys, so NOT SET is only a failure when you ask for it). Stdlib only, so it runs before
`make setup`.
"""

from __future__ import annotations

import argparse
import http.client
import json
import os
import re
import sys
import urllib.error
import urllib.parse
import urllib.request
from collections.abc import Callable, Mapping, Sequence
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Final

import init_env

REPO_ROOT: Final = Path(__file__).resolve().parent.parent
SARVAM_KEY: Final = "SARVAM_API_KEY"
GOOGLE_KEY: Final = "GOOGLE_API_KEY"
TELEGRAM_KEY: Final = "TELEGRAM_BOT_TOKEN"
KEY_NAMES: Final = (SARVAM_KEY, GOOGLE_KEY)
OPTIONAL_KEY_NAMES: Final = (
    TELEGRAM_KEY,
)  # reported, never required: the bot is simulated without its token
TELEGRAM_API: Final = "https://api.telegram.org"
GEMINI_MODELS_URL: Final = "https://generativelanguage.googleapis.com/v1beta/models"
API_KEY_HEADER: Final = "x-goog-api-key"
GENERATE_METHOD: Final = "generateContent"
MODEL_PREFIX: Final = "models/"
PAGE_SIZE: Final = 100
MAX_PAGES: Final = 20
TIMEOUT_S: Final = 15.0
STATUS_WORD: Final = re.compile(r"^[A-Z_]{3,40}$")
LABEL_WIDTH: Final = max(len(name) for name in (*KEY_NAMES, *OPTIONAL_KEY_NAMES))

Fetcher = Callable[[str, str], Mapping[str, Any]]
"""`(url, api_key) -> parsed JSON object`; raises `KeyCheckError` with a message that is safe to print."""
TelegramFetcher = Callable[[str], Mapping[str, Any]]
"""`token -> getMe answer`; raises `KeyCheckError` with a message that is safe to print (never the token)."""


class KeyCheckError(RuntimeError):
    """A failure whose message is safe to print: no key, no response text."""


@dataclass(frozen=True, slots=True)
class GeminiModel:
    name: str
    display_name: str


def read_dotenv(path: Path) -> dict[str, str]:
    """Active `KEY=value` lines of `path`; a missing file is an empty result, other read errors propagate."""
    try:
        return init_env.read_values(path.read_text(encoding="utf-8"))
    except FileNotFoundError:
        return {}


def key_value(name: str, environ: Mapping[str, str], dotenv: Mapping[str, str]) -> str:
    """The value of `name`: the environment wins over `.env`, even when empty (as pydantic-settings does)."""
    return environ[name] if name in environ else dotenv.get(name, "")


def is_set(value: str) -> bool:
    return bool(value.strip())


def _error_status(exc: urllib.error.HTTPError) -> str:
    """The `error.status` enum word of a Google error body ("INVALID_ARGUMENT"), or "" when absent or odd."""
    try:
        parsed = json.loads(exc.read())
    except (OSError, ValueError):
        return ""
    error = parsed.get("error") if isinstance(parsed, dict) else None
    status = error.get("status") if isinstance(error, dict) else None
    return status if isinstance(status, str) and STATUS_WORD.fullmatch(status) else ""


def fetch_json(url: str, api_key: str, timeout: float = TIMEOUT_S) -> Mapping[str, Any]:
    """GET `url` with the key in a header and return the JSON object; only safe messages are raised."""
    if not url.startswith("https://"):
        raise KeyCheckError("refusing to send a key over a non-https URL")
    request = urllib.request.Request(url, headers={API_KEY_HEADER: api_key, "Accept": "application/json"})  # noqa: S310 - https only, checked above
    try:
        with urllib.request.urlopen(request, timeout=timeout) as response:  # noqa: S310 - https only, checked above
            body = response.read()
    except urllib.error.HTTPError as exc:
        raise KeyCheckError(f"HTTP {exc.code} {_error_status(exc)}".strip()) from None
    except (OSError, http.client.HTTPException) as exc:
        raise KeyCheckError(f"network error ({type(exc).__name__})") from None
    except ValueError:
        # http.client quotes an illegal header value in its message, which would print the key itself
        raise KeyCheckError("the key cannot be sent in a header (stray line break or non-ASCII?)") from None
    try:
        parsed = json.loads(body)
    except ValueError:
        raise KeyCheckError("unreadable response (not JSON)") from None
    if not isinstance(parsed, dict):
        raise KeyCheckError("unreadable response (not a JSON object)")
    return parsed


def fetch_telegram_me(token: str, timeout: float = TIMEOUT_S) -> Mapping[str, Any]:
    """`getMe` for `token`: the bot's own answer. The token is in the URL path, so no URL or body is ever raised or printed."""
    request = urllib.request.Request(  # noqa: S310 - the https Bot API host is a constant
        f"{TELEGRAM_API}/bot{token}/getMe", headers={"Accept": "application/json"}
    )
    try:
        with urllib.request.urlopen(request, timeout=timeout) as response:  # noqa: S310 - https constant above
            body = response.read()
    except urllib.error.HTTPError as exc:
        raise KeyCheckError(f"HTTP {exc.code}") from None
    except (OSError, http.client.HTTPException) as exc:
        raise KeyCheckError(f"network error ({type(exc).__name__})") from None
    except ValueError:
        raise KeyCheckError("the token cannot be used in a URL (stray space or line break?)") from None
    try:
        parsed = json.loads(body)
    except ValueError:
        raise KeyCheckError("unreadable response (not JSON)") from None
    if not isinstance(parsed, dict):
        raise KeyCheckError("unreadable response (not a JSON object)")
    return parsed


def _report_telegram(token: str, fetch: TelegramFetcher) -> bool:
    """Print the bot's username (never the token); False when `getMe` failed."""
    try:
        answer = fetch(token)
    except KeyCheckError as exc:
        print(f"{TELEGRAM_KEY}: getMe failed ({exc})")
        return False
    result = answer.get("result")
    username = result.get("username") if isinstance(result, dict) else None
    if answer.get("ok") is not True or not isinstance(username, str) or not username:
        print(f"{TELEGRAM_KEY}: getMe did not name a bot (is the token right?)")
        return False
    print(f"Telegram bot: @{username}  (deep link: https://t.me/{username}?start=S-0142)")
    return True


def _page_url(page_token: str | None) -> str:
    query = f"pageSize={PAGE_SIZE}"
    if page_token:
        query += f"&pageToken={urllib.parse.quote(page_token, safe='')}"
    return f"{GEMINI_MODELS_URL}?{query}"


def _entry_of(item: object) -> tuple[GeminiModel, bool] | None:
    """`(model, can_generate)` for a well-formed entry of the list; None for anything else."""
    if not isinstance(item, dict) or not isinstance(name := item.get("name"), str):
        return None
    display = item.get("displayName")
    methods = item.get("supportedGenerationMethods")
    model = GeminiModel(name.removeprefix(MODEL_PREFIX), display if isinstance(display, str) else "")
    return model, isinstance(methods, list) and GENERATE_METHOD in methods


def list_gemini_models(api_key: str, fetch: Fetcher = fetch_json) -> tuple[list[GeminiModel], int]:
    """Models the key can call with `generateContent`, sorted by id, and how many models it can see in all.

    Reads the free models-list endpoint page by page (at most MAX_PAGES, so a bad token loop ends).
    """
    models: list[GeminiModel] = []
    total = 0
    page_token: str | None = None
    for _ in range(MAX_PAGES):
        payload = fetch(_page_url(page_token), api_key)
        items = payload.get("models")
        for item in items if isinstance(items, list) else []:
            if (entry := _entry_of(item)) is not None:
                total += 1
                if entry[1]:
                    models.append(entry[0])
        token = payload.get("nextPageToken")
        page_token = token if isinstance(token, str) and token else None
        if page_token is None:
            break
    return sorted(models, key=lambda model: model.name), total


def _report_models(api_key: str, fetch: Fetcher) -> bool:
    """Print the Gemini model list; False when it could not be read."""
    try:
        models, total = list_gemini_models(api_key, fetch)
    except KeyCheckError as exc:
        print(f"{GOOGLE_KEY}: the Gemini model list could not be read ({exc})")
        return False
    if not models:
        print(f"Gemini: no model supports {GENERATE_METHOD} for this key (it sees {total}).")
        return True
    print(f"Gemini models this key can call ({GENERATE_METHOD}), {len(models)} of {total}:")
    width = max(len(model.name) for model in models)
    for model in models:
        print(f"  {model.name:<{width}}  {model.display_name}".rstrip())
    return True


def _load_dotenv(path: Path) -> dict[str, str]:
    try:
        return read_dotenv(path)
    except OSError as exc:
        print(
            f"note: could not read {path} ({exc.strerror or type(exc).__name__}); using the environment only"
        )
        return {}


def main(
    argv: Sequence[str] | None = None,
    *,
    environ: Mapping[str, str] | None = None,
    fetch: Fetcher = fetch_json,
    telegram_fetch: TelegramFetcher = fetch_telegram_me,
) -> int:
    parser = argparse.ArgumentParser(
        description="Report SARVAM_API_KEY, GOOGLE_API_KEY and TELEGRAM_BOT_TOKEN as SET or NOT SET"
    )
    parser.add_argument("--env-file", type=Path, default=REPO_ROOT / ".env", help="default: the repo's .env")
    parser.add_argument("--strict", action="store_true", help="exit 1 when a key is NOT SET")
    args = parser.parse_args(argv)
    env = os.environ if environ is None else environ
    dotenv = _load_dotenv(args.env_file)
    values = {name: key_value(name, env, dotenv) for name in (*KEY_NAMES, *OPTIONAL_KEY_NAMES)}
    for name in (*KEY_NAMES, *OPTIONAL_KEY_NAMES):
        print(f"{name:<{LABEL_WIDTH}}  {'SET' if is_set(values[name]) else 'NOT SET'}")
    failed = False
    if is_set(values[GOOGLE_KEY]):
        failed = not _report_models(values[GOOGLE_KEY].strip(), fetch)
    if is_set(values[TELEGRAM_KEY]):
        failed = not _report_telegram(values[TELEGRAM_KEY].strip(), telegram_fetch) or failed
    missing = not all(is_set(values[name]) for name in KEY_NAMES)
    return 1 if failed or (args.strict and missing) else 0


if __name__ == "__main__":
    sys.exit(main())
