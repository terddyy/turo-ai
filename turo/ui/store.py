"""What Turo saves on this laptop (in %APPDATA%\\Turo): settings and the question history."""
import json
import time

from turo.config import DATA

SETTINGS_FILE = DATA / "settings.json"
HISTORY_FILE = DATA / "history.json"
DEFAULTS = {"onboarded": False, "wake": True, "speak": True, "voice": "af_heart", "buddy": True,
            "tray_hint_shown": False}


def load_settings():
    try:
        return {**DEFAULTS, **json.loads(SETTINGS_FILE.read_text(encoding="utf-8"))}
    except (OSError, ValueError):
        return dict(DEFAULTS)


def save_settings(settings):
    DATA.mkdir(parents=True, exist_ok=True)
    SETTINGS_FILE.write_text(json.dumps(settings, indent=2), encoding="utf-8")


def load_history():
    try:
        return json.loads(HISTORY_FILE.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return []


def add_history(question, app):
    items = [h for h in load_history() if h.get("q") != question][:49]
    items.insert(0, {"q": question, "app": app, "t": time.strftime("%b %d, %I:%M %p")})
    DATA.mkdir(parents=True, exist_ok=True)
    HISTORY_FILE.write_text(json.dumps(items, indent=2), encoding="utf-8")
