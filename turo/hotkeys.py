"""Global keys: F9 ask, F10 next, F7 do it, F6 cloud, Esc stop, and hold Win+Alt to talk."""
import threading

import keyboard
import uiautomation as auto

from turo import tutor
from turo.commands import handle_speech, on_wake
from turo.config import AGENT_KEY, ASK_KEY, CLOUD_KEY, NEXT_KEY, WAKE_WORD
from turo.session import bridge, speak, state, user32, voice


# --- F9: type a question -----------------------------------------------------------
def on_ask_key():
    tutor.track_app()   # remember the app before Turo takes focus
    bridge.ask.emit()


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


def register(wake_on):
    """Hook every key and start the "Hey Turo" listener. wake_on: the saved Listening setting."""
    keyboard.add_hotkey(ASK_KEY, on_ask_key, suppress=True)
    keyboard.add_hotkey(NEXT_KEY, tutor.start_step, suppress=True)
    keyboard.add_hotkey(AGENT_KEY, tutor.start_agent, suppress=True)
    keyboard.add_hotkey(CLOUD_KEY, tutor.ask_cloud, suppress=True)
    keyboard.add_hotkey("esc", tutor.stop_all)
    if voice:
        keyboard.hook(on_any_key)   # not suppressed: Win and Alt must keep working normally
        if WAKE_WORD:
            voice.listen(on_wake, handle_speech, busy=speak.is_busy if speak else None)
            voice.set_listening(wake_on)
