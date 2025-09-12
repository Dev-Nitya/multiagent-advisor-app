import json
import os
from pathlib import Path
from typing import Optional

_DATA_DIR = Path(os.getenv("BACKEND_DATA_DIR", "backend/data"))
_DATA_DIR.mkdir(parents=True, exist_ok=True)
_APP_CONFIG = _DATA_DIR / "app_config.json"

_DEFAULTS = {"prompt_sanitization_enabled": True}


def _read_config() -> dict:
    try:
        if _APP_CONFIG.exists():
            with _APP_CONFIG.open("r", encoding="utf-8") as fh:
                return json.load(fh)
    except Exception:
        pass
    return dict(_DEFAULTS)


def _write_config(cfg: dict) -> None:
    tmp = _APP_CONFIG.with_suffix(".tmp")
    with tmp.open("w", encoding="utf-8") as fh:
        json.dump(cfg, fh)
    tmp.replace(_APP_CONFIG)


def is_prompt_sanitization_enabled() -> bool:
    cfg = _read_config()
    return bool(cfg.get("prompt_sanitization_enabled", _DEFAULTS["prompt_sanitization_enabled"]))


def set_prompt_sanitization_enabled(enabled: bool) -> None:
    cfg = _read_config()
    cfg["prompt_sanitization_enabled"] = bool(enabled)
    _write_config(cfg)