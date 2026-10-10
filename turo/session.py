"""Shared runtime: the signal bridge to the Qt thread, the current question's state, and the optional voice modules.
Every other part of Turo talks to the UI only through `bridge` (worker threads must never draw)."""
import ctypes
import threading
import time

from PySide6.QtCore import QObject, Signal

from turo.config import WAKE_WORD

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
    card = Signal(str, str)       # task card: start / step / thinking / finish / hide / capture / restore / offer
    talk = Signal(bool)           # mic button: recording on / off
    home = Signal()               # a second launch asked to show the window
    clear = Signal()


bridge = Bridge()
state = {"hwnd": None, "question": "", "context": "", "history": [], "gen": 0, "stop": False,
         "app": "", "path": [], "recalled": None, "last_label": "", "active": False, "offered": False,
         "talking": False, "last": None}
busy = threading.Lock()   # one model call at a time
user32 = ctypes.windll.user32


def say_and_show(rect, text, spoken=None):
    state["last"] = (rect, text)
    bridge.show.emit(rect, text)
    if speak:
        speak.speak(spoken or text)   # queued: a step never cuts off the one before it (Esc / stop / new question do)


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
