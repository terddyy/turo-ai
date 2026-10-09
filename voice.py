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
# "Hey" + anything like turo/turrow/toro/taro, or a bare "Turo", anywhere in the phrase ("uh, hey Turo, ...").
# Parakeet heard "Hey Turrow" in testing.
WAKE = re.compile(r"(?<![a-z])(?:(?:hey|hi|hay|okay|ok)\W+(?:t[aeiou]{1,2}r+[aeiou]{0,2}w?|tudo|duro|truro|tour o)"
                  r"|turo|toro|turrow)\b\W*", re.IGNORECASE)
FILLERS = re.compile(r"(?<![a-z])(?:uh+|um+|uhm+|erm|er|ah+|hmm+|you know)(?![a-z])[,.]?\s*", re.IGNORECASE)
FOLLOW_UP_S = 45   # a session stays open this long after Turo last spoke; Esc / "stop" ends it

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
def clean(text):
    """Drop fillers like "uh", "um" so the model sees the actual question."""
    return " ".join(FILLERS.sub("", text).split()).strip(" ,.")


def strip_wake(text):
    """The request around the wake word ("" if only the name was said), or None if there's no wake word."""
    m = WAKE.search(text)
    if not m:
        return None
    after, before = clean(text[m.end():]), clean(text[:m.start()])
    return after if after or len(before.split()) < 3 else before   # "how do I X, hey Turo" works too


_expect_until = 0.0


def expect(seconds=FOLLOW_UP_S):
    """Session: for `seconds`, every phrase is a request, no wake word needed. 0 ends the session."""
    global _expect_until
    _expect_until = time.time() + seconds if seconds else 0.0


def in_session():
    return time.time() < _expect_until


def set_listening(on):
    """Pause or resume "Hey Turo" (push-to-talk still works)."""
    global _listening
    _listening = bool(on)
    if not on:
        expect(0)


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


def _listen_loop(on_wake, on_request):
    global _expect_until
    for clip in _utterances():
        if _recording or _busy():
            continue
        text = transcribe(clip)
        if not text:
            continue
        rest = strip_wake(text)
        if rest is None and time.time() < _expect_until:   # inside a session: no wake word needed
            if clean(text):
                on_request(clean(text), True)
            continue
        if rest is None:
            continue
        print(f"[voice] wake: {text!r}")
        _expect_until = 0.0
        if len(rest.split()) >= 2:
            on_request(rest, False)
        else:
            expect(7)
            on_wake()


def listen(on_wake, on_followup, busy=None):
    """Background "Hey Turo" listener. on_wake(): heard the name only.
    on_followup(text, is_follow_up): a request; is_follow_up=True when said inside the conversation window."""
    global _busy, _listening
    _listening = True
    if busy:
        _busy = busy
    threading.Thread(target=_listen_loop, args=(on_wake, on_followup), daemon=True).start()


if __name__ == "__main__":
    print("Say: 'Hey Turo, how do I freeze the top row?' (Ctrl+C to quit)")
    listen(lambda: print("-> wake only, listening for the question"),
           lambda text, follow: print("-> request:", text, "(follow-up)" if follow else ""))
    while True:
        time.sleep(1)
