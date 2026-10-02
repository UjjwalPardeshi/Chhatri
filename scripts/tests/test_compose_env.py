# ruff: noqa: S105, S106, S310 - test fixtures: dummy secrets, local http:// URLs (same policy as backend tests/)
"""docker-compose.yml and .env.example against Settings (SPEC §0.1, §21, §23; decisions B1, B6, B8)."""

from __future__ import annotations

import json
import re
import shutil
import subprocess
from pathlib import Path
from typing import Any

import pytest
import yaml
from chhatri.config import Settings

DOCKER = shutil.which("docker") or "docker"
FIXED_IN_CONTAINER = {
    "CHHATRI_DATA_DIR": "/app/data",
    "CHHATRI_VAR_DIR": "/app/var",
    "CHHATRI_PUBLIC_URL": "http://backend:8000",
}
SECRET_FIELDS = {name.upper() for name, f in Settings.model_fields.items() if "Secret" in str(f.annotation)}


def _settings_env_names() -> set[str]:
    return {name.upper() for name in Settings.model_fields}


def _compose(repo_root: Path) -> dict[str, Any]:
    return yaml.safe_load((repo_root / "docker-compose.yml").read_text(encoding="utf-8"))


def _config(repo_root: Path, env_file: Path) -> subprocess.CompletedProcess[str]:
    return subprocess.run(  # noqa: S603 - fixed argv
        [DOCKER, "compose", "--env-file", str(env_file), "config", "--format", "json"],
        cwd=repo_root,
        capture_output=True,
        text=True,
        timeout=60,
        check=False,
    )


def test_env_example_lists_every_settings_field_without_secrets(
    repo_root: Path,
) -> None:
    text = (repo_root / ".env.example").read_text(encoding="utf-8")
    listed = set(re.findall(r"^(?:# )?([A-Z][A-Z0-9_]*)=", text, flags=re.M))
    assert _settings_env_names() <= listed
    active = dict(re.findall(r"^([A-Z][A-Z0-9_]*)=(.*)$", text, flags=re.M))
    for name in SECRET_FIELDS | {
        "N8N_ENCRYPTION_KEY",
        "WHATSAPP_DEMO_RECIPIENT",
        "PAYTM_MID",
    }:
        assert active.get(name, "") == "", f"{name} must not carry a value in .env.example"


def test_compose_passes_every_setting_to_the_backend(repo_root: Path) -> None:
    env = _compose(repo_root)["services"]["backend"]["environment"]
    assert _settings_env_names() <= set(env)
    for name, value in FIXED_IN_CONTAINER.items():
        assert env[name] == value
    assert env["N8N_BASE_URL"] == "${CHHATRI_STACK_N8N_URL-http://n8n:5678}"
    optional = [n for n in _settings_env_names() if n not in FIXED_IN_CONTAINER and n != "N8N_BASE_URL"]
    for name in optional:
        value = env[name]
        assert value is None or str(value).startswith("${"), f"{name} must come from .env/shell"


def test_compose_services_ports_and_n8n(repo_root: Path) -> None:
    services = _compose(repo_root)["services"]
    assert sorted(services) == ["backend", "frontend", "n8n"]
    ports = {name: svc["ports"][0] for name, svc in services.items()}
    assert ports == {
        "backend": "${CHHATRI_BIND_ADDR:-127.0.0.1}:${CHHATRI_BACKEND_PORT:-8000}:8000",
        "frontend": "${CHHATRI_BIND_ADDR:-127.0.0.1}:${CHHATRI_CONSOLE_PORT:-8080}:8080",
        "n8n": "${CHHATRI_BIND_ADDR:-127.0.0.1}:${CHHATRI_N8N_PORT:-5678}:5678",
    }
    n8n = services["n8n"]
    assert re.fullmatch(r"docker\.n8n\.io/n8nio/n8n:2\.\d+\.\d+", n8n["image"])
    assert n8n["entrypoint"] == ["/bin/sh", "/chhatri/entrypoint.sh"]
    assert "./n8n/workflows:/chhatri/workflows:ro" in n8n["volumes"]
    assert "./n8n/entrypoint.sh:/chhatri/entrypoint.sh:ro" in n8n["volumes"]
    assert n8n["environment"]["N8N_BLOCK_ENV_ACCESS_IN_NODE"] == "false"
    assert n8n["environment"]["CHHATRI_PUBLIC_URL"] == "http://backend:8000"
    backend_health = " ".join(services["backend"]["healthcheck"]["test"])
    assert "urllib.request" in backend_health and "requests" not in backend_health.replace(
        "urllib.request", ""
    )
    assert services["frontend"]["depends_on"]["backend"]["condition"] == "service_healthy"


