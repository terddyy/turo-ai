import ctypes
import ctypes.wintypes
import json
import os
import re
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

import keyboard
import uiautomation as auto
from PySide6.QtCore import QObject, QTimer, Signal
from PySide6.QtWidgets import QApplication

from turo.ai import brain, memory, skills
from turo.sense import screen
from turo.config import AGENT_KEY, ASK_KEY, BASE_URL, CLOUD_KEY, MAX_AGENT_STEPS, MODEL, NEXT_KEY, WAKE_WORD
from turo.ui.overlay import Overlay

try:
    from turo.voice import speak
except Exception as err:   # no SAPI voice: run silent
    print("Spoken reply off:", err)
    speak = None

try:
    from turo.voice import listen as voice
except Exception as err:   # no mic or model: typing still works
    print("Voice input off:", err)
    voice = None


class Bridge(QObject):
    ask = Signal()                # hotkey thread -> Qt thread
    show = Signal(object, str)    # worker thread -> Qt thread
    mode = Signal(str)            # listening / thinking / done / reset
    copy = Signal(str)            # example prompt -> clipboard (Qt thread only)
    card = Signal(str, str)       # task card: start / step / thinking / finish / hide / capture / restore
    clear = Signal()


app = QApplication(sys.argv)
app.setQuitOnLastWindowClosed(False)
overlay = Overlay(level_fn=lambda: voice.level if voice else 0.0,
                  session_fn=lambda: bool(voice and voice.in_session()))
bridge = Bridge()
state = {"hwnd": None, "question": "", "context": "", "history": [], "gen": 0, "stop": False,
         "app": "", "path": [], "recalled": None,
         "talking": False, "last": None}
busy = threading.Lock()   # one model call at a time
user32 = ctypes.windll.user32
RISKY = ("delete", "remove", "send", "pay", "buy", "format", "sign out", "shut down", "uninstall")

# Spoken commands. Matched only when the whole phrase is the command, so questions never trigger them.
COMMANDS = {
    "next": ("next", "next step", "continue", "go on", "done", "what's next", "and then", "what now"),
    "stop": ("stop", "cancel", "never mind", "nevermind", "quit", "that's enough", "close"),
    "repeat": ("repeat", "say again", "say that again", "come again", "repeat that"),
    "agent": ("do it", "do it for me", "you do it", "just do it", "go ahead", "do it yourself"),
}


def say_and_show(rect, text, spoken=None):
    state["last"] = (rect, text)
    bridge.show.emit(rect, text)
    if speak:
        speak.speak(spoken or text)   # queued: a step never cuts off the one before it (Esc / stop / new question do)


def compute_step(use_cloud=False):
    """One look at the screen. Caller holds the UIA initializer.
    Returns {action: click/type/explain, rect, say, text, done, label}.
    Vision first: the model reads a screenshot and decides. UI Automation only sharpens the box."""
    title, items = screen.list_controls(state["hwnd"])
    exe = screen.exe_of(state["hwnd"])
    skill = skills.for_app(title, exe)
    state["app"] = exe.lower()
    if state["recalled"] == "unset":   # first look at this question: anything similar done before here?
        state["recalled"] = memory.recall(state["app"], state["question"])
    known = state["recalled"] or []
    for n in range(len(known) - 1, -1, -1) if not use_cloud else ():
        if known[n] in state["path"]:   # this and everything before it is already done
            break
        hit = screen.find_named(known[n], items)
        if hit:   # the furthest remembered step on screen: replay it, no screenshot or model call
            print(f"[memory] step: {known[n]}")
            return {"action": "click", "rect": hit["rect"], "say": f"Click {hit['name']}.", "text": "",
                    "done": n == len(known) - 1, "label": hit["name"]}
    bridge.mode.emit("capture")   # Turo's ring, label and card must not be in its own screenshot
    bridge.card.emit("capture", "")
    time.sleep(0.15)
    try:
        image, (ml, mt, mw, mh) = screen.grab(state["hwnd"])
    finally:
        bridge.mode.emit("thinking")
        bridge.card.emit("restore", "")
    seen = brain.locate(state["question"], title, image, state["history"], use_cloud=use_cloud, skill=skill,
                        context=state["context"], memory=" > ".join(known))
    step = {"action": seen["action"], "rect": None, "say": seen["say"], "text": seen["text"],
            "done": seen["done"], "label": seen["label"]}
    if seen["action"] == "explain":   # an answer, not a click: no box
        step["done"] = True
        return step
    if seen["point"]:
        x, y = ml + seen["point"][0] * mw / 1000, mt + seen["point"][1] * mh / 1000
        step["rect"], name = screen.snap(x, y, seen["label"], items, action=seen["action"])
        step["label"] = name or seen["label"]
        return step
    # The model saw nothing to click: fall back to reasoning over the control names.
    reply = brain.next_step(state["question"], title, items, state["history"], use_cloud=use_cloud, skill=skill)
    hit = next((i for i in items if i["id"] == reply["id"]), None)
    if hit:
        step.update(action="click", rect=hit["rect"], say=reply["say"], done=reply["done"], label=hit["name"])
    return step


