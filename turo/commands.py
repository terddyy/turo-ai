"""Spoken input: "Hey Turo", short commands (next / stop / repeat / do it), or a new question."""
import re

import uiautomation as auto

from turo import tutor
from turo.ai import brain
from turo.config import WAKE_WORD
from turo.session import bridge, say_and_show, state, voice

# Spoken commands. Matched only when the whole phrase is the command, so questions never trigger them.
COMMANDS = {
    "next": ("next", "next step", "continue", "go on", "done", "what's next", "and then", "what now",
             "what next", "now what", "then what", "what's next then", "what do i do now", "what should i do now"),
    "stop": ("stop", "cancel", "never mind", "nevermind", "quit", "that's enough", "close"),
    "repeat": ("repeat", "say again", "say that again", "come again", "repeat that"),
    "agent": ("do it", "do it for me", "you do it", "just do it", "go ahead", "do it yourself"),
    "yes": ("yes", "yeah", "yep", "yes please", "sure", "please do", "yes do it"),   # answers "Want me to do it?"
    "no": ("no", "nope", "no thanks", "show me", "i'll do it", "i will do it", "let me do it"),
}


# A follow-up that opens like this is a new task; anything else ("I already did that", "it's not there")
# is a remark about the current task.
NEW_TASK = re.compile(r"^(?:(?:okay|ok|so|and|hey|turo|please|um|uh)\s+)*(?:how|paano|pano|where|saan|what is|what are|"
                      r"what's the|can you|could you|can i|i want|i need|help me|show me|teach me|open|ano ang)\b")


# Asked to act, not to be taught: "open connectors for me", "can you turn on dark mode?"
DO_FOR_ME = re.compile(r"\b(?:for me|do it|you do)\b|^(?:(?:okay|ok|hey|turo|please)\s+)*(?:can|could|would) you\s+"
                       r"(?!show|tell|teach|help|explain|guide)")


# "Hi Turo" (Parakeet also hears "Hi to the", "Hey Toro"): a greeting, not a task.
GREETING = re.compile(r"^(?:hi|hello|hey|hay|hiya|yo|good (?:morning|afternoon|evening)|kumusta|musta)\b")
NAME = re.compile(r"^(?:turo|toro|turrow|truro|tudo|duro|to row|to the|tour o|there)\b")
THANKS = re.compile(r"^(?:(?:okay|ok)\s+)?(?:thanks|thank you|thank you so much|salamat|ty)(?:\s+turo)?$")
# Asking to learn ("how do I...", "where is...") -> teach. A command ("turn on dark mode") -> offer to do it.
QUESTION = re.compile(r"^(?:(?:okay|ok|so|and|um|uh|please)\s+)*(?:how|paano|pano|where|saan|nasaan|what|why|when|"
                      r"which|who|is there|are there|can i|could i|do i|does|ano|bakit|can you|could you|show me|"
                      r"teach me|help me)\b")


def split_greeting(text):
    """'Hi Turo, how do I X?' -> 'how do I X?'. '' when the user only said hello."""
    plain = _plain(text)
    m = GREETING.match(plain)
    if not m:
        return text
    rest = plain[m.end():].strip()
    n = NAME.match(rest)
    if n:
        rest = rest[n.end():].strip()
    if not rest:
        return ""
    drop = len(plain.split()) - len(rest.split())   # words used by the greeting
    return " ".join(text.split()[drop:]).strip(" ,.!")


def intent_of(text):
    """'do': act right away. 'offer': show the step and ask "Want me to do it?". 'teach': just show."""
    plain = _plain(text)
    if DO_FOR_ME.search(plain):
        return "do"
    if QUESTION.match(plain) or text.rstrip().endswith("?"):
        return "teach"
    return "offer"


def _plain(text):
    return " ".join(re.sub(r"[^a-z' ]", " ", text.lower()).split())


def command_of(text):
    t = _plain(text)
    t = re.sub(r"^(?:(?:please|okay|ok|hey|turo)\s+)+", "", t)
    t = re.sub(r"(?:\s+(?:please|turo))+$", "", t)
    return next((cmd for cmd, phrases in COMMANDS.items() if t in phrases), None)


def ask_back(text):
    """Turo needs more from the user: say so, then listen without another tap."""
    from turo import hotkeys   # hotkeys imports this module
    say_and_show(None, text)
    hotkeys.listen_again()


def handle_speech(text, follow_up=False):
    text = split_greeting(text)
    if not text:
        ask_back("Hi! What would you like to do?")
        return
    if THANKS.match(_plain(text)):
        say_and_show(None, "You're welcome! Tap the mic whenever you need me.")
        return
    cmd = command_of(text)
    print(f"[voice] heard {text!r} -> {cmd or ('follow-up' if follow_up else 'question')}")
    if follow_up and not cmd and len(text.split()) < 3 and voice and voice.in_session():   # stray "okay" in a "Hey Turo" session
        return
    if cmd == "next":
        tutor.start_step()
    elif cmd == "stop":
        tutor.stop_all()
    elif cmd == "repeat" and state["last"]:
        say_and_show(*state["last"])
    elif cmd == "agent" or (cmd == "yes" and state["offered"]):
        tutor.start_agent()
    elif cmd in ("yes", "no"):
        state["offered"] = False
        bridge.card.emit("offer", "")   # hide the question; the user does it themselves
    elif follow_up and state["question"] and not NEW_TASK.match(_plain(text)):
        if voice and WAKE_WORD:
            voice.expect()   # the conversation goes on
        tutor.add_remark(text)
    elif len(_plain(text).split()) < 2:   # "Relevant", a cough: not a task
        ask_back("Sorry, I didn't get that. What would you like to do?")
    else:
        tutor.track_app()   # Turo's own windows never count as the app
        state["hwnd"] = state.get("app_hwnd") or auto.GetForegroundWindow()
        if voice and WAKE_WORD:
            voice.expect()   # a request starts (or continues) the session
        # A follow-up keeps the earlier question as context (sent to the model, never shown or typed).
        tutor.new_question(text, context=state["question"] if follow_up else "", mode=intent_of(text))


def on_wake():
    brain.keep_warm()   # the GPU wakes while the user is still talking
    state["gen"] += 1
    voice.expect()   # the session starts now
    bridge.show.emit(None, "Yes? I'm listening…")
    bridge.mode.emit("listening")


if __name__ == "__main__":
    for phrase in ("Okay next please", "stop", "do it for me Turo", "How do I freeze the top row?"):
        print(f"{phrase!r} -> {command_of(phrase)}")
