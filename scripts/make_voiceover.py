"""Narration and Turo's spoken steps for the "Turo ai" launch video, made with Kokoro (offline).
Writes video/public/vo/<id>.wav and video/src/vo.json ({id: seconds}); the video times its scenes from that.
Run: .venv\\Scripts\\python scripts/make_voiceover.py
"""
import json
import sys
import wave
from pathlib import Path

import numpy as np
from kokoro_onnx import Kokoro

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from turo.config import ROOT

NARRATOR = "am_michael"
TURO = "af_heart"   # Turo's own voice, same as the app default in turo/voice/speak.py
SPEED = 1.05
LINES = {
    "hook": (NARRATOR, "Ever get stuck on your computer, and the tutorial looks nothing like your screen?"),
    "intro": (NARRATOR, "Meet Turo AI. It points at exactly what to click, right on your own screen."),
    "device": (NARRATOR, "Headphones won't connect? Just ask. Turo reads your screen and walks you there, "
                         "one step at a time."),
    "device_1": (TURO, "Click Bluetooth and devices."),
    "device_2": (TURO, "Now click Add device."),
    "ai": (NARRATOR, "New to AI? Turo shows you where to attach a file, and how to write a good prompt."),
    "ai_1": (TURO, "Click the paperclip to attach your notes."),
    "ai_2": (TURO, "I typed a prompt for you. Press Enter when you're ready."),
    "local": (NARRATOR, "And it all runs on your laptop. No internet, no cloud bills. Your screen stays yours."),
    "outro": (NARRATOR, "Turo AI. Your screen tutor."),
}

out_dir = ROOT / "video" / "public" / "vo"
out_dir.mkdir(parents=True, exist_ok=True)
kokoro = Kokoro(str(ROOT / "models" / "kokoro-v1.0.onnx"), str(ROOT / "models" / "voices-v1.0.bin"))
durations = {}
for key, (voice, text) in LINES.items():
    samples, rate = kokoro.create(text, voice=voice, speed=SPEED, lang="en-us")
    pcm = (np.clip(samples, -1, 1) * 32767).astype(np.int16)
    with wave.open(str(out_dir / f"{key}.wav"), "wb") as f:
        f.setnchannels(1)
        f.setsampwidth(2)
        f.setframerate(rate)
        f.writeframes(pcm.tobytes())
    durations[key] = round(len(pcm) / rate, 3)
    print(f"{key}: {durations[key]:.2f}s")

(ROOT / "video" / "src" / "vo.json").write_text(json.dumps(durations, indent=2) + "\n")
print(f"total: {sum(durations.values()):.1f}s")