def present(step, prefix=""):
    """Show and speak one step. For typing steps, the example goes to the clipboard."""
    say = prefix + step["say"]
    full = say
    if step["action"] == "type" and step["text"]:
        bridge.copy.emit(step["text"])
        full = f'{say}  Try: "{step["text"]}" (copied: press Ctrl+V)'
    if step["rect"]:   # on screen only a short label; the card holds the full instruction
        short = "Type here, then Ctrl+V" if step["action"] == "type" else f'Click {step["label"] or "here"}'
        say_and_show(step["rect"], short[:48], spoken=say)
    else:
        say_and_show(None, say)
    bridge.card.emit("step", full)
    state["history"].append(say)
    if step["rect"] and step["label"]:
        state["path"].append(screen.clean_label(step["label"]))


def learn():
    """The task finished: remember the click path for next time."""
    memory.remember(state["app"], state["question"], state["path"])


def finish(gen):
    learn()
    say_and_show(None, "All done! 🎉 Anything else?")
    bridge.card.emit("finish", "")
    bridge.mode.emit("done")
    open_follow_up()
    time.sleep(3)
    if state["gen"] == gen:
        bridge.clear.emit()


def watch(rect, done, gen, key):
    """Auto-advance. key 0x01: a click inside the highlighted box. key 0x0D: Enter (sent a typed prompt)."""
    left, top, right, bottom = rect
    was_down = False
    while state["gen"] == gen:
        down = bool(user32.GetAsyncKeyState(key) & 0x8000)
        if was_down and not down:
            pt = ctypes.wintypes.POINT()
            user32.GetCursorPos(ctypes.byref(pt))
            if key != 0x01 or (left - 8 <= pt.x <= right + 8 and top - 8 <= pt.y <= bottom + 8):
                time.sleep(1.0 if key == 0x01 else 2.5)   # let the app redraw / the AI start answering
                if state["gen"] != gen:
                    return
                if done:
                    finish(gen)
                else:
                    start_step()
                return
        was_down = down
        time.sleep(0.03)


def run_step(use_cloud):
    try:
        with auto.UIAutomationInitializerInThread():
            step = compute_step(use_cloud)
        present(step, "[CLOUD] " if use_cloud else "")
        open_follow_up()
        if step["action"] == "explain":
            bridge.mode.emit("reset")
        elif step["rect"]:
            key = 0x0D if step["action"] == "type" else 0x01
            threading.Thread(target=watch, args=(step["rect"], step["done"], state["gen"], key),
                             daemon=True).start()
    except Exception as err:
        bridge.show.emit(None, f"Error: {err}")
    finally:
        busy.release()


def start_step(use_cloud=False):
    if not state["question"] or not busy.acquire(blocking=False):
        return
    state["gen"] += 1   # cancels the previous click watcher
    bridge.show.emit(None, "Looking…")
    bridge.mode.emit("thinking")
    bridge.card.emit("thinking", "")
    threading.Thread(target=run_step, args=(use_cloud,), daemon=True).start()


def new_question(text, context=""):
    if speak:
        speak.stop()   # a new question replaces whatever Turo was saying
    state["question"], state["context"], state["history"] = text, context, []
    state["path"], state["recalled"] = [], "unset"
    home.add_history(text, state.get("app_title", ""))
    bridge.mode.emit("reset")
    bridge.card.emit("start", text)
    start_step()


# --- spoken input: commands or a new question ---------------------------------------
def command_of(text):
    t = " ".join(re.sub(r"[^a-z' ]", " ", text.lower()).split())
    t = re.sub(r"^(?:(?:please|okay|ok|hey|turo)\s+)+", "", t)
    t = re.sub(r"(?:\s+(?:please|turo))+$", "", t)
    return next((cmd for cmd, phrases in COMMANDS.items() if t in phrases), None)


