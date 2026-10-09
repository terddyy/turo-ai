"""App skills: plain-text know-how per app, loaded into the prompt when that app is on screen.

Each file in skills/ starts with a `match:` line of comma-separated words. A skill is used when any word
appears in the window title or the program name (e.g. "excel.exe"); "=word" means the whole title equals it.
Add an app by dropping in a new file.
"""
from pathlib import Path

SKILLS_DIR = Path(__file__).parent / "skills"
MAX_SKILLS = 2   # keep the prompt inside the model's 4096-token context


def _load():
    skills = []
    for path in sorted(SKILLS_DIR.glob("*.md")):
        head, _, body = path.read_text(encoding="utf-8").partition("\n")
        if head.lower().startswith("match:"):
            words = [w.strip().lower() for w in head[6:].split(",") if w.strip()]
            skills.append((path.stem, words, body.strip()))
    return skills


SKILLS = _load()


def for_app(title, exe):
    """Know-how text for the app in front ("" if none), most specific first (title before program)."""
    title, exe = (title or "").lower(), (exe or "").lower()
    def hit(w, text):
        return text == w[1:] if w.startswith("=") else w in text

    by_title = [s for s in SKILLS if any(hit(w, title) for w in s[1])]
    by_exe = [s for s in SKILLS if s not in by_title and any(hit(w, exe) for w in s[1])]
    specific = lambda s: len(s[1])   # a skill matching fewer words is more specific (Claude before AI-chat)
    picked = (sorted(by_title, key=specific) + sorted(by_exe, key=specific))[:MAX_SKILLS]
    if picked:
        print(f"[skills] {[s[0] for s in picked]}")
    return "\n\n".join(s[2] for s in picked)


if __name__ == "__main__":
    for name, words, body in SKILLS:
        print(f"{name:16} {len(body):5} chars  match={words}")
    for t, e in [("Book1 - Excel", "EXCEL.EXE"), ("ChatGPT - Google Chrome", "chrome.exe"),
                 ("Downloads", "explorer.exe"), ("Settings", "ApplicationFrameHost.exe"),
                 ("Settings - Google Chrome", "chrome.exe"), ("Document1 - Word", "WINWORD.EXE"),
                 ("Claude", "claude.exe"), ("Spotify", "spotify.exe")]:
        print(f"{t!r:28} {e:20} ->", for_app(t, e)[:40].replace(chr(10), " "))
