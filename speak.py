"""Spoken replies. Kokoro (natural, offline, faster than real time on CPU), Windows SAPI as fallback."""
import queue
import re
import threading
from pathlib import Path

import numpy as np
import sounddevice as sd

MODELS = Path(__file__).parent / "models"
KOKORO_MODEL = MODELS / "kokoro-v1.0.onnx"   # fp32: ~1x real time on this CPU; int8 was 8x slower
KOKORO_VOICES = MODELS / "voices-v1.0.bin"
TAIL_S = 0.35   # silence after each sentence
VOICES = {   # Kokoro voice id -> label shown in Settings
    "af_heart": "Heart (warm, US)", "af_bella": "Bella (bright, US)", "af_nicole": "Nicole (soft, US)",
    "am_michael": "Michael (calm, US)", "am_fenrir": "Fenrir (deep, US)",
    "bf_emma": "Emma (British)", "bm_george": "George (British)",
}

_q = queue.Queue()
_talking = False
_gen = 0            # bumped by stop(): sentences from an older reply are dropped
voice = "af_heart"
enabled = True

try:
    from kokoro_onnx import Kokoro
    _kokoro = Kokoro(str(KOKORO_MODEL), str(KOKORO_VOICES))
    engine_name = "Kokoro (natural, offline)"
except Exception as err:   # model files missing: fall back to the built-in Windows voice
    print("Kokoro off, using Windows voice:", err)
    _kokoro = None
    engine_name = "Windows voice"


def _sentences(text):
    text = re.sub(r"[\U0001F300-\U0001FAFF]", "", text)   # emoji are read out literally otherwise
    return [s for s in re.split(r"(?<=[.!?])\s+", text.strip()) if s]


_audio = queue.Queue()   # (gen, samples, rate): generated sentences waiting to be played


def _player():
    """Plays sentences as soon as they're ready, so the next one is generated while this one plays."""
    global _talking
    while True:
        gen, samples, rate = _audio.get()
        if gen == _gen and samples is not None:
            sd.play(samples, rate)
            sd.wait()
        if _audio.empty() and _q.empty():
            _talking = False


def _worker():
    global _talking
    if _kokoro is None:
        import comtypes
        import pyttsx3
        comtypes.CoInitialize()   # the Windows speech engine needs COM on this thread
    while True:
        gen, text = _q.get()
        if gen != _gen:
            continue
        _talking = True
        try:
            if _kokoro is not None:
                for sentence in _sentences(text):
                    if gen != _gen:
                        break
                    samples, rate = _kokoro.create(sentence, voice=voice, speed=1.05, lang="en-us")
                    # Pad with silence: the sound device drops the last ~0.2 s of a clip, which clipped the
                    # end of the last sentence. The pad also keeps is_busy() true through the room echo.
                    samples = np.concatenate([samples, np.zeros(int(rate * TAIL_S), dtype=samples.dtype)])
                    _audio.put((gen, samples, rate))
            else:
                engine = pyttsx3.init()   # fresh engine per line: a reused one often goes silent
                engine.setProperty("rate", 175)
                engine.say(text)
                engine.runAndWait()
                engine.stop()
                _talking = not _q.empty()
        except Exception as err:
            print("speak:", err)
            _talking = False


threading.Thread(target=_worker, daemon=True).start()
threading.Thread(target=_player, daemon=True).start()


def is_busy():
    return _talking or not _q.empty() or not _audio.empty()


def stop():
    """Cut off whatever is being said (a new step, Esc)."""
    global _gen, _talking
    _gen += 1
    sd.stop()
    _talking = False


def speak(text):
    if text and enabled:
        _q.put((_gen, text))


if __name__ == "__main__":
    import time
    print("engine:", engine_name)
    t = time.time()
    speak("Hi, I'm Turo. Click the View tab, and I'll show you where Freeze Panes is.")
    while not _talking:
        time.sleep(0.05)
    print(f"started talking after {time.time() - t:.2f}s")
    while is_busy():
        time.sleep(0.1)
