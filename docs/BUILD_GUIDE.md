# Turo: Build Guide

Oct 10, 2026 · @geno

Turo is a local screen tutor for Windows: ask how to do something, and it points at the right button and explains the step. Submission closes at 10:00 AM on Oct 10, 2026, with no extensions and no edits.

## What you are building

All eight features are in scope. Build them in the order below, so there is a working product at every stop. *Turo* is Tagalog for both "to point" and "to teach".

| Order | Feature | Key | Done when |
| --- | --- | --- | --- |
| 1 | Ask by typing | F9 | A typed question returns a step in under 10 seconds |
| 2 | Pointer and bubble |  | A green box lands on the right button, with one sentence of explanation |
| 3 | Next step | F10 | Pressing the key re-reads the screen and points at the following button |
| 4 | Works offline |  | Features 1 to 3 work with Wi-Fi off |
| 5 | Ask by voice | Hold F8 | Speaking a Taglish question gives the same result as typing it |
| 6 | Spoken reply |  | Turo reads each step aloud through a Windows voice |
| 7 | Agent mode | F7, Esc to stop | Turo clicks through a three-step task by itself and refuses risky buttons |
| 8 | Hybrid mode | F6 | When the local model has no answer, one key press asks a cloud model, after a warning |

Each feature sits on top of the ones before it. If one is not working by the end of its time slot, skip it and move on. Features 1 to 4 are the product; 5 to 8 are what make it impressive.

## How it works

Windows supplies the exact position of every button, and the local model only chooses which one to point at. The model never guesses pixels, which is what makes a small model reliable enough to demo.

1. You press the ask key while Excel is in front.
2. Turo reads the list of visible controls from Windows UI Automation: each one's name, type, and rectangle.
3. You type or speak the question. Speech becomes text through faster-whisper on the CPU.
4. The local model receives the question and the numbered control list. It returns the number of one control and one sentence.
5. A transparent, click-through overlay draws a box on that control's rectangle and shows the sentence.
6. You click the button yourself. Pressing the next key repeats steps 2 to 5 until the model says the task is done.

The screenshot is optional. Start with the control list alone, because text is faster and the list already holds the positions.

## Setup

Start the two downloads first, because they run while you write code. Everything needs about 6 GB (estimated), and the laptop had 27 GB free at yesterday's check.

Install Ollama and pull the model (3.3 GB):

```powershell
winget install Ollama.Ollama
ollama pull qwen3-vl:4b
ollama run qwen3-vl:4b "Paano mag-save ng file sa Excel? Sagot sa isang pangungusap."
```

If `winget` fails, use the installer from ollama.com/download. The last command is your first Taglish quality check.

Create the project and install the packages:

```powershell
mkdir turo; cd turo
python -m venv .venv
.venv\Scripts\activate
pip install PySide6 uiautomation keyboard mss pillow openai faster-whisper sounddevice numpy pyttsx3
```

Download the speech model once, while you still have internet:

```powershell
python -c "from faster_whisper import WhisperModel; WhisperModel('small', device='cpu', compute_type='int8')"
```

Before testing, close Chrome and other heavy apps. The laptop had only 4 GB of memory available with them open.

## Files and build order

Build the seven files in this order, and test each one alone before moving on. The code is an untested starting point, written without a Windows machine, so expect small fixes.

| Order | File | Job |
| --- | --- | --- |
| 1 | `config.py` | Model name, base URL, hotkeys, cloud settings |
| 2 | `screen.py` | Reads the control list from the app in front |
| 3 | `brain.py` | Builds the prompt, calls the local or cloud model, parses the reply |
| 4 | `overlay.py` | Draws the box and the bubble |
| 5 | `main.py` | Hotkeys, the tutor loop, agent mode, and the cloud key |
| 6 | `voice.py` | Push-to-talk recording and transcription |
| 7 | `speak.py` | Reads each step aloud |

### config.py

