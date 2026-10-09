import ctypes
import ctypes.wintypes
import sys
import threading
import time

import keyboard
import uiautomation as auto
from PySide6.QtCore import QObject, Qt, Signal
from PySide6.QtWidgets import QApplication, QInputDialog

import brain
import screen
from config import AGENT_KEY, ASK_KEY, CLOUD_KEY, MAX_AGENT_STEPS, NEXT_KEY
from overlay import Overlay

try:
    import speak
except Exception as err:   # no SAPI voice: run silent
    print("Spoken reply off:", err)
    speak = None

try:
    import voice
except Exception as err:   # no mic or model: typing still works
    print("Voice input off:", err)
    voice = None


class Bridge(QObject):
    ask = Signal()                # hotkey thread -> Qt thread
    show = Signal(object, str)    # worker thread -> Qt thread
    clear = Signal()


app = QApplication(sys.argv)
app.setQuitOnLastWindowClosed(False)
overlay = Overlay()
bridge = Bridge()
state = {"hwnd": None, "question": "", "history": [], "gen": 0, "stop": False, "talking": False}
busy = threading.Lock()   # one model call at a time
user32 = ctypes.windll.user32
RISKY = ("delete", "remove", "send", "pay", "buy", "format", "sign out", "shut down", "uninstall")


def say_and_show(rect, text):
    bridge.show.emit(rect, text)
    if speak:
        speak.speak(text)


def compute_step(use_cloud=False):
    """One look at the screen. Returns (rect, say, done, label). Caller holds the UIA initializer."""
    title, items = screen.list_controls(state["hwnd"])
    reply = brain.next_step(state["question"], title, items, state["history"], use_cloud=use_cloud)
    hit = next((i for i in items if i["id"] == reply["id"]), None)
    if hit:
        return hit["rect"], reply["say"], reply["done"], hit["name"]
    # No usable control (browser, game, custom UI): read the screenshot instead.
    image, (wl, wt, ww, wh) = screen.grab(state["hwnd"])
    seen = brain.locate(state["question"], title, image, state["history"], use_cloud=use_cloud)
    if seen["point"]:
        x, y = wl + seen["point"][0] * ww / 1000, wt + seen["point"][1] * wh / 1000
        return (x - 18, y - 18, x + 18, y + 18), seen["say"], seen["done"], seen["say"]
    return None, seen["say"], False, ""


def watch_click(rect, done, gen):
    """Clicky-style auto-advance: a click inside the box moves to the next step."""
    left, top, right, bottom = rect
    was_down = False
    while state["gen"] == gen:
        down = bool(user32.GetAsyncKeyState(0x01) & 0x8000)   # left mouse button
        if was_down and not down:
            pt = ctypes.wintypes.POINT()
            user32.GetCursorPos(ctypes.byref(pt))
            if left - 8 <= pt.x <= right + 8 and top - 8 <= pt.y <= bottom + 8:
                time.sleep(1.0)   # let the app redraw
                if state["gen"] != gen:
                    return
                if done:
                    bridge.show.emit(None, "Tapos na! 🎉")
                    time.sleep(2.5)
                    if state["gen"] == gen:
                        bridge.clear.emit()
                else:
                    start_step()
                return
        was_down = down
        time.sleep(0.03)


def run_step(use_cloud):
    try:
        with auto.UIAutomationInitializerInThread():
            rect, say, done, _ = compute_step(use_cloud)
        say = ("[CLOUD] " if use_cloud else "") + say
        if not rect and not use_cloud and brain.cloud:
            say += f" Pindutin ang {CLOUD_KEY.upper()} para itanong sa cloud (lalabas sa laptop ang screen at tanong mo)."
        state["history"].append(say)
        say_and_show(rect, say)
        if rect:
            gen = state["gen"]
            threading.Thread(target=watch_click, args=(rect, done, gen), daemon=True).start()
    except Exception as err:
        bridge.show.emit(None, f"Error: {err}")
    finally:
        busy.release()