def test_console_build_arguments_are_documented(repo_root: Path) -> None:
    """VITE_TILE_URL (a keyed tile URL, SPEC §20) and VITE_FEATURES (Wave 0 flags) reach the frontend build."""
    build = _compose(repo_root)["services"]["frontend"]["build"]
    assert build["args"] == {
        "VITE_TILE_URL": "${VITE_TILE_URL:-}",
        "VITE_FEATURES": "${VITE_FEATURES:-${CHHATRI_FEATURES:-}}",
    }
    example = (repo_root / ".env.example").read_text(encoding="utf-8")
    assert re.search(r"^# VITE_TILE_URL=$", example, re.M)
    assert re.search(r"^# VITE_FEATURES=", example, re.M)
    assert re.search(r"^# CHHATRI_FEATURES=$", example, re.M)


def _resolved(repo_root: Path, tmp_path: Path, extra: str) -> dict[str, Any]:
    env_file = tmp_path / "features.env"
    env_file.write_text(f"CHHATRI_INTERNAL_SECRET=abc123\n{extra}", encoding="utf-8")
    result = _config(repo_root, env_file)
    assert result.returncode == 0, result.stderr
    doc: dict[str, Any] = json.loads(result.stdout)
    return doc


def test_one_features_setting_turns_flags_on_in_the_backend_and_the_console_build(
    repo_root: Path, tmp_path: Path
) -> None:
    doc = _resolved(repo_root, tmp_path, "CHHATRI_FEATURES=n1_miniapp,n2_ask_chhatri\n")
    assert doc["services"]["backend"]["environment"]["CHHATRI_FEATURES"] == "n1_miniapp,n2_ask_chhatri"
    assert doc["services"]["frontend"]["build"]["args"]["VITE_FEATURES"] == "n1_miniapp,n2_ask_chhatri"


def test_the_console_flags_can_differ_from_the_backend_flags(repo_root: Path, tmp_path: Path) -> None:
    doc = _resolved(repo_root, tmp_path, "CHHATRI_FEATURES=n1_miniapp\nVITE_FEATURES=console_polish\n")
    assert doc["services"]["backend"]["environment"]["CHHATRI_FEATURES"] == "n1_miniapp"
    assert doc["services"]["frontend"]["build"]["args"]["VITE_FEATURES"] == "console_polish"


def test_every_flag_is_off_when_nothing_is_set(repo_root: Path, tmp_path: Path) -> None:
    doc = _resolved(repo_root, tmp_path, "")
    assert doc["services"]["backend"]["environment"].get("CHHATRI_FEATURES") is None  # passed only when set
    assert doc["services"]["frontend"]["build"]["args"]["VITE_FEATURES"] == ""


AI_SETTINGS = ("GOOGLE_API_KEY", "GEMINI_MODEL", "GEMINI_VISION_MODEL", "CHHATRI_DATA_IS_SYNTHETIC")


def test_env_example_documents_gemini_and_declares_the_prototype_data_synthetic(repo_root: Path) -> None:
    """Card 4.1: Gemini needs a key AND a model id (none has a default), and ADR 0009's gate is open in the example."""
    text = (repo_root / ".env.example").read_text(encoding="utf-8")
    for name in ("GOOGLE_API_KEY", "GEMINI_MODEL", "GEMINI_VISION_MODEL"):
        assert re.search(rf"^# {name}=$", text, flags=re.M), f"{name} must be a commented line with no value"
    assert re.search(r"^CHHATRI_DATA_IS_SYNTHETIC=true$", text, flags=re.M)
    assert not re.search(r"gemini-\d", text, flags=re.I), (
        "no document names a Gemini model: the free-tier ids change"
    )