```python
BASE_URL = "http://localhost:11434/v1"   # Ollama's OpenAI-compatible endpoint
MODEL = "qwen3-vl:4b"
ASK_KEY = "f9"
NEXT_KEY = "f10"
```

The hotkeys are registered with `suppress=True`, so Excel never sees them. Avoid Alt in any hotkey, because Alt opens Excel's ribbon key tips.

### screen.py

```python
import time
import uiautomation as auto

CLICKABLE = {"ButtonControl", "SplitButtonControl", "MenuItemControl", "TabItemControl",
             "CheckBoxControl", "RadioButtonControl", "ComboBoxControl", "EditControl",
             "HyperlinkControl", "ListItemControl"}
SKIP = {"DataGridControl", "TableControl"}   # spreadsheet cells: thousands of items


def _walk(ctrl, depth, items, max_items, max_depth):
    if depth > max_depth or len(items) >= max_items:
        return
    for child in ctrl.GetChildren():
        kind = child.ControlTypeName
        if kind in SKIP:
            continue
        if kind in CLICKABLE and child.Name:
            r = child.BoundingRectangle
            if r.width() > 0 and r.height() > 0:
                items.append({
                    "id": len(items) + 1,
                    "type": kind.replace("Control", ""),
                    "name": child.Name[:60],
                    "rect": (r.left, r.top, r.right, r.bottom),
                })
        _walk(child, depth + 1, items, max_items, max_depth)


def list_controls(handle=None, max_items=200, max_depth=16):
    win = auto.ControlFromHandle(handle) if handle else auto.GetForegroundControl().GetTopLevelControl()
    pid = win.ProcessId
    # Open menus are separate top-level windows of the same app, so scan those too.
    roots = [w for w in auto.GetRootControl().GetChildren() if w.ProcessId == pid]
    items = []
    for root in roots:
        _walk(root, 0, items, max_items, max_depth)
    return win.Name, items


if __name__ == "__main__":
    time.sleep(3)   # switch to Excel now
    t = time.time()
    title, items = list_controls()
    print(title, len(items), f"{time.time() - t:.1f}s")
    for it in items:
        print(it["id"], it["type"], it["name"])
```

Test it: run `python screen.py`, switch to Excel, and check three things.

- The scan takes under 2 seconds. If it is slower, print the control types and add the slow container to `SKIP`.
- The ribbon tabs (Home, Insert, View) appear in the list.
- With a ribbon dropdown open, its menu items appear too.

### brain.py

```python
import json
from openai import OpenAI
from config import BASE_URL, MODEL

client = OpenAI(base_url=BASE_URL, api_key="local")

SYSTEM = """You are Turo, an on-screen tutor for Windows apps.
The user asks how to do something in the app on their screen.
You receive a numbered list of the controls that are visible right now.
Pick the ONE control the user should click next.
Reply with JSON only: {"id": number, "say": string, "done": boolean}
- id: the number of the control to click, or -1 if no listed control fits.
- say: one short sentence telling the user what to click and why. Use the user's language. If they wrote Taglish, answer in Taglish.
- done: true only when the task is finished after this click.
Never invent a control that is not in the list."""


def next_step(question, app_title, items, history):
    controls = "\n".join(f'{i["id"]} | {i["type"]} | {i["name"]}' for i in items)
    shown = "\n".join(f"- {h}" for h in history) or "none"
    user = (f"Question: {question}\nApp window: {app_title}\n"
            f"Steps already shown:\n{shown}\n\nControls:\n{controls}")
    resp = client.chat.completions.create(
        model=MODEL,
        temperature=0,
        response_format={"type": "json_object"},
        messages=[{"role": "system", "content": SYSTEM},
                  {"role": "user", "content": user}],
    )
    return json.loads(resp.choices[0].message.content)


if __name__ == "__main__":
    demo = [{"id": 1, "type": "TabItem", "name": "Home"},
            {"id": 2, "type": "TabItem", "name": "View"},
            {"id": 3, "type": "Button", "name": "Bold"}]
    print(next_step("paano mag-freeze ng top row?", "Book1 - Excel", demo, []))
```

