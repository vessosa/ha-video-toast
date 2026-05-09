import json
from pathlib import Path

CONFIG_DIR = Path.home() / ".ha-video-toast"
CONFIG_FILE = CONFIG_DIR / "config.json"

DEFAULTS = {
    "ha_url": "",
    "token": "",
    "toast": {
        "width": 400,
        "height": 225,
        "duration": 15,
        "gap": 10,
        "margin": 15,
        "max_toasts": 4,
        "taskbar_height": 48,
        "respect_dnd": True,
        "start_with_windows": False,
        "monitor_index": 0,
        "corner": "bottom-right",
    },
}


def load():
    if not CONFIG_FILE.exists():
        return {**DEFAULTS, "toast": {**DEFAULTS["toast"]}}
    try:
        with open(CONFIG_FILE, "r") as f:
            data = json.load(f)
        result = {**DEFAULTS, **data}
        result["toast"] = {**DEFAULTS["toast"], **data.get("toast", {})}
        return result
    except Exception:
        return {**DEFAULTS, "toast": {**DEFAULTS["toast"]}}


def save(config):
    CONFIG_DIR.mkdir(parents=True, exist_ok=True)
    with open(CONFIG_FILE, "w") as f:
        json.dump(config, f, indent=2)


def is_configured(config):
    return bool(config.get("ha_url") and config.get("token"))
