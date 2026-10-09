import queue
import re
import threading
import time

import numpy as np
import onnx_asr
import sounddevice as sd

from config import PARAKEET_DIR

SR = 16000
BLOCK = 1600   # 100 ms
MIN_RMS = 0.004   # quieter than this is silence; Parakeet invents "Thank you." from silence
# "Hey" + anything like turo/turrow/toro/taro, or a bare "Turo". Parakeet heard "Hey Turrow" in testing.
WAKE = re.compile(r"^\W*(?:(?:hey|hi|hay|a|okay|ok)\W+(?:t[aeiou]{1,2}r+[aeiou]{0,2}w?|tudo|duro|truro|tour o|two row)"
                  r"|turo|toro|turrow)\b\W*", re.IGNORECASE)

# Parakeet TDT 0.6B v3 (English), int8 on CPU: ~0.4 s per phrase. Load once: takes seconds.
model = onnx_asr.load_model("nemo-parakeet-tdt-0.6b-v3", PARAKEET_DIR, quantization="int8")
level = 0.0            # live mic loudness, for the overlay's waveform
_ptt = []              # push-to-talk frames
_recording = False
_listening = False
_blocks = queue.Queue()
_busy = lambda: False  # set by listen(): True while Turo is speaking (don't hear ourselves)


def _on_audio(data, _frames, _time, _status):
    global level
    mono = data[:, 0].copy()
    level = float(np.sqrt(np.mean(mono * mono)))
    if _recording:
        _ptt.append(mono)
    elif _listening:
        _blocks.put(mono)


stream = sd.InputStream(samplerate=SR, channels=1, dtype="float32", blocksize=BLOCK, callback=_on_audio)
stream.start()


def transcribe(audio):
    if len(audio) < SR * 0.3 or float(np.sqrt(np.mean(audio * audio))) < MIN_RMS:
        return ""
    return str(model.recognize(audio, sample_rate=SR)).strip()


# --- push-to-talk ------------------------------------------------------------------
def start():
    global _recording
    _ptt.clear()
    _recording = True


def stop_and_transcribe():
    global _recording
    _recording = False
    if not _ptt:
        return ""
    return transcribe(np.concatenate(_ptt))


# --- "Hey Turo" --------------------------------------------------------------------
def strip_wake(text):
    """Returns the words after the wake word, or None if the wake word isn't there."""
    m = WAKE.match(text)
    return text[m.end():].strip() if m else None


def _utterances():
    """Yields one numpy clip per spoken phrase, using a simple loudness gate."""
    noise, buf, speaking, quiet = 0.005, [], False, 0
    while True:
        block = _blocks.get()
        rms = float(np.sqrt(np.mean(block * block)))
        loud = rms > max(0.012, noise * 3)
        if not speaking:
            noise = 0.95 * noise + 0.05 * rms
            buf = (buf + [block])[-3:]   # keep 300 ms before speech starts
            if loud:
                speaking, quiet = True, 0
        else:
            buf.append(block)
            quiet = 0 if loud else quiet + 1
            if quiet >= 8 or len(buf) > 120:   # 0.8 s of silence, or 12 s max
                clip, buf, speaking = np.concatenate(buf), [], False
                if len(clip) > SR * 0.5:
                    yield clip


def _listen_loop(on_wake, on_followup):
    expect_until = 0.0   # after a bare "Hey Turo", the next phrase is the question
    for clip in _utterances():
        if _recording or _busy():
            continue
        text = transcribe(clip)
        if not text:
            continue
        if time.time() < expect_until:
            expect_until = 0.0
            on_followup(text)
            continue
        rest = strip_wake(text)
        if rest is None:
            continue
        print(f"[voice] wake: {text!r}")
        if len(rest.split()) >= 2:
            on_followup(rest)
        else:
            expect_until = time.time() + 7
            on_wake()


def listen(on_wake, on_followup, busy=None):
    """Background "Hey Turo" listener. on_wake(): heard the name only. on_followup(text): a request."""
    global _busy, _listening
    _listening = True
    if busy:
        _busy = busy
    threading.Thread(target=_listen_loop, args=(on_wake, on_followup), daemon=True).start()


if __name__ == "__main__":
    print("Say: 'Hey Turo, paano i-freeze ang top row?' (Ctrl+C to quit)")
    listen(lambda: print("-> wake only, listening for the question"),
           lambda text: print("-> request:", text))
    while True:
        time.sleep(1)
