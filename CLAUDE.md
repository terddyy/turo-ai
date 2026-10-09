# Turo — project context

Local screen tutor for Windows. User asks "how do I X?" (typed or Taglish voice); Turo reads the
foreground app's controls via UI Automation, a local model picks ONE control, and a click-through
overlay draws a green box on it plus a one-sentence bubble. *Turo* = Tagalog for "to point" / "to teach".

**Hackathon build. Submission closes 10:00 AM, Oct 10 2026. No extensions, no edits.**
Full plan, starter code, demo script, and submission answers: [docs/BUILD_GUIDE.md](docs/BUILD_GUIDE.md).
That guide is the source of truth for scope and order; this file adds verified API notes and rules.

## Priorities (override generic rules)

- **Speed over polish.** Working demo > clean architecture. No new abstractions, no test framework,
  no type-hint campaigns. Each module gets a `if __name__ == "__main__":` smoke test (as in the guide).
- **Build order is fixed** (features 1→8, files config → screen → brain → overlay → main → voice → speak).
  Each step must leave a runnable product. Skip a feature that overruns its slot; never break an earlier one.
- **Feature freeze at 8:20.** After that: only the worst-bug fix, README, video.
- **Skip order if late:** hybrid → agent → spoken reply → voice. Features 1–4 are the product.
- Only add the packages in `requirements.txt`. Ask before any other dependency.

## Hard rules

- **The model never guesses pixels.** It returns a control `id`; coordinates come only from UIA rects.
- **Offline by default.** Features 1–7 must work with Wi-Fi off. Cloud (F6) is only ever called after the
  user presses F6 following the on-screen warning. Never auto-fallback to cloud.
- **No secrets in the repo** — the repo goes public. Cloud settings come only from env vars
  `TURO_CLOUD_URL`, `TURO_CLOUD_MODEL`, `TURO_CLOUD_KEY`. Grep for keys before making it public.
- **Threading:** hotkey callbacks and worker threads only `emit` Qt signals; all drawing on the Qt thread.
  Any UIA call off the main thread goes inside `with auto.UIAutomationInitializerInThread():`.
- Save the target `hwnd` the instant the hotkey fires, before Turo's dialog steals focus.
- Hotkeys never use Alt (opens Excel ribbon key tips). Registered with `suppress=True` (except Esc).
- Agent mode guards stay: `MAX_AGENT_STEPS`, RISKY-name stop, Esc stop.

## Hotkeys

| Key | Action |
| --- | --- |
| F9 | Ask by typing |
| F10 | Next step (re-read screen) |
| Hold F8 | Ask by voice |
| F7 / Esc | Agent mode / stop |
| F6 | One-time cloud ask (after warning) |

## Machine (checked 04:45 Oct 10)

- Windows 11, **Python 3.10.0**, git present. **Ollama not yet installed** at time of check.
- GPU: RTX 3060 Laptop (6 GB VRAM). `qwen3-vl:4b` (3.3 GB) only — **do not switch to 8b**.
- ~4 GB free RAM with Chrome open → close Chrome/heavy apps before testing.
- Display 2560×1600 with Windows scaling on (fractional DPR expected, e.g. 1.5).

## Run

```powershell
cd $HOME\Desktop\turo
.venv\Scripts\activate
python screen.py   # each module has a smoke test; switch to Excel within 3 s
python main.py     # full app
```

## Verified API notes (Context7, Oct 10 2026)

**Ollama (OpenAI-compatible `/v1/chat/completions`)**
- `api_key` is required by the client but ignored. `response_format={"type": "json_object"}` is supported.
- **Thinking:** pass `reasoning_effort="none"` to disable thinking on models that support it. Check with
  `ollama show qwen3-vl:4b` — if capabilities list `thinking`, send it. Also keep the fallback parser
  (text from first `{` to last `}`), since reasoning can leak before the JSON.
- **Context length defaults to 4096 tokens on <24 GB VRAM**, and the OpenAI endpoint has **no `num_ctx`**.
  Overflow is silent (late controls get dropped → "ignores controls late in the list").
  Fix: set user env var `OLLAMA_CONTEXT_LENGTH=8192` then restart Ollama (quit tray app), or create a
  Modelfile variant (`FROM qwen3-vl:4b` / `PARAMETER num_ctx 8192`). Or keep `max_items` ≲ 120.
- `OLLAMA_KEEP_ALIVE` (env) keeps the model loaded between questions — avoids a cold-load on the demo.

**uiautomation (yinkaisheng)**
- `UIAutomationInitializerInThread()` is required in worker threads (confirmed).
- `ControlFromHandle`, `GetForegroundWindow`, `GetRootControl().GetChildren()`, module-level `Click(x, y)`.
- `BoundingRectangle` is in **physical pixels** (Qt makes the process per-monitor DPI aware).
  A Qt "SetProcessDpiAwarenessContext failed" warning at startup is harmless.

**PySide6 / Qt 6**
- High-DPI scaling is always on; default rounding policy is PassThrough, so `devicePixelRatioF()`
  is fractional. Overlay converts UIA physical px → logical px by dividing by it (primary monitor only).

**faster-whisper**
- `transcribe(np.float32 16 kHz array, language="tl")` returns `(segments_generator, info)`;
  work happens only when the generator is iterated.
- Useful knobs: `vad_filter=True` (trims push-to-talk silence), `beam_size=1` (faster on CPU),
  `hotwords="Excel Freeze Panes View"` (biases app terms), `language=None` if Taglish garbles.
- Loading `WhisperModel` takes seconds — load once at startup, not per question.

**pyttsx3 (Windows SAPI5)** — needs `comtypes.CoInitialize()` on its worker thread. If only the first
utterance plays, create the engine inside the loop. No Filipino voice by default (English accent).

## Known gaps in the guide's starter code (fix while building)

- `brain.py`: the guide's error table isn't implemented. Parse defensively: strip to `{…}`, coerce
  `id` to int, missing `done` → false, empty `say` → `"Hindi ko makita. Subukan ulit."`.
- `brain.py`: add `reasoning_effort="none"` if the model has thinking (see above). Time every call; target < 10 s.
- `overlay.py`: clamp the bubble to the screen's right/bottom edge.
- `voice.py`: show the transcribed text in the bubble so mishearings are visible.

## Main demo (rehearse with Wi-Fi off)

Excel: "Paano i-freeze ang top row?" → View tab → Freeze Panes → Freeze Top Row (`done: true`).
Backups: Word "Paano maglagay ng page number?" (Insert → Page Number); File Explorer "Paano gumawa ng
bagong folder?" (New → Folder, used for agent mode).

## Commits

Conventional commits (`feat(screen): ...`). Commit after each feature works so there's always a
known-good state to roll back to.
