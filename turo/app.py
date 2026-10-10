"""Wiring: Qt app, overlay, Home window, task card, tray, settings and the ready-check status.
The tutor loop lives in tutor.py, spoken commands in commands.py, global keys in hotkeys.py."""
import json
import sys
import threading
import time
import urllib.request

from turo.ui import home
from turo.ui.card import GuideCard
from turo.ui.style import make_icon
from turo.ui.tray import Tray

if sys.stdout is None:   # started without a console (pythonw / desktop shortcut): log to a file
    home.DATA.mkdir(parents=True, exist_ok=True)
    sys.stdout = sys.stderr = open(home.DATA / "turo.log", "a", encoding="utf-8", buffering=1)

from PySide6.QtCore import QTimer
from PySide6.QtWidgets import QApplication

from turo import hotkeys, tutor
from turo.ai import memory, skills
from turo.config import AGENT_KEY, ASK_KEY, BASE_URL, MODEL, NEXT_KEY, WAKE_WORD
from turo.session import bridge, speak, voice
from turo.ui.overlay import Overlay

app = QApplication(sys.argv)
app.setQuitOnLastWindowClosed(False)
overlay = Overlay(level_fn=lambda: voice.level if voice else 0.0,
                  session_fn=lambda: bool(voice and voice.in_session()))

# --- settings and the ready check ----------------------------------------------------
settings = home.load_settings()
status = {"Local AI": (False, "checking…")}


def check_ai():
    while True:
        try:
            with urllib.request.urlopen(BASE_URL.replace("/v1", "/api/tags"), timeout=3) as r:
                names = [m["name"] for m in json.load(r).get("models", [])]
            status["Local AI"] = ((MODEL in names), MODEL + (" ready" if MODEL in names else " not downloaded"))
        except Exception:
            status["Local AI"] = (False, "Ollama isn't running: start it, then wait a moment")
        time.sleep(5)


def get_status():
    listening = bool(voice and settings.get("wake"))
    return {
        "Local AI": status["Local AI"],
        "Microphone": (voice is not None, "on" if voice else "not found: typing still works"),
        "Voice": (bool(speak) and settings.get("speak"),
                  (speak.engine_name if speak else "off") + ("" if settings.get("speak") else " (muted)")),
        "Listening": (listening, "say “Hey Turo”" if listening else "paused: press F9 to type"),
        "Memory": (True, f"{memory.count()} tasks learned on this laptop"),
    }


def apply_setting(key, value):
    settings[key] = value
    home.save_settings(settings)
    if key == "speak" and speak:
        speak.enabled = value
        if not value:
            speak.stop()
    elif key == "voice" and speak:
        speak.voice = value
        speak.speak("Hi, this is my new voice.")
    elif key == "buddy":
        overlay.show_idle = bool(value)
    elif key == "wake" and voice:
        voice.set_listening(value)
    tray.setToolTip("Turo: say “Hey Turo”" if settings.get("wake") else "Turo: listening paused (F9 to type)")


def toggle_listening():
    apply_setting("wake", not settings.get("wake"))


def quit_app():
    tray.hide()
    app.quit()


# --- Home window and tray ------------------------------------------------------------
skill_list = [(body.splitlines()[0].replace("SKILL:", "").split("(")[0].split(".")[0].strip(), words)
              for _name, words, body in skills.SKILLS]
win = home.Home(settings, skill_list, get_status, speak.VOICES if speak else {})
win.ask.connect(tutor.on_home_ask)
win.setting_changed.connect(apply_setting)
overlay.show_idle = bool(settings.get("buddy", True))


def on_hidden_to_tray():
    """First time the window is closed, say where Turo went (the buddy stays, so it looked like a bug)."""
    if not settings.get("tray_hint_shown"):
        tray.showMessage("Turo is still running",
                         "It keeps listening for “Hey Turo”. Right-click the tray icon to quit, "
                         "or turn off the cursor buddy in Settings.", make_icon(), 6000)
        apply_setting("tray_hint_shown", True)


win.hidden_to_tray.connect(on_hidden_to_tray)
tray = Tray(win, lambda: (tutor.track_app(), win.open_ask()), toggle_listening, quit_app)
app.setWindowIcon(make_icon())
if speak:
    speak.enabled, speak.voice = settings.get("speak", True), settings.get("voice", "af_heart")
threading.Thread(target=check_ai, daemon=True).start()
app_timer = QTimer()
app_timer.timeout.connect(tutor.track_app)
app_timer.start(500)

# --- signals from worker threads -> Qt thread ------------------------------------------
bridge.ask.connect(win.open_ask)
bridge.show.connect(overlay.point_at)
bridge.mode.connect(overlay.set_mode)
bridge.clear.connect(overlay.clear)
bridge.copy.connect(lambda text: app.clipboard().setText(text))
card = GuideCard()
card.next_clicked.connect(lambda: tutor.start_step())
card.do_clicked.connect(tutor.start_agent)
card.stop_clicked.connect(tutor.stop_all)


def on_card(op, text):
    if op == "start":
        card.start(text)
    elif op == "step":
        card.add_step(text)
    elif op == "thinking":
        card.thinking()
    elif op == "finish":
        card.finish()
    elif op == "hide":
        card.hide()
    elif op in ("capture", "restore"):
        card.setWindowOpacity(0.0 if op == "capture" else 1.0)


bridge.card.connect(on_card)


def run():
    """Register hotkeys, start listening, show Home (or the tour on first run), and run the Qt loop."""
    hotkeys.register(settings.get("wake", True))
    print(f"Turo ready. Say \"Hey Turo\"{'' if voice and WAKE_WORD else ' (off)'}, hold Win+Alt to talk, "
          f"{ASK_KEY.upper()} type, {NEXT_KEY.upper()} next, {AGENT_KEY.upper()} do it for me, Esc stop.")
    if settings.get("onboarded"):
        win.show_front()
    else:
        win.show_tour()   # first run: the tour
    sys.exit(app.exec())
