"""The tutor loop: look at the app, show one step, wait for the user's click, repeat. Plus agent mode (F7),
stop (Esc) and the one-time cloud ask (F6). Runs on worker threads; the UI is reached only via `bridge`."""
import ctypes
import ctypes.wintypes
import os
import threading
import time

import keyboard
import uiautomation as auto

from turo.ai import brain, memory, skills
from turo.config import MAX_AGENT_STEPS
from turo.sense import screen
from turo.session import bridge, busy, open_follow_up, say_and_show, speak, state, user32, voice
from turo.ui import store

RISKY = ("delete", "remove", "send", "pay", "buy", "format", "sign out", "shut down", "uninstall")


def compute_step(use_cloud=False):
    """One look at the screen. Caller holds the UIA initializer.
    Returns {action: click/type/explain, rect, say, text, done, label}.
    Vision first: the model reads a screenshot and decides. UI Automation only sharpens the box."""
    pre = state.pop("prefetch", None)
    if pre and pre[0] == state["hwnd"] and time.time() - pre[1] < 30:
        title, items = pre[2]   # read while the user was talking
    else:
        title, items = screen.list_controls(state["hwnd"])
    exe = screen.exe_of(state["hwnd"])
    skill = skills.for_app(title, exe)
    state["app"] = exe.lower()
    if state["recalled"] == "unset":   # first look at this question: anything similar done before here?
        state["recalled"] = memory.recall(state["app"], state["question"])
    known = state["recalled"] or []
    # Remembered labels are a hint, not proof that the current screen is at the same task step.
    bridge.mode.emit("capture")   # Turo's ring, label and card must not be in its own screenshot
    bridge.card.emit("capture", "")
    time.sleep(0.15)
    try:
        image, (ml, mt, mw, mh) = screen.grab(state["hwnd"])
    finally:
        bridge.mode.emit("thinking")
        bridge.card.emit("restore", "")
    look = dict(use_cloud=use_cloud, skill=skill, context=state["context"], memory=" > ".join(known),
                items=items, viewport=(ml, mt, mw, mh))
    seen = brain.locate(state["question"], title, image, state["history"], **look)
    last = state.get("last_label", "")
    if last and not use_cloud and seen["action"] != "explain" and screen.label_score(seen["label"], last) >= 0.8:
        # Same control as the step the user just did: the 4b model loops here. Ask once more, excluding it.
        seen = brain.locate(state["question"], title, image, state["history"], avoid=last, **look)
    step = {"action": seen["action"], "rect": None, "say": seen["say"], "text": seen["text"],
            "done": seen["done"], "label": seen["label"], "verified": False}
    if seen["action"] == "explain":   # an answer, not a click: no box
        step["done"] = True
        return step
    if seen["point"] or seen.get("control_id") is not None:
        point = seen["point"] or (500, 500)
        x, y = ml + point[0] * mw / 1000, mt + point[1] * mh / 1000
        box = seen.get("box")
        rect = (ml + box[0]*mw/1000, mt + box[1]*mh/1000,
                ml + box[2]*mw/1000, mt + box[3]*mh/1000) if box else None
        step["rect"], name, step["verified"] = screen.resolve_target(
            x, y, seen["label"], items, action=seen["action"], box=rect, control_id=seen.get("control_id"))
        step["label"] = name or seen["label"]
        if not step["verified"]:
            step["done"] = False
            if not step["rect"]:
                step["say"] = "I couldn't verify that control on this screen. Open the relevant menu and press Next."
            else:
                step["say"] = "Check this suggested area; I couldn't verify the exact control. " + step["say"]
        return step
    # The model saw nothing to click: fall back to reasoning over the control names.
    reply = brain.next_step(state["question"], title, items, state["history"], use_cloud=use_cloud, skill=skill)
    hit = next((i for i in items if i["id"] == reply["id"]), None)
    if hit:
        step.update(action="click", rect=hit["rect"], say=reply["say"], done=reply["done"], label=hit["name"],
                    verified=True)
    else:
        step.update(done=False, say="I couldn't verify that control. Open the relevant menu and press Next.")
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
        if not step.get("verified", False):
            short = f'Check {step["label"] or "this area"}'
        say_and_show(step["rect"], short[:48], spoken=say)
    else:
        say_and_show(None, say)
    bridge.card.emit("step", full)
    state["history"].append(say)
    state["last_label"] = step["label"] if step["rect"] else ""
    if step["rect"] and step["label"] and step.get("verified", False):
        state["path"].append(screen.clean_label(step["label"]))