Test it: `python brain.py` should return id 2 (the View tab) with a Taglish sentence. Time the call. This is your go or no-go check for the model.

### overlay.py

```python
from PySide6.QtCore import Qt, QRectF
from PySide6.QtGui import QColor, QFont, QPainter, QPen
from PySide6.QtWidgets import QApplication, QWidget


class Overlay(QWidget):
    def __init__(self):
        super().__init__()
        self.setWindowFlags(Qt.FramelessWindowHint | Qt.WindowStaysOnTopHint
                            | Qt.Tool | Qt.WindowTransparentForInput)
        self.setAttribute(Qt.WA_TranslucentBackground)
        self.setAttribute(Qt.WA_ShowWithoutActivating)
        self.setGeometry(QApplication.primaryScreen().geometry())
        self.target = None
        self.text = ""

    def point_at(self, rect, text):
        # UI Automation gives physical pixels; Qt draws in scaled pixels.
        scale = self.devicePixelRatioF()
        if rect:
            left, top, right, bottom = (v / scale for v in rect)
            self.target = QRectF(left, top, right - left, bottom - top)
        else:
            self.target = None
        self.text = text
        self.show()
        self.update()

    def paintEvent(self, _event):
        p = QPainter(self)
        p.setRenderHint(QPainter.Antialiasing)
        anchor = self.target or QRectF(40, 40, 0, 0)
        if self.target:
            p.setPen(QPen(QColor("#22c55e"), 4))
            p.setBrush(Qt.NoBrush)
            p.drawRoundedRect(self.target.adjusted(-6, -6, 6, 6), 8, 8)
        bubble = QRectF(anchor.left(), anchor.bottom() + 14, 420, 72)
        p.setPen(Qt.NoPen)
        p.setBrush(QColor(17, 24, 39, 235))
        p.drawRoundedRect(bubble, 10, 10)
        p.setPen(QColor("white"))
        p.setFont(QFont("Segoe UI", 11))
        p.drawText(bubble.adjusted(12, 8, -12, -8), Qt.TextWordWrap, self.text)
```

Test it: show the overlay with a fixed rectangle over a known button. Check that the box lines up and that clicks pass through to the app underneath. If the box is offset, the display scaling division is the first suspect; your screen runs at 2560 x 1600 with scaling on. Clamp the bubble if it runs off the right or bottom edge.

### main.py

```python
import sys
import threading

import keyboard
import uiautomation as auto
from PySide6.QtCore import QObject, Qt, Signal
from PySide6.QtWidgets import QApplication, QInputDialog

import brain
import screen
from config import ASK_KEY, NEXT_KEY
from overlay import Overlay


class Bridge(QObject):
    ask = Signal()                # hotkey thread -> Qt thread
    show = Signal(object, str)    # worker thread -> Qt thread


app = QApplication(sys.argv)
app.setQuitOnLastWindowClosed(False)
overlay = Overlay()
bridge = Bridge()
state = {"hwnd": None, "question": "", "history": []}


def run_step():
    try:
        with auto.UIAutomationInitializerInThread():
            title, items = screen.list_controls(state["hwnd"])
        reply = brain.next_step(state["question"], title, items, state["history"])
        hit = next((i for i in items if i["id"] == reply.get("id")), None)
        say = reply.get("say", "")
        state["history"].append(say)
        bridge.show.emit(hit["rect"] if hit else None, say)
    except Exception as err:
        bridge.show.emit(None, f"Error: {err}")


def start_step():
    bridge.show.emit(None, "Tinitingnan ko ang screen mo...")
    threading.Thread(target=run_step, daemon=True).start()


def on_ask_key():
    state["hwnd"] = auto.GetForegroundWindow()   # remember the app before Turo takes focus
    bridge.ask.emit()


def ask_question():
    dlg = QInputDialog()
    dlg.setWindowFlags(dlg.windowFlags() | Qt.WindowStaysOnTopHint)
    dlg.setWindowTitle("Turo")
    dlg.setLabelText("Ano ang gusto mong gawin?")
    if dlg.exec() and dlg.textValue().strip():
        state["question"], state["history"] = dlg.textValue().strip(), []
        start_step()


bridge.ask.connect(ask_question)
bridge.show.connect(overlay.point_at)
keyboard.add_hotkey(ASK_KEY, on_ask_key, suppress=True)
keyboard.add_hotkey(NEXT_KEY, start_step, suppress=True)
sys.exit(app.exec())
```