def handle_speech(text, follow_up=False):
    cmd = command_of(text)
    print(f"[voice] heard {text!r} -> {cmd or ('follow-up' if follow_up else 'question')}")
    if follow_up and not cmd and len(text.split()) < 3:   # stray "okay" / "yeah" picked up in a session
        return
    if cmd == "next":
        start_step()
    elif cmd == "stop":
        stop_all()
    elif cmd == "repeat" and state["last"]:
        say_and_show(*state["last"])
    elif cmd == "agent":
        start_agent()
    else:
        state["hwnd"] = auto.GetForegroundWindow()
        if voice and WAKE_WORD:
            voice.expect()   # a request starts (or continues) the session
        # A follow-up keeps the earlier question as context (sent to the model, never shown or typed).
        new_question(text, context=state["question"] if follow_up else "")


def open_follow_up():
    """Keep the session open: once Turo stops talking, the user just talks (no "Hey Turo") for a while."""
    if not (voice and WAKE_WORD):
        return

    def wait():
        for _ in range(300):   # up to 30 s of speech
            if not (speak and speak.is_busy()):
                break
            time.sleep(0.1)
        voice.expect()

    threading.Thread(target=wait, daemon=True).start()


def on_wake():
    state["gen"] += 1
    voice.expect()   # the session starts now
    bridge.show.emit(None, "Yes? I'm listening…")
    bridge.mode.emit("listening")


# --- F9: type a question -----------------------------------------------------------
def on_ask_key():
    track_app()   # remember the app before Turo takes focus
    bridge.ask.emit()


def on_home_ask(text):
    """A question typed in Home: put the app the user was using back in front, then look at it."""
    hwnd = state.get("app_hwnd")
    if hwnd:
        state["hwnd"] = hwnd
        user32.SetForegroundWindow(hwnd)

    def go():
        time.sleep(0.35)   # let Home disappear and the app repaint before the screenshot
        new_question(text)

    threading.Thread(target=go, daemon=True).start()


def track_app():
    """Remember the last real app window in front (not Turo itself), for questions typed in Home."""
    hwnd = user32.GetForegroundWindow()
    pid = ctypes.wintypes.DWORD()
    user32.GetWindowThreadProcessId(hwnd, ctypes.byref(pid))
    if hwnd and pid.value != os.getpid():
        buf = ctypes.create_unicode_buffer(256)
        user32.GetWindowTextW(hwnd, buf, 256)
        if buf.value:
            state["app_hwnd"], state["app_title"] = hwnd, buf.value


# --- hold Win+Alt: push-to-talk ------------------------------------------------------
held = set()


def mask_modifiers():
    # Tap an unassigned key (vk 0xE8) so releasing Win won't open Start
    # and releasing Alt won't open Office's ribbon key tips.
    user32.keybd_event(0xE8, 0, 0, 0)
    user32.keybd_event(0xE8, 0, 2, 0)   # KEYEVENTF_KEYUP


def on_any_key(event):
    name = (event.name or "").lower()
    kind = "win" if "windows" in name else "alt" if ("alt" in name or "menu" in name) else None
    if not kind:
        return
    if event.event_type == keyboard.KEY_DOWN:
        held.add(kind)
    else:
        held.discard(kind)
    if held == {"win", "alt"}:
        on_talk_down()
    elif state["talking"]:
        on_talk_up()


def on_talk_down():
    if voice and not state["talking"]:   # key repeat fires this many times
        state["talking"] = True
        mask_modifiers()
        state["hwnd"] = auto.GetForegroundWindow()
        state["gen"] += 1
        bridge.show.emit(None, "Listening… let go of Win+Alt when you're done.")
        bridge.mode.emit("listening")
        voice.start()


def on_talk_up():
    if not voice or not state["talking"]:
        return
    state["talking"] = False

    def work():
        text = voice.stop_and_transcribe()
        if text:
            handle_speech(text)
        else:
            bridge.show.emit(None, "I didn't catch that. Hold Win+Alt and try again.")

    threading.Thread(target=work, daemon=True).start()


