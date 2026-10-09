import os

BASE_URL = "http://localhost:11434/v1"   # Ollama's OpenAI-compatible endpoint
MODEL = "qwen3-vl:4b-instruct"   # the default 4b tag always thinks: 26 s+ per step, sometimes minutes
NO_THINK = False  # True sends reasoning_effort="none"; only for models whose `ollama show` lists "thinking"

# Hotkeys: never use Alt (opens Excel's ribbon key tips).
ASK_KEY = "f9"
NEXT_KEY = "f10"
TALK_KEY = "f8"
AGENT_KEY = "f7"
CLOUD_KEY = "f6"

MAX_AGENT_STEPS = 6
MAX_ITEMS = 120   # keeps the prompt inside Ollama's 4096-token context (overflow is silent)

# Cloud fallback (F6 only, after a warning). Values come only from the environment.
CLOUD_BASE_URL = os.environ.get("TURO_CLOUD_URL", "")
CLOUD_MODEL = os.environ.get("TURO_CLOUD_MODEL", "")
CLOUD_API_KEY = os.environ.get("TURO_CLOUD_KEY", "")
