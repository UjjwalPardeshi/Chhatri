"""`make env`: .env from .env.example with generated secrets, never overwriting (SPEC §21)."""

from __future__ import annotations

import stat
from pathlib import Path

import init_env


def test_render_fills_only_empty_generated_keys() -> None:
    lines = [
        "A=1\n",
        "CHHATRI_INTERNAL_SECRET=\n",
        "N8N_ENCRYPTION_KEY=keep",
        "# CHHATRI_INTERNAL_SECRET=\n",
    ]
    text = init_env.render_env(lines, {"CHHATRI_INTERNAL_SECRET": "T1", "N8N_ENCRYPTION_KEY": "T2"})
    assert text == "A=1\nCHHATRI_INTERNAL_SECRET=T1\nN8N_ENCRYPTION_KEY=keep\n# CHHATRI_INTERNAL_SECRET=\n"


def test_read_values_ignores_comments_and_quotes() -> None:
    assert init_env.read_values("# X=1\nX='2'\n  Y=\"3\" \nnot a line\n") == {
        "X": "2",
        "Y": "3",
    }


def test_creates_private_env_from_the_real_example(repo_root: Path, tmp_path: Path) -> None:
    target = tmp_path / ".env"
    assert init_env.main(["--example", str(repo_root / ".env.example"), "--target", str(target)]) == 0
    values = init_env.read_values(target.read_text(encoding="utf-8"))
    assert len(values["CHHATRI_INTERNAL_SECRET"]) >= 40 and len(values["N8N_ENCRYPTION_KEY"]) >= 40
    assert values["CHHATRI_INTERNAL_SECRET"] != values["N8N_ENCRYPTION_KEY"]
    assert stat.S_IMODE(target.stat().st_mode) == 0o600
    before = target.read_text(encoding="utf-8")
    assert init_env.main(["--example", str(repo_root / ".env.example"), "--target", str(target)]) == 0
    assert target.read_text(encoding="utf-8") == before


def test_existing_env_without_secret_fails(tmp_path: Path) -> None:
    target = tmp_path / ".env"
    target.write_text("CHHATRI_INTERNAL_SECRET=\n", encoding="utf-8")
    assert init_env.main(["--target", str(target)]) == 1
    assert target.read_text(encoding="utf-8") == "CHHATRI_INTERNAL_SECRET=\n"


def test_example_without_secret_line_writes_nothing(tmp_path: Path) -> None:
    example = tmp_path / "example"
    example.write_text("A=1\n", encoding="utf-8")
    target = tmp_path / ".env"
    assert init_env.main(["--example", str(example), "--target", str(target)]) == 1
    assert not target.exists()


def test_unwritable_target_is_reported(tmp_path: Path, repo_root: Path) -> None:
    target = tmp_path / "missing-dir" / ".env"
    assert init_env.main(["--example", str(repo_root / ".env.example"), "--target", str(target)]) == 1