Three things this file gets right that are easy to get wrong:

- Hotkey callbacks run on another thread, so they only emit signals. All drawing happens on the Qt thread.
- UI Automation calls from a worker thread sit inside `UIAutomationInitializerInThread`.
- The app's window handle is saved at the moment the hotkey fires, before the question box takes focus.

If the question box opens without focus, click it once. Windows blocks background apps from taking focus.

### voice.py

```python
import numpy as np
import sounddevice as sd
from faster_whisper import WhisperModel

model = WhisperModel("small", device="cpu", compute_type="int8")
frames = []


def _on_audio(data, _frames, _time, _status):
    frames.append(data.copy())


stream = sd.InputStream(samplerate=16000, channels=1, dtype="float32", callback=_on_audio)


def start():
    frames.clear()
    stream.start()


def stop_and_transcribe():
    stream.stop()
    if not frames:
        return ""
    audio = np.concatenate(frames).flatten()
    segments, _info = model.transcribe(audio, language="tl")
    return " ".join(s.text for s in segments).strip()
```

Wire it into `main.py` as hold-to-talk on a third key:

```python
import voice

talking = False


def on_talk_down(_event):
    global talking
    if not talking:               # key repeat fires this many times
        talking = True
        state["hwnd"] = auto.GetForegroundWindow()
        voice.start()


def on_talk_up(_event):
    global talking
    talking = False

    def work():
        text = voice.stop_and_transcribe()
        if text:
            state["question"], state["history"] = text, []
            start_step()

    threading.Thread(target=work, daemon=True).start()


keyboard.on_press_key("f8", on_talk_down, suppress=True)
keyboard.on_release_key("f8", on_talk_up, suppress=True)
```

If Taglish questions come out garbled, try `language=None` to let the model detect the language. Voice needs no focus change, so it is also the smoother demo.

### speak.py (spoken reply)

```python
import queue
import threading

import comtypes
import pyttsx3

_q = queue.Queue()


def _worker():
    comtypes.CoInitialize()   # the Windows speech engine needs COM on this thread
    engine = pyttsx3.init()
    engine.setProperty("rate", 175)
    while True:
        text = _q.get()
        engine.say(text)
        engine.runAndWait()


threading.Thread(target=_worker, daemon=True).start()


def speak(text):
    if text:
        _q.put(text)
```

In `main.py`, add `import speak` and call `speak.speak(say)` right after `say` is set in `run_step`. Install it with `pip install pyttsx3`. It uses the voices built into Windows, so it works offline. Windows likely has no Filipino voice installed, so Taglish will be read with an English accent. If it only speaks the first sentence, create the engine inside the loop.

### Agent mode (in main.py)

Agent mode reuses the same loop, but Turo clicks the control itself and then re-reads the screen. Add these lines to `config.py`:

```python
AGENT_KEY = "f7"
CLOUD_KEY = "f6"
MAX_AGENT_STEPS = 6
```

Add `"stop": False` to `state`, import `time` and the new config names, and put this above the last line of `main.py`:

```python
RISKY = ("delete", "remove", "send", "pay", "buy", "format", "sign out", "shut down", "uninstall")


def run_agent():
    state["stop"] = False
    state["history"] = []
    try:
        with auto.UIAutomationInitializerInThread():
            for _ in range(MAX_AGENT_STEPS):
                if state["stop"]:
                    break
                title, items = screen.list_controls(state["hwnd"])
                reply = brain.next_step(state["question"], title, items, state["history"])
                hit = next((i for i in items if i["id"] == reply.get("id")), None)
                say = reply.get("say", "")
                state["history"].append(say)
                bridge.show.emit(hit["rect"] if hit else None, say)
                if not hit:
                    break
                if any(word in hit["name"].lower() for word in RISKY):
                    bridge.show.emit(hit["rect"], "Ikaw na ang mag-click nito. " + say)
                    break
                time.sleep(1.2)   # show the box before clicking
                if state["stop"]:
                    break
                left, top, right, bottom = hit["rect"]
                auto.Click((left + right) // 2, (top + bottom) // 2)
                if reply.get("done"):
                    break
                time.sleep(0.8)   # let the app redraw
    except Exception as err:
        bridge.show.emit(None, f"Error: {err}")


def start_agent():
    if state["question"]:
        threading.Thread(target=run_agent, daemon=True).start()


def stop_agent():
    state["stop"] = True


keyboard.add_hotkey(AGENT_KEY, start_agent, suppress=True)
keyboard.add_hotkey("esc", stop_agent)
```

Ask a question first with F9 or F8, then press F7 to have Turo do it. Three guards keep it safe: a six-step limit, a stop on any button whose name looks destructive, and Esc to stop at once.

### Hybrid mode (in config.py, brain.py, and main.py)

The cloud is a fallback the user chooses, never a default. Add these lines to `config.py`:

```python
import os

CLOUD_BASE_URL = os.environ.get("TURO_CLOUD_URL", "")
CLOUD_MODEL = os.environ.get("TURO_CLOUD_MODEL", "")
CLOUD_API_KEY = os.environ.get("TURO_CLOUD_KEY", "")
```

In `brain.py`, add a second client and a `use_cloud` argument:

```python
from config import CLOUD_API_KEY, CLOUD_BASE_URL, CLOUD_MODEL

cloud = OpenAI(base_url=CLOUD_BASE_URL, api_key=CLOUD_API_KEY) if CLOUD_API_KEY else None

# def next_step(question, app_title, items, history, use_cloud=False):
#     ...
#     use = cloud if (use_cloud and cloud) else client
#     model = CLOUD_MODEL if (use_cloud and cloud) else MODEL
#     resp = use.chat.completions.create(model=model, ...)
```

In `main.py`, change `run_step` to read a one-time cloud flag and label every answer:

```python
        use_cloud = state.pop("cloud_once", False)
        reply = brain.next_step(state["question"], title, items, state["history"], use_cloud=use_cloud)
        hit = next((i for i in items if i["id"] == reply.get("id")), None)
        say = ("[CLOUD] " if use_cloud else "[LOCAL] ") + reply.get("say", "")
        if not hit and not use_cloud and brain.cloud:
            say += " Pindutin ang F6 para itanong sa cloud. Lalabas sa laptop ang listahan ng buttons."
```

```python
def ask_cloud():
    if brain.cloud and state["question"]:
        state["cloud_once"] = True
        start_step()


keyboard.add_hotkey(CLOUD_KEY, ask_cloud, suppress=True)
```

Set the three values in PowerShell before running, using any provider with an OpenAI-compatible endpoint:

```powershell
$env:TURO_CLOUD_URL = "https://your-provider/v1"
$env:TURO_CLOUD_MODEL = "model-name"
$env:TURO_CLOUD_KEY = "your-key"
```

Three rules for this feature:

- The key lives only in the environment. The repository is public, so never commit it.
- Pressing F6 after the warning is the consent. Turo never calls the cloud by itself.
- The warning must stay true: the question and the names of the on-screen controls are what leave the laptop.

## Prompt and reply format

The model returns one JSON object per step, and the code treats anything unexpected as "no pointer, show the sentence".

| Field | Meaning | If it is wrong |
| --- | --- | --- |
| `id` | Number of the control to click, or -1 | No match in the list: show the bubble with no box |
| `say` | One sentence in the user's language | Empty: show "Hindi ko makita. Subukan ulit." |
| `done` | True when the task ends after this click | Missing: treat as false |

