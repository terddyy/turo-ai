"""Spoken input: "Hey Turo", short commands (next / stop / repeat / do it), or a new question."""
import re

import uiautomation as auto

from turo import tutor
from turo.config import WAKE_WORD
from turo.session import bridge, say_and_show, state, voice

# Spoken commands. Matched only when the whole phrase is the command, so questions never trigger them.
COMMANDS = {
    "next": ("next", "next step", "continue", "go on", "done", "what's next", "and then", "what now"),
    "stop": ("stop", "cancel", "never mind", "nevermind", "quit", "that's enough", "close"),
    "repeat": ("repeat", "say again", "say that again", "come again", "repeat that"),
    "agent": ("do it", "do it for me", "you do it", "just do it", "go ahead", "do it yourself"),
}


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
        tutor.start_step()
    elif cmd == "stop":
        tutor.stop_all()
    elif cmd == "repeat" and state["last"]:
        say_and_show(*state["last"])
    elif cmd == "agent":
        tutor.start_agent()
    else:
        state["hwnd"] = auto.GetForegroundWindow()
        if voice and WAKE_WORD:
            voice.expect()   # a request starts (or continues) the session
        # A follow-up keeps the earlier question as context (sent to the model, never shown or typed).
        tutor.new_question(text, context=state["question"] if follow_up else "")


def on_wake():
    state["gen"] += 1
    voice.expect()   # the session starts now
    bridge.show.emit(None, "Yes? I'm listening…")
    bridge.mode.emit("listening")


if __name__ == "__main__":
    for phrase in ("Okay next please", "stop", "do it for me Turo", "How do I freeze the top row?"):
        print(f"{phrase!r} -> {command_of(phrase)}")
