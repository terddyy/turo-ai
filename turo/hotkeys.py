"""Global keys: F9 ask, F10 next, F7 do it, F6 cloud, Esc stop, and Win+Alt to talk (hold or tap)."""
import threading
import time

import keyboard
import uiautomation as auto

from turo import tutor
from turo.ai import brain
from turo.commands import handle_speech, on_wake
from turo.config import AGENT_KEY, ASK_KEY, CLOUD_KEY, NEXT_KEY, WAKE_WORD
from turo.session import bridge, speak, state, user32, voice


# --- F9: type a question -----------------------------------------------------------
def on_ask_key():
    brain.keep_warm()   # the GPU wakes while the user types
    tutor.track_app()   # remember the app before Turo takes focus
    bridge.ask.emit()


# --- talk: hold Win+Alt (or the mic button) = push-to-talk, tap = hands-free -----------
TAP_S = 0.35   # released sooner than this: a tap, so keep listening until the user goes quiet
held = set()
combo = {"down": False, "t": 0.0, "consumed": False}


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
    if held == {"win", "alt"} and not combo["down"]:   # key repeat fires KEY_DOWN many times
        combo["down"] = True
        mask_modifiers()
        talk_press()
    elif held != {"win", "alt"} and combo["down"]:
        combo["down"] = False
        talk_release()


def talk_press():
    """Win+Alt or the mic button went down. A second press while hands-free ends the recording."""
    if not voice:
        bridge.show.emit(None, "No microphone found. Press F9 to type instead.")
        return
    if state["talking"]:
        combo["consumed"] = True
        finish_talk()
        return
    combo["t"], combo["consumed"] = time.time(), False
    if speak:
        speak.stop()   # don't record Turo's own voice
    state["auto"] = False
    begin_listening()
    bridge.show.emit(None, "Listening… let go when you're done.")


def begin_listening(on_quiet=None):
    """Record for the app in front. on_quiet: hands-free, ends by itself when the user stops talking."""
    brain.keep_warm()   # the GPU wakes while the user talks
    tutor.track_app()   # the app in front (or the last one, if Turo's mic button was clicked)
    state["hwnd"] = state.get("app_hwnd") or auto.GetForegroundWindow()
    state["talking"] = True
    state["gen"] += 1
    voice.start(on_quiet)
    tutor.prefetch()   # read the app's controls while the user is still talking
    bridge.mode.emit("listening")
    bridge.talk.emit(True)


def listen_again():
    """Turo just asked the user something ("What would you like to do?"): listen once it stops talking."""
    if not voice:
        return

    def work():
        quiet = 0
        for _ in range(100):   # up to 10 s of Turo talking
            quiet = quiet + 1 if not (speak and speak.is_busy()) else 0
            if quiet >= 3:   # 0.3 s of silence: between phrases is_busy() can read False for a moment
                break
            time.sleep(0.1)
        if not state["talking"]:
            state["auto"] = True
            begin_listening(on_quiet=finish_talk)

    threading.Thread(target=work, daemon=True).start()


def talk_release():
    if not state["talking"] or combo["consumed"]:
        return
    if time.time() - combo["t"] < TAP_S:   # a tap: hands-free until the user stops talking
        voice.hands_free(finish_talk)
        bridge.show.emit(None, "Listening… just talk, I'll stop when you do.")
    else:
        finish_talk()


def finish_talk():
    if not state["talking"]:
        return
    state["talking"] = False
    asked_by_turo, state["auto"] = state.get("auto", False), False
    bridge.talk.emit(False)

    def work():
        text = voice.stop_and_transcribe()
        if text:
            handle_speech(text, follow_up=state.get("active", False))
        elif asked_by_turo:   # Turo listened on its own and the user said nothing: just stop quietly
            bridge.clear.emit()
        else:
            bridge.mode.emit("reset")
            bridge.show.emit(None, "I didn't catch that. Tap Win+Alt or the mic and try again.")

    threading.Thread(target=work, daemon=True).start()


def register(wake_on):
    """Hook every key and start the "Hey Turo" listener. wake_on: the saved Listening setting."""
    keyboard.add_hotkey(ASK_KEY, on_ask_key, suppress=True)
    keyboard.add_hotkey(NEXT_KEY, tutor.start_step, suppress=True)
    keyboard.add_hotkey(CLOUD_KEY, tutor.ask_cloud, suppress=True)
    keyboard.add_hotkey("esc", tutor.stop_all)
    keyboard.hook(on_any_key)   # not suppressed: Win and Alt must keep working normally
    if voice:
        if WAKE_WORD:
            voice.listen(on_wake, handle_speech, busy=speak.is_busy if speak else None)
            voice.set_listening(wake_on)
