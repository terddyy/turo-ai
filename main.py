"""Start Turo. Same as `python -m turo`; the desktop shortcut runs `pythonw main.py`."""
from turo import instance

if __name__ == "__main__" and instance.claim():   # already running: that copy shows its window instead
    from turo.app import run
    run()
