"""Fix tech names the speech model mishears ("Claude" comes out as "cloud"). Applied to every transcript,
before the wake word, commands or the AI see it. Add a line to FIXES when you catch a new mishearing."""
import re

# (pattern, replacement). Patterns are case-insensitive and match whole words.
FIXES = [
    # "cloud" -> Claude, but not real cloud talk: "the cloud", "a cloud", "Google Cloud", "cloud storage".
    (r"(?<!\bthe )(?<!\ba )(?<!google )(?<!icloud )\b(?:cloud|claud|clawed|clod)\b"
     r"(?!\s+(?:storage|drive|backup|sync|server|servers|computing|service|services|account))", "Claude"),
    (r"\bclaude['’]s\b", "Claude's"),
    (r"\bclaude\s+code\b", "Claude Code"),
    (r"\bchat\s*g\s*[pb]\s*t\b|\bchad\s*g\s*[pb]\s*t\b", "ChatGPT"),
    (r"\bopen\s+a\s*i\b", "OpenAI"),
    (r"\bco[\s-]?pilot\b", "Copilot"),
    (r"\bdeep\s+seek\b", "DeepSeek"),
    (r"\bmid\s+journey\b", "Midjourney"),
    (r"\bo\s*llama\b|\bolama\b", "Ollama"),
    (r"\bv\s*s\s+code\b|\bvs\s*code\b", "VS Code"),
    (r"\bgit\s+hub\b", "GitHub"),
    (r"\byou\s+tube\b", "YouTube"),
    (r"\bpower\s+point\b", "PowerPoint"),
    (r"\bone\s+drive\b", "OneDrive"),
    (r"\bout\s+look\b", "Outlook"),
    (r"\bperplexity\b", "Perplexity"),
    (r"\bgemini\b", "Gemini"),
]
_COMPILED = [(re.compile(p, re.IGNORECASE), r) for p, r in FIXES]


def fix(text: str) -> str:
    for pattern, replacement in _COMPILED:
        text = pattern.sub(replacement, text)
    return text


if __name__ == "__main__":
    for s in ["How do I use connectors in cloud?", "Open Cloud and upload a PDF", "save it to the cloud",
              "how do I check my Google Cloud account", "how do I upload a PDF to chat GPT",
              "Hey Turo, how do I use cloud code in VS code", "back up to cloud storage", "What is clawed?"]:
        print(f"{s!r:52} -> {fix(s)!r}")