def test_a_make_env_file_opens_the_gate_and_leaves_gemini_waiting_for_a_key(
    repo_root: Path, tmp_path: Path
) -> None:
    import init_env

    target = tmp_path / ".env"
    assert init_env.main(["--example", str(repo_root / ".env.example"), "--target", str(target)]) == 0
    settings = Settings(_env_file=target)  # type: ignore[call-arg]
    assert settings.chhatri_data_is_synthetic is True
    assert settings.google_api_key is None and settings.gemini_model == ""
    assert not settings.gemini_chat_live and not settings.gemini_vision_live


def test_compose_passes_the_ai_settings_only_when_they_are_set(repo_root: Path, tmp_path: Path) -> None:
    env = _resolved(repo_root, tmp_path, "")["services"]["backend"]["environment"]
    assert all(env.get(name) is None for name in AI_SETTINGS)  # never an empty string: unset stays unset
    values = "GOOGLE_API_KEY=k1\nGEMINI_MODEL=m1\nGEMINI_VISION_MODEL=m2\nCHHATRI_DATA_IS_SYNTHETIC=true\n"
    env = _resolved(repo_root, tmp_path, values)["services"]["backend"]["environment"]
    assert [env[name] for name in AI_SETTINGS] == ["k1", "m1", "m2", "true"]


def test_compose_config_validates_and_resolves(repo_root: Path, tmp_path: Path) -> None:
    env_file = tmp_path / "stack.env"
    env_file.write_text(
        "CHHATRI_INTERNAL_SECRET=abc123\nCHHATRI_OFFICER_TOKEN=tok\nCHHATRI_CONSOLE_PORT=18080\n"
        "CHHATRI_STACK_N8N_URL=\n",
        encoding="utf-8",
    )
    result = _config(repo_root, env_file)
    assert result.returncode == 0, result.stderr
    doc = json.loads(result.stdout)
    backend = doc["services"]["backend"]["environment"]
    assert (
        backend["CHHATRI_INTERNAL_SECRET"] == doc["services"]["n8n"]["environment"]["CHHATRI_INTERNAL_SECRET"]
    )
    assert backend["CHHATRI_OFFICER_TOKEN"] == "tok"
    assert backend["N8N_BASE_URL"] == ""
    assert backend["CHHATRI_CONSOLE_ORIGIN"] == "http://localhost:18080"  # follows CHHATRI_CONSOLE_PORT
    assert "SARVAM_API_KEY" not in backend or backend["SARVAM_API_KEY"] is None
    published = {name: svc["ports"][0]["published"] for name, svc in doc["services"].items()}
    assert published == {"backend": "8000", "frontend": "18080", "n8n": "5678"}
    assert all(svc["ports"][0]["host_ip"] == "127.0.0.1" for svc in doc["services"].values())


def test_compose_refuses_to_start_without_the_internal_secret(repo_root: Path, tmp_path: Path) -> None:
    env_file = tmp_path / "empty.env"
    env_file.write_text("CHHATRI_INTERNAL_SECRET=\n", encoding="utf-8")
    result = _config(repo_root, env_file)
    assert result.returncode != 0
    assert "CHHATRI_INTERNAL_SECRET" in result.stderr


@pytest.mark.parametrize(
    "line",
    [
        ".env",
        ".env.*",
        "!.env.example",
        "!frontend/.env.mock",
        "backend/var/",
        "frontend/node_modules/",
    ],
)
def test_gitignore_keeps_secrets_and_run_state_out(repo_root: Path, line: str) -> None:
    assert line in (repo_root / ".gitignore").read_text(encoding="utf-8").splitlines()
