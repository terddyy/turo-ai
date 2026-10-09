import numpy as np
import sounddevice as sd
from faster_whisper import WhisperModel

model = WhisperModel("small", device="cpu", compute_type="int8")   # load once: takes seconds
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
    segments, _info = model.transcribe(audio, language="tl", beam_size=1, vad_filter=True,
                                       hotwords="Excel Word Freeze Panes View Insert Page Number folder")
    return " ".join(s.text for s in segments).strip()


if __name__ == "__main__":
    import time
    print("Speak for 4 seconds...")
    start()
    time.sleep(4)
    t = time.time()
    print(repr(stop_and_transcribe()), f"{time.time() - t:.1f}s")
