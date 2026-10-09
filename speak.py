import queue
import threading

import comtypes
import pyttsx3

_q = queue.Queue()
_talking = False


def _worker():
    comtypes.CoInitialize()   # the Windows speech engine needs COM on this thread
    global _talking
    while True:
        text = _q.get()
        _talking = True
        engine = pyttsx3.init()   # fresh engine per line: a reused one often goes silent after the first
        engine.setProperty("rate", 175)
        engine.say(text)
        engine.runAndWait()
        engine.stop()
        _talking = not _q.empty()


threading.Thread(target=_worker, daemon=True).start()


def is_busy():
    return _talking or not _q.empty()


def speak(text):
    if text:
        _q.put(text)


if __name__ == "__main__":
    import time
    speak("Pindutin ang View tab.")
    speak("Second line, to check that it keeps talking.")
    time.sleep(8)