The target walkthrough, which is also the main demo:

| Step | Screen state | Expected reply |
| --- | --- | --- |
| 1 | Excel on the Home tab | Points at the View tab |
| 2 | View tab open | Points at Freeze Panes |
| 3 | Freeze Panes dropdown open | Points at Freeze Top Row, with `done` true |

If the model picks wrong controls, improve the prompt before changing models: add two worked examples to the system prompt, and send fewer controls.

## Timeline to 10:00 AM

Stop adding features at 8:20, whatever state the code is in. With all eight features in scope there are only 15 minutes of slack, so skip any feature that overruns its slot.

- [ ] 4:55 to 5:20. Start both downloads. Write `config.py` and `screen.py`. Confirm the Excel control list.
- [ ] 5:20 to 5:45. Write `brain.py`. Go or no-go: the View tab test passes and the reply is fast enough to demo.
- [ ] 5:45 to 6:35. Write `overlay.py` and `main.py`. Get the first full loop working with a typed question (features 1 and 2).
- [ ] 6:35 to 6:55. Add the next key and finish the three-step Excel walkthrough. Test it with Wi-Fi off (features 3 and 4).
- [ ] 6:55 to 7:20. Voice input (feature 5).
- [ ] 7:20 to 7:35. Spoken reply (feature 6).
- [ ] 7:35 to 8:00. Agent mode (feature 7).
- [ ] 8:00 to 8:20. Hybrid mode (feature 8).
- [ ] 8:20 to 8:45. Rehearse the demos with Wi-Fi off. Fix only the worst bug.
- [ ] 8:45 to 9:20. Record the one-minute video. Write the README. Check that no key is in the code, then make the GitHub repository public.
- [ ] 9:20 to 9:35. Post the video on X or LinkedIn. Tag Devin / Cognition and add #AppBuildersPH.
- [ ] 9:35 to 9:45. Submit on the Cerebral Valley page. Check every field first, because there is no resubmit.

If the 5:45 check fails, do not switch to `qwen3-vl:8b`: at 6.1 GB it will not fit your graphics memory. Shrink the control list and add examples to the prompt.

## Demo and video script

Rehearse three questions and keep only the ones that work every time. Each should need two or three clicks, so the next-step loop is visible.

| Demo | Question | Expected path |
| --- | --- | --- |
| 1, Excel | "Paano i-freeze ang top row?" | View, Freeze Panes, Freeze Top Row |
| 2, Word | "Paano maglagay ng page number?" | Insert, Page Number |
| 3, File Explorer | "Paano gumawa ng bagong folder?" | New, Folder |

The paths are from memory of Office and Windows 11. Confirm them on your laptop during rehearsal.

**Five-minute pitch on Demo Day.**

1. The problem, in 30 seconds: people get stuck in software, and cloud screen assistants need internet, a subscription, and your screen.
2. Turn Wi-Fi off where the judges can see it.
3. Run demo 1 by voice, in Taglish, and let Turo speak each step.
4. Run demo 2 in a different app, to show it is not hard-coded to Excel.
5. Run demo 3 in agent mode: press F7 and let Turo do the clicks itself.
6. Show Ollama running locally and say what runs on the laptop.
7. Close with why local. Mention the opt-in cloud key only if you have time left; do not turn Wi-Fi back on.

**One-minute video.**

| Seconds | Shot |
| --- | --- |
| 0 to 8 | "Stuck in Excel, with no internet?" Show Wi-Fi off. |
| 8 to 33 | Demo 1 by voice, from question to the last click, uncut. |
| 33 to 48 | Agent mode: press F7 and Turo finishes demo 3 itself. |
| 48 to 56 | "Your screen never leaves this laptop. No subscription. No message cap." |
| 56 to 60 | Name and tagline: "Turo. It points, it teaches, it stays on your PC." |