# --- F7: agent mode, Esc: stop -----------------------------------------------------
def run_agent():
    state["stop"], state["history"] = False, []
    bridge.mode.emit("reset")
    try:
        with auto.UIAutomationInitializerInThread():
            for _ in range(MAX_AGENT_STEPS):
                if state["stop"]:
                    break
                step = compute_step()
                present(step)
                rect = step["rect"]
                if step["action"] == "explain" or not rect:
                    break
                if any(word in step["label"].lower() for word in RISKY):
                    say_and_show(rect, "You click this one yourself. " + step["say"])
                    break
                time.sleep(1.8)   # let the pointer fly and land before clicking
                if state["stop"]:
                    break
                left, top, right, bottom = rect
                auto.Click(int((left + right) / 2), int((top + bottom) / 2))
                if step["action"] == "type" and step["text"]:
                    time.sleep(0.4)
                    keyboard.write(step["text"], delay=0.01)
                    # Never press Enter for the user: sending a message is their call.
                    say_and_show(rect, "I typed it in. Read it, then press Enter or Send when you're ready.")
                    break
                if step["done"]:
                    learn()
                    say_and_show(None, "All done! 🎉")
                    bridge.mode.emit("done")
                    bridge.card.emit("finish", "")
                    break
                time.sleep(1.0)   # let the app redraw
    except Exception as err:
        bridge.show.emit(None, f"Error: {err}")
    finally:
        busy.release()


def start_agent():
    if state["question"] and busy.acquire(blocking=False):
        state["gen"] += 1
        threading.Thread(target=run_agent, daemon=True).start()


def stop_all():
    state["stop"] = True
    state["gen"] += 1
    if speak:
        speak.stop()
    if voice:
        voice.expect(0)   # end the session: back to waiting for "Hey Turo"
    bridge.clear.emit()
    bridge.card.emit("hide", "")


# --- F6: one-time cloud ask (only after the user presses it) ------------------------
def ask_cloud():
    if not brain.cloud:
        bridge.show.emit(None, "Cloud isn't set up. Set TURO_CLOUD_URL, TURO_CLOUD_MODEL and TURO_CLOUD_KEY.")
    elif state["question"]:
        start_step(use_cloud=True)


# --- Home window, tray, settings, status ---------------------------------------------
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


skill_list = [(body.splitlines()[0].replace("SKILL:", "").split("(")[0].split(".")[0].strip(), words)
              for _name, words, body in skills.SKILLS]
win = home.Home(settings, skill_list, get_status, speak.VOICES if speak else {})
win.ask.connect(on_home_ask)
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
tray = Tray(win, lambda: (track_app(), win.open_ask()), toggle_listening, quit_app)
app.setWindowIcon(make_icon())
if speak:
    speak.enabled, speak.voice = settings.get("speak", True), settings.get("voice", "af_heart")
threading.Thread(target=check_ai, daemon=True).start()
app_timer = QTimer()
app_timer.timeout.connect(track_app)
app_timer.start(500)

bridge.ask.connect(win.open_ask)
bridge.show.connect(overlay.point_at)
bridge.mode.connect(overlay.set_mode)
bridge.clear.connect(overlay.clear)
bridge.copy.connect(lambda text: app.clipboard().setText(text))
card = GuideCard()
card.next_clicked.connect(lambda: start_step())
card.do_clicked.connect(start_agent)
card.stop_clicked.connect(stop_all)


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
    keyboard.add_hotkey(ASK_KEY, on_ask_key, suppress=True)
    keyboard.add_hotkey(NEXT_KEY, start_step, suppress=True)
    keyboard.add_hotkey(AGENT_KEY, start_agent, suppress=True)
    keyboard.add_hotkey(CLOUD_KEY, ask_cloud, suppress=True)
    keyboard.add_hotkey("esc", stop_all)
    if voice:
        keyboard.hook(on_any_key)   # not suppressed: Win and Alt must keep working normally
        if WAKE_WORD:
            voice.listen(on_wake, handle_speech, busy=speak.is_busy if speak else None)
            voice.set_listening(settings.get("wake", True))
    print(f"Turo ready. Say \"Hey Turo\"{'' if voice and WAKE_WORD else ' (off)'}, hold Win+Alt to talk, "
          f"{ASK_KEY.upper()} type, {NEXT_KEY.upper()} next, {AGENT_KEY.upper()} do it for me, Esc stop.")
    if settings.get("onboarded"):
        win.show_front()
    else:
        win.show_tour()   # first run: the tour
    sys.exit(app.exec())
