import os

BASE_URL = "http://localhost:11434/v1"   # Ollama's OpenAI-compatible endpoint
MODEL = "qwen3-vl:4b"

# Hotkeys: never use Alt (opens Excel's ribbon key tips).
ASK_KEY = "f9"
NEXT_KEY = "f10"
TALK_KEY = "f8"
AGENT_KEY = "f7"
CLOUD_KEY = "f6"

MAX_AGENT_STEPS = 6
MAX_ITEMS = 120   # Ollama's default 4096-token context silently drops controls past ~120

# Cloud fallback (F6 only, after a warning). Values come only from the environment.
CLOUD_BASE_URL = os.environ.get("TURO_CLOUD_URL", "")
CLOUD_MODEL = os.environ.get("TURO_CLOUD_MODEL", "")
CLOUD_API_KEY = os.environ.get("TURO_CLOUD_KEY", "")