Record the screen at normal speed. The briefing lists fake benchmarks as grounds for dispute, so do not speed up the model's response.

## Submission answers

These drafts cover every field the briefing lists. Edit them to match what actually shipped, and delete any feature you did not finish.

| Field | Draft |
| --- | --- |
| Project name | Turo |
| Short description | Turo is a local AI screen tutor for Windows. Ask how to do something in an app, in English or Taglish, and it points at the exact button and walks you through step by step, or does the clicks for you. Speech recognition and the language model run on the laptop, so it works with no internet and your screen never leaves the device. |
| Why does this product benefit from running AI locally? | A screen tutor has to read whatever is on your screen: bank pages, chats, client records. Running the model on the device means none of that leaves the laptop. It also keeps working offline, costs nothing per question, and has no monthly message cap. |
| What runs locally | Reading the on-screen controls (Windows UI Automation), speech recognition, the language model, the spoken replies, agent mode, and the overlay. |
| What requires internet | A one-time download of the two models and the Python packages, plus the optional cloud fallback. Everything else runs offline. |
| Models used | qwen3-vl:4b through Ollama; Whisper small through faster-whisper. |
| Technologies and frameworks | Python, PySide6 (Qt), Ollama, faster-whisper, uiautomation, keyboard, sounddevice, pyttsx3, and the openai Python client. |
| APIs and cloud services | An optional cloud fallback through an OpenAI-compatible API; name the provider and model you used. It is off by default and runs only when the user presses the cloud key after a warning. |
| Existing code and assets | None. All code was written during the hackathon. The concept is inspired by Clicky (heyclicky.com); no Clicky code is used. |
| AI development tools | Claude, for planning, this build guide, and starter code. Add every other tool you used. |
| Team members | Use the exact names from the official list at appbuildersph.com/hackathon. |

Still to produce before submitting:

- [ ] Public GitHub repository with a README that lets judges run it: install steps, model pull commands, and the hotkeys
- [ ] Demo video, about one minute
- [ ] X or LinkedIn post with the video, tagging Devin / Cognition, with #AppBuildersPH
- [ ] The "existing code" line is true: nothing copied from the Clicky repository

## Risks and fallbacks

The model choosing the wrong control is the main risk, and rehearsal is the main defence: demo only the questions that work every time.

| Risk | Fallback |
| --- | --- |
| The model picks the wrong control | Add two worked examples to the prompt. Send fewer controls. |
| The control scan is slow | Add the slow container type to `SKIP`. Lower `max_depth`. |
| Open menus are missing from the list | Use two-click demos that need no dropdown, such as Word's Insert tab. |
| The box is offset from the button | Check the scaling division in `point_at`. |
| Answers ignore controls late in the list | The model's context window is too small. Raise the context length in Ollama's settings, or lower `max_items`. |
| The model writes reasoning before the JSON | Turn thinking off for the model, or keep only the text from the first `{` to the last `}`. |
| The app exposes no controls, as browsers and games often do | Out of scope today; say so if asked. Reading the screenshot is the next step. |
| Voice mishears Taglish | Type the question. Show the heard text in the bubble so mistakes are visible. |
| Agent mode clicks the wrong thing | Demo it only on the rehearsed task. The step limit, the risky-name stop, and Esc are the guards. |
| The cloud key leaks into the public repository | Keep it in environment variables only. Search the code for the key before making the repository public. |
| The cloud call fails on venue Wi-Fi | Skip it. The local demo is the point. |
| The projector changes your screen resolution | Start Turo after plugging in the display, and mirror the screen. |
| Time runs out | Skip in this order: hybrid, agent, spoken reply, voice. |

## Sources

- AppBuildersPH Hackathon 2026 Participant Briefing (the PDF you shared): rules, deadline, judging criteria, and submission fields.
- [Clicky](https://heyclicky.com): the product this idea adapts, including its platforms and pricing.
- [qwen3-vl on Ollama](https://ollama.com/library/qwen3-vl): model tags and sizes.