def start_step(use_cloud=False):
    if not state["question"] or not busy.acquire(blocking=False):
        return
    state["gen"] += 1   # cancels the previous click watcher
    bridge.show.emit(None, f'"{state["question"]}"\nTinitingnan ko ang screen mo...')
    threading.Thread(target=run_step, args=(use_cloud,), daemon=True).start()


def new_question(text):
    state["question"], state["history"] = text, []
    start_step()


# --- F9: type a question -----------------------------------------------------------
def on_ask_key():
    state["hwnd"] = auto.GetForegroundWindow()   # remember the app before Turo takes focus
    bridge.ask.emit()


def ask_question():
    dlg = QInputDialog()
    dlg.setWindowFlags(dlg.windowFlags() | Qt.WindowStaysOnTopHint)
    dlg.setWindowTitle("Turo")
    dlg.setLabelText("Ano ang gusto mong gawin?")
    dlg.show()
    dlg.raise_()
    dlg.activateWindow()
    if dlg.exec() and dlg.textValue().strip():
        new_question(dlg.textValue().strip())


# --- hold Win+Alt: ask by voice ----------------------------------------------------
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
        bridge.show.emit(None, "🎙️ Nakikinig ako... (bitawan ang Win+Alt kapag tapos na)")
        voice.start()


def on_talk_up():
    if not voice or not state["talking"]:
        return
    state["talking"] = False

    def work():
        text = voice.stop_and_transcribe()
        if text:
            new_question(text)
        else:
            bridge.show.emit(None, "Hindi kita narinig. Subukan ulit.")

    threading.Thread(target=work, daemon=True).start()


# --- F7: agent mode, Esc: stop -----------------------------------------------------
def run_agent():
    state["stop"], state["history"] = False, []
    try:
        with auto.UIAutomationInitializerInThread():
            for _ in range(MAX_AGENT_STEPS):
                if state["stop"]:
                    break
                rect, say, done, label = compute_step()
                state["history"].append(say)
                say_and_show(rect, say)
                if not rect:
                    break
                if any(word in label.lower() for word in RISKY):
                    say_and_show(rect, "Ikaw na ang mag-click nito. " + say)
                    break
                time.sleep(1.5)   # show the pointer before clicking
                if state["stop"]:
                    break
                left, top, right, bottom = rect
                auto.Click(int((left + right) / 2), int((top + bottom) / 2))
                if done:
                    say_and_show(None, "Tapos na! 🎉")
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
    bridge.clear.emit()


# --- F6: one-time cloud ask (only after the user presses it) ------------------------
def ask_cloud():
    if not brain.cloud:
        bridge.show.emit(None, "Walang cloud na naka-set. Ilagay ang TURO_CLOUD_URL / MODEL / KEY.")
    elif state["question"]:
        start_step(use_cloud=True)


bridge.ask.connect(ask_question)
bridge.show.connect(overlay.point_at)
bridge.clear.connect(overlay.clear)
keyboard.add_hotkey(ASK_KEY, on_ask_key, suppress=True)
keyboard.add_hotkey(NEXT_KEY, start_step, suppress=True)
keyboard.add_hotkey(AGENT_KEY, start_agent, suppress=True)
keyboard.add_hotkey(CLOUD_KEY, ask_cloud, suppress=True)
keyboard.add_hotkey("esc", stop_all)
if voice:
    keyboard.hook(on_any_key)   # not suppressed: Win and Alt must keep working normally
print(f"Turo ready. {ASK_KEY.upper()} type, hold Win+Alt talk, {NEXT_KEY.upper()} next, "
      f"{AGENT_KEY.upper()} do it for me, Esc stop, {CLOUD_KEY.upper()} cloud"
      f"{'' if brain.cloud else ' (not set)'}.")
sys.exit(app.exec())