def learn():
    """The task finished: remember the click path for next time."""
    memory.remember(state["app"], state["question"], state["path"])


def finish(gen):
    learn()
    state["active"] = False
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
        offer(step)
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
    brain.keep_warm()   # also covers the wait for the user's click before the next step
    state["gen"] += 1   # cancels the previous click watcher
    state["offered"] = False   # the user moved on: the "Want me to do it?" question is stale
    bridge.show.emit(None, "Looking…")
    bridge.mode.emit("thinking")
    bridge.card.emit("thinking", "")
    threading.Thread(target=run_step, args=(use_cloud,), daemon=True).start()


def new_question(text, context="", mode="teach"):
    """mode: 'teach' (a how/where question: show the steps), 'offer' (a command: show the step and ask
    "Want me to do it?"), 'do' (asked "... for me": run agent mode right away)."""
    if speak:
        speak.stop()   # a new question replaces whatever Turo was saying
    state["question"], state["context"], state["history"] = text, context, []
    state["path"], state["recalled"], state["last_label"] = [], "unset", ""
    state["active"], state["asked"], state["offered"], state["mode"] = True, False, False, mode
    store.add_history(text, state.get("app_title", ""))
    bridge.mode.emit("reset")
    bridge.card.emit("start", text)
    start_step()   # instructions only, even for "... for me"


def offer(step):
    """Once per task, for a command (not a how-to question) or a user who is stuck, when the step is a verified,
    harmless click: ask "Want me to do it?" (card + voice). Answer: Yes button, F7, or saying "yes"."""
    if (True or state.get("mode") != "offer" or state["asked"]   # off: Turo gives instructions only or not step["rect"] or not step.get("verified") or step["action"] == "explain"
            or any(word in step["label"].lower() for word in RISKY)):
        return
    state["asked"] = state["offered"] = True
    bridge.card.emit("offer", "Want me to do it for you?")
    if speak:
        speak.speak("Want me to do it for you?")


def prefetch():
    """Read the app's controls while the user is still talking: the first step skips that 0.4 s."""
    hwnd = state["hwnd"]

    def work():
        try:
            with auto.UIAutomationInitializerInThread():
                state["prefetch"] = (hwnd, time.time(), screen.list_controls(hwnd))
        except Exception as err:   # window closed mid-scan: compute_step reads it again
            print("[prefetch]", err)

    threading.Thread(target=work, daemon=True).start()


def add_remark(text):
    """A follow-up that isn't a new task ("I already did that", "it's not there"): same task, look again."""
    if speak:
        speak.stop()
    state["history"].append(f'User replied: "{text}"')
    if state.get("mode") == "teach":   # "I can't find it", "I already did that": stuck, so offer help
        state["mode"], state["asked"] = "offer", False
    start_step()


# --- questions typed in Home ---------------------------------------------------------
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


# --- F7: agent mode, Esc: stop -----------------------------------------------------
def run_agent():
    state["stop"], state["history"], state["last_label"] = False, [], ""   # nothing clicked yet
    state["offered"] = False
    bridge.card.emit("offer", "")
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
                if not step.get("verified", False):
                    say_and_show(rect, "I can't verify the exact control. Please check it yourself.")
                    break
                if any(word in step["label"].lower() for word in RISKY):
                    say_and_show(rect, "You click this one yourself. " + step["say"])
                    break
                time.sleep(1.8)   # let the pointer fly and land before clicking
                if state["stop"]:
                    break
                if not screen.verify_target(rect, step["label"], step["action"]):
                    say_and_show(None, "That control changed or couldn't be verified. Press Next to look again.")
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
                    state["active"] = False
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
    state["active"] = state["offered"] = False
    if voice and state["talking"]:   # Esc while listening: throw the recording away
        state["talking"] = False
        voice.cancel()
        bridge.talk.emit(False)
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
