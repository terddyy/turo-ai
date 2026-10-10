"""Turo's memory: the click path that finished a task, per app. Stored only on this laptop.

Next time a similar question comes up in the same app, Turo replays the path straight away (no model call)
while the screen matches it, and falls back to vision with the path as a hint when it doesn't.
"""
import json
import re
import time

from turo.config import DATA

FILE = DATA / "memory.json"
MAX_PER_APP = 100
MIN_SIMILARITY = 0.5   # share of meaningful words two questions must have in common
STOP_WORDS = {"how", "do", "i", "the", "a", "an", "to", "in", "on", "of", "my", "this", "here", "can", "you", "me",
              "please", "is", "it", "what", "where", "turo", "hey", "uh", "um", "and", "with", "for"}


def _words(text):
    return {w for w in re.findall(r"[a-z0-9]+", text.lower()) if w not in STOP_WORDS}


def _load():
    try:
        return json.loads(FILE.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return {}


def _save(mem):
    DATA.mkdir(parents=True, exist_ok=True)
    FILE.write_text(json.dumps(mem, indent=2), encoding="utf-8")


def remember(app, question, path):
    """Save the labels that were clicked, in order, for a task that finished."""
    if not (app and question and path):
        return
    mem = _load()
    items = mem.setdefault(app, [])
    for item in items:
        if item["q"].lower() == question.lower():
            item.update(path=path, uses=item.get("uses", 0) + 1, t=time.strftime("%Y-%m-%d %H:%M"))
            break
    else:
        items.insert(0, {"q": question, "path": path, "uses": 1, "t": time.strftime("%Y-%m-%d %H:%M")})
        del items[MAX_PER_APP:]
    _save(mem)
    print(f"[memory] {app}: {question!r} -> {' > '.join(path)}")


def recall(app, question):
    """The remembered click path for the most similar earlier question in this app, or None."""
    asked = _words(question)
    best, best_score = None, MIN_SIMILARITY
    for item in _load().get(app, []):
        known = _words(item["q"])
        score = len(asked & known) / max(len(asked | known), 1)
        if score >= best_score:
            best, best_score = item, score
    if best:
        print(f"[memory] recalled {best['q']!r} ({best_score:.2f}): {' > '.join(best['path'])}")
    return best["path"] if best else None


def count():
    return sum(len(v) for v in _load().values())


if __name__ == "__main__":
    remember("excel.exe", "How do I freeze the top row?", ["View", "Freeze Panes", "Freeze Top Row"])
    print(recall("excel.exe", "uh how can I freeze the top row in this sheet"))
    print(recall("excel.exe", "How do I insert a chart?"))
    print(count(), "tasks remembered")
