"""The backend and the console must name the same feature flags, and `.env.example` must document them (Wave 0)."""

from __future__ import annotations

import re
from pathlib import Path

from chhatri.features import FEATURE_NAMES

FRONTEND_FLAGS = Path("frontend") / "src" / "features.ts"
FLAG_NAME = re.compile(r"[a-z][a-z0-9_]*")


def frontend_flag_names(repo_root: Path) -> list[str]:
    """The names in `export const FEATURE_NAMES = [...] as const` of frontend/src/features.ts, in order."""
    text = (repo_root / FRONTEND_FLAGS).read_text(encoding="utf-8")
    match = re.search(r"export const FEATURE_NAMES = \[(?P<body>.*?)\] as const", text, flags=re.DOTALL)
    assert match, f"{FRONTEND_FLAGS} must export `FEATURE_NAMES = [...] as const`"
    body = re.sub(r"//[^\n]*|/\*.*?\*/", "", match["body"], flags=re.DOTALL)
    return re.findall(r"'([^']+)'", body)


def test_backend_and_console_list_the_same_flags_in_the_same_order(repo_root: Path) -> None:
    frontend = frontend_flag_names(repo_root)
    backend = list(FEATURE_NAMES)
    assert frontend, "the console lists no flags"
    only_backend = sorted(set(backend) - set(frontend))
    only_frontend = sorted(set(frontend) - set(backend))
    assert not only_backend and not only_frontend, (
        f"flag lists differ: only in backend/chhatri/features.py {only_backend}, "
        f"only in {FRONTEND_FLAGS.as_posix()} {only_frontend}"
    )
    assert frontend == backend, "same flags, different order: keep the two lists identical"


def test_flag_names_are_unique_lower_snake_case(repo_root: Path) -> None:
    for names in (list(FEATURE_NAMES), frontend_flag_names(repo_root)):
        assert len(set(names)) == len(names)
        assert all(FLAG_NAME.fullmatch(name) for name in names)


def test_env_example_documents_both_settings_and_every_flag(repo_root: Path) -> None:
    example = (repo_root / ".env.example").read_text(encoding="utf-8")
    assert re.search(r"^# CHHATRI_FEATURES=$", example, flags=re.MULTILINE)
    assert re.search(r"^# VITE_FEATURES=", example, flags=re.MULTILINE)
    undocumented = [name for name in FEATURE_NAMES if not re.search(rf"\b{name}\b", example)]
    assert undocumented == [], f".env.example does not list {undocumented}"
