# Turo — submission draft

Source: https://cerebralvalley.ai/e/appbuildersph-hackathon-2026/hackathon/submit

## Project Name

Turo

## Project Description

Turo is an offline AI screen tutor for Windows. When someone gets stuck in an app, they can type a question or say ‘Hey Turo’, and Turo looks at the current screen, highlights the next control, and explains what to do. It guides users one step at a time, with spoken instructions and optional agent mode for simple clicks and text entry.

Instead of making users search tutorials and translate instructions to their own screen, Turo teaches directly inside the app they are using. The prototype includes app-specific guidance for Excel, Word, PowerPoint, File Explorer, browsers, AI chat apps, and Windows Settings.

The screen-understanding model, speech recognition, and speech output run locally after setup. This keeps screen and microphone data on the laptop during local use, works without internet, and avoids per-question cloud inference charges. Voice input currently uses an English speech model; typed questions can include English or Taglish. An optional cloud request is available only when explicitly triggered by the user.

## Team Name


## Team Members (Separated by comma)

Pending confirmation. The form currently lists Imogen Inocentes (@terdimogen).

## Public GitHub Repository


## Demo Video


## X / LinkedIn Video URL


## Technical Disclosures

AI MODELS
• Qwen3-VL 4B Instruct (qwen3-vl:4b-instruct) through local Ollama for screenshot understanding and step selection.
• NVIDIA NeMo Parakeet TDT 0.6B v3, INT8, through onnx-asr for local English speech recognition and the ‘Hey Turo’ wake phrase.
• Kokoro v1.0 ONNX for local speech output, with Windows SAPI5 through pyttsx3 as a fallback.

FRAMEWORKS AND LIBRARIES
Python; PySide6/Qt for the desktop UI, tray icon, task card, and transparent overlay; Windows UI Automation through uiautomation for control names and bounding boxes; mss and Pillow for screenshots; keyboard for hotkeys; sounddevice and NumPy for audio; onnx-asr/ONNX Runtime and kokoro-onnx for speech inference; pyttsx3/comtypes for the Windows voice fallback; and the OpenAI Python client for OpenAI-compatible inference endpoints.

HOW LOCAL AI IS USED
A monitor screenshot is processed by Qwen locally. Its proposed target is refined using Windows UI Automation where possible, with a control-name reasoning fallback. Plain-text per-app skills provide task guidance. Screen capture, speech recognition, model inference, speech output, and the overlay run on the PC. Initial installation and model downloads require internet.

APIS AND CLOUD SERVICES
The default inference endpoint is local Ollama at localhost:11434/v1; use of the OpenAI client does not require the OpenAI cloud. The code also includes an optional, user-triggered OpenAI-compatible cloud endpoint configured through environment variables. When used, the question, screenshot, and relevant task/app context are sent to that configured provider. There is no automatic cloud fallback. No specific hosted provider is claimed for the local demo.

AI DEVELOPMENT TOOLS
Claude for planning, the build guide, and starter code; OpenAI Codex for project inspection and submission drafting.

EXISTING CODE AND ASSETS
The application is a custom hackathon implementation using existing open-source packages and pretrained model/voice assets listed above. The concept is inspired by Clicky (heyclicky.com); project instructions prohibit copying or cloning its code. Parakeet model files are reused from an existing local Handy installation.

PROTOTYPE LIMITATIONS
Windows-only; guidance depends on model accuracy and visible app controls. English voice recognition is used, so Taglish voice accuracy is not claimed. Agent mode has a six-step limit, an Esc stop, and a risky-control-name check; these are heuristic guards. For text-entry steps it leaves Enter/Send to the user. No universal app coverage or benchmark result is claimed.
