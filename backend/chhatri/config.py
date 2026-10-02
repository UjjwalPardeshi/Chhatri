"""Runtime settings (SPEC §0.1, §14, §21).

All secrets come from the environment (or a local .env). Nothing here is ever sent to the browser;
`Settings.public_summary()` is the only view that leaves the process.
"""

from __future__ import annotations

import secrets
from functools import lru_cache
from pathlib import Path

from pydantic import Field, SecretStr
from pydantic_settings import BaseSettings, SettingsConfigDict

BACKEND_DIR = Path(__file__).resolve().parent.parent
DATA_DIR = BACKEND_DIR / "data"
DEFAULT_VAR_DIR = BACKEND_DIR / "var"


def _has(value: SecretStr | str | None) -> bool:
    if value is None:
        return False
    raw = value.get_secret_value() if isinstance(value, SecretStr) else value
    return bool(raw.strip())


def _model_id(value: str) -> str:
    """A model id as the API names it: trimmed, without the `models/` prefix its own list puts in front."""
    return value.strip().removeprefix("models/").strip()


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=(".env", "../.env"),
        env_file_encoding="utf-8",
        extra="ignore",
        frozen=True,
    )

    # Core
    chhatri_seed: int = 20251019
    chhatri_var_dir: Path = DEFAULT_VAR_DIR
    chhatri_data_dir: Path = DATA_DIR
    chhatri_console_origin: str = "http://localhost:5173"
    chhatri_public_url: str = "http://localhost:8000"
    chhatri_officer_token: SecretStr = Field(default_factory=lambda: SecretStr(secrets.token_urlsafe(24)))
    chhatri_internal_secret: SecretStr = Field(default_factory=lambda: SecretStr(secrets.token_urlsafe(24)))
    chhatri_demo_mode: bool = True  # console receives the officer token automatically in demo mode
    chhatri_log_level: str = "INFO"
    # Feature flags (Wave 0): comma-separated names from chhatri.features.FEATURE_NAMES; empty = all off.
    chhatri_features: str = ""
    # X4: how long Chhatri waits for the lender's answer to an EDI holiday request, in seconds. One attempt, no
    # retry (fs-03 section 7.4); proposed 10 s, a target to tune. Simulated lender answers are instant.
    chhatri_lender_timeout_seconds: float = Field(default=10.0, gt=0)

    # Sarvam (SPEC §14.1)
    sarvam_api_key: SecretStr | None = None
    sarvam_chat_model: str = "sarvam-105b"
    sarvam_stt_model: str = "saaras:v3"
    sarvam_tts_model: str = "bulbul:v3"
    sarvam_tts_speaker: str = "ritu"

    # Gemini (Google AI Studio free tier; ADR 0003). A link is in a chain only with a key AND a model id. No model id
    # has a default: the free-tier ids change, so `make check-keys` lists the real ones and the environment names one.
    google_api_key: SecretStr | None = None
    gemini_model: str = ""  # text model; also reads slips unless GEMINI_VISION_MODEL names another
    gemini_vision_model: str = ""  # optional: a model that accepts images, for the slip reader
    # ADR 0009: free-tier AI links are called only when the deployment says its data is synthetic. Fails closed.
    chhatri_data_is_synthetic: bool = False

    # WhatsApp Cloud API (SPEC §14.2)
    whatsapp_access_token: SecretStr | None = None
    whatsapp_phone_number_id: str | None = None
    whatsapp_app_secret: SecretStr | None = None
    whatsapp_verify_token: SecretStr | None = None
    whatsapp_graph_version: str = "v25.0"
    whatsapp_template_language: str = "hi"
    whatsapp_demo_recipient: str | None = None  # E.164; live messages for demo merchants go here

    # Paytm payment link (SPEC §14.3)
    paytm_mcp_url: str | None = None  # e.g. http://localhost:8080/sse
    paytm_mid: str | None = None
    paytm_key_secret: SecretStr | None = None
    paytm_base_url: str = "https://securestage.paytmpayments.com"

    # n8n (SPEC §14.5)
    n8n_base_url: str | None = None

    # Memory (SPEC §14.6)
    cognee_enabled: bool = False

    # Open-Meteo (SPEC §14.4)
    openmeteo_live: bool = False

    @property
    def var_dir(self) -> Path:
        return self.chhatri_var_dir

    @property
    def sarvam_live(self) -> bool:
        return _has(self.sarvam_api_key)

    @property
    def gemini_key_set(self) -> bool:
        return _has(self.google_api_key)

    @property
    def gemini_chat_model_id(self) -> str:
        return _model_id(self.gemini_model)

    @property
    def gemini_vision_model_id(self) -> str:
        """The slip reader's model: GEMINI_VISION_MODEL, else the text model."""
        return _model_id(self.gemini_vision_model) or self.gemini_chat_model_id

    @property
    def gemini_chat_live(self) -> bool:
        return self.gemini_key_set and bool(self.gemini_chat_model_id)

    @property
    def gemini_vision_live(self) -> bool:
        return self.gemini_key_set and bool(self.gemini_vision_model_id)

    @property
    def whatsapp_live(self) -> bool:
        return all(
            _has(v)
            for v in (
                self.whatsapp_access_token,
                self.whatsapp_phone_number_id,
                self.whatsapp_app_secret,
                self.whatsapp_verify_token,
            )
        )

    @property
    def paytm_mode(self) -> str:
        """'mcp' | 'rest' | 'simulated'."""
        if _has(self.paytm_mcp_url):
            return "mcp"
        if _has(self.paytm_mid) and _has(self.paytm_key_secret):
            return "rest"
        return "simulated"

    @property
    def n8n_live(self) -> bool:
        return _has(self.n8n_base_url)

    def public_summary(self) -> dict[str, object]:
        """Non-secret view for /api/health and logs."""
        return {
            "seed": self.chhatri_seed,
            "demo_mode": self.chhatri_demo_mode,
            "sarvam_live": self.sarvam_live,
            "whatsapp_live": self.whatsapp_live,
            "paytm_mode": self.paytm_mode,
            "n8n_live": self.n8n_live,
            "cognee_enabled": self.cognee_enabled,
        }


@lru_cache(maxsize=1)
def get_settings() -> Settings:
    return Settings()
