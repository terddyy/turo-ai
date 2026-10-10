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
- **Build order is fixed** (features 1→8, see Layout below).
  Each step must leave a runnable product. Skip a feature that overruns its slot; never break an earlier one.
- **Skip order if late:** hybrid → agent → spoken reply → voice. Features 1–4 are the product.
- Only add the packages in `requirements.txt`. Ask before any other dependency.

## Hard rules

- **Pointing order (user wants visual recognition, 07:10):** every step screenshots the app's whole monitor →
  qwen3-vl returns `bbox_2d` (0-1000 grid) + label + say → `screen.snap` sharpens it to the UIA control
  (same-named TabItem first, then nearest same name, then smallest control under the point). Only if vision
  finds nothing: text plan/match over UIA names. Warm vision call ≈ 1 s.
- **Skills (user, 07:20):** Turo is for ALL apps. `skills/*.md` = per-app know-how (first line `match:` words vs
  window title / exe; `=x` = exact title). Up to 2 skills go into the vision prompt. Have: excel, word, powerpoint,
  file-explorer, browser, ai-chat, windows-settings. Steps are click / type (example copied to clipboard,
  advance on Enter) / explain (no box). Agent types text but never presses Enter/Send.
- **Goal (user, 05:55):** a Clicky-like app (heyclicky.com) that runs locally, in any app. Write our own
  code — never clone or copy clicky / clicky-windows code.
- **Offline by default.** Features 1–7 must work with Wi-Fi off. Cloud (F6) is only ever called after the
  user presses F6 following the on-screen warning. Never auto-fallback to cloud.
- **No secrets in the repo** — the repo goes public. Cloud settings come only from env vars
  `TURO_CLOUD_URL`, `TURO_CLOUD_MODEL`, `TURO_CLOUD_KEY`. Grep for keys before making it public.
- **Threading:** hotkey callbacks and worker threads only `emit` Qt signals; all drawing on the Qt thread.
  Any UIA call off the main thread goes inside `with auto.UIAutomationInitializerInThread():`.
- Save the target `hwnd` the instant the hotkey fires, before Turo's dialog steals focus.
- Hotkeys avoid Alt (opens Excel ribbon key tips), except voice: hold **Win+Alt** (user request), which
  injects unassigned vk 0xE8 on press so Start/key tips do not open. F-keys use `suppress=True` (not Esc).
- Agent mode guards stay: `MAX_AGENT_STEPS`, RISKY-name stop, Esc stop.

## Hotkeys

| Key | Action |
| --- | --- |
| F9 | Ask by typing |
| F10 | Next step (re-read screen) |
| Tap or hold Win+Alt, or click the mic button | Talk (tap = hands-free, ends after 0.9 s quiet) |
| F7 / Esc | Agent mode / stop |
| F6 | One-time cloud ask (after warning) |

## Machine (checked 04:45 Oct 10)

- Windows 11, **Python 3.10.0**, git present. **Ollama not yet installed** at time of check.
- GPU: RTX 3060 Laptop (6 GB VRAM). Model: **`qwen3-vl:4b-instruct`** (the plain `qwen3-vl:4b` tag always
  thinks: 26 s to minutes per step). **Do not switch to 8b.** Keep context 4096 (8192 spills to CPU).
- Python 3.10.0 needs `pydantic<2.12`. Two monitors: external 1920×1080 @100% (primary) + laptop @150%.
- ~4 GB free RAM with Chrome open → close Chrome/heavy apps before testing.
- Display 2560×1600 with Windows scaling on (fractional DPR expected, e.g. 1.5).

## Layout and run

```
main.py               launcher (desktop shortcut runs `pythonw main.py`; same as `python -m turo`)
turo/app.py           wiring only: Qt app, overlay, Home, tray, task card, settings, ready-check status
turo/session.py       shared state dict, `bridge` (Qt signals), busy lock, optional speak/voice modules
turo/tutor.py         tutor loop: compute_step, present, auto-advance watch, agent mode, stop, cloud ask
turo/commands.py      spoken commands ("next", "stop", "do it") and Hey Turo handling
turo/hotkeys.py       F-keys, Esc, hold Win+Alt push-to-talk; register()
turo/config.py        model, hotkeys, paths (ROOT = repo root)
turo/ai/              brain.py (vision + text prompts), skills.py (loads skills/*.md)
turo/sense/screen.py  UI Automation controls, screenshot, snap point -> exact control
turo/voice/           listen.py (Parakeet STT, "Hey Turo", sessions), speak.py (Kokoro TTS)
turo/ui/              overlay.py (buddy cursor), home.py (sidebar + page stack), card.py (task card), tray.py,
                      style.py (colour tokens C, QSS, glyph icons, make_* builders), store.py (settings/history)
turo/ui/pages/        ask.py, tour.py, apps.py, history.py, settings.py: one QWidget per Home page
skills/  models/      per-app know-how; Kokoro model files (git-ignored)
```

```powershell
cd $HOME\Desktop	uro
.venv\Scripts\python main.py              # full app (or double-click the Turo desktop shortcut)
.venv\Scripts\python -m turo.ui.overlay   # smoke tests: each module has a __main__ block
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

**Speech-to-text (07:00): Parakeet TDT 0.6B v3 int8 via `onnx-asr`, English only** — replaced faster-whisper.
  Model files reused from `%APPDATA%\com.pais.handy\models\parakeet-tdt-0.6b-v3-int8` (`TURO_PARAKEET_DIR`
  overrides). ~0.3 s/phrase on CPU. Invents "Thank you." from silence → keep the `MIN_RMS` gate.
  Wake word "Hey Turo" is OFF (user, Oct 10: `WAKE_WORD = False`); talk only via Win+Alt / mic button.
  "Want me to do it?" is offered once per task on a verified, non-RISKY step. UI text is English.

**faster-whisper (no longer used)**
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
