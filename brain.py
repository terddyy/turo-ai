import json
import time

from openai import OpenAI

from config import BASE_URL, CLOUD_API_KEY, CLOUD_BASE_URL, CLOUD_MODEL, MODEL, NO_THINK

client = OpenAI(base_url=BASE_URL, api_key="local")
cloud = OpenAI(base_url=CLOUD_BASE_URL, api_key=CLOUD_API_KEY) if CLOUD_API_KEY else None

SYSTEM = """You are Turo, an on-screen tutor for Windows apps.
The user asks how to do something in the app on their screen.
You receive a numbered list of the controls that are visible right now.
Pick the ONE control the user should click next.
Reply with JSON only: {"id": number, "say": string, "done": boolean}
- id: the number of the control to click, or -1 if no listed control fits.
- say: one short sentence telling the user what to click and why. Use the user's language. If they wrote Taglish, answer in Taglish.
- done: true only when the task is finished after this click.
Never invent a control that is not in the list.
How to choose:
- Features live on ribbon tabs. If the feature is not in the list, pick the TabItem whose tab holds it.
- A TabItem marked (selected) is already open. Never pick it again; pick a control on it instead.
- If a dropdown is open, pick the matching item inside it.

Example 1. Question: "How do I insert a table?" in Word, Home tab selected.
Controls include "12 | TabItem | Insert". Reply: {"id": 12, "say": "Click the Insert tab, where the Table button is.", "done": false}
Next screen: "12 | TabItem (selected) | Insert", "40 | MenuItem | Table". Reply: {"id": 40, "say": "Click Table, then pick the size you want.", "done": true}
Example 2. Question: "Paano mag-sort ng A to Z?" in Excel, Home tab selected.
Controls include "33 | TabItem | Data". Reply: {"id": 33, "say": "I-click ang Data tab, nandoon ang Sort.", "done": false}"""

FALLBACK_SAY = "I couldn't find that on screen. Try asking another way."


def _parse(text):
    # Reasoning can leak before the JSON, so keep only the outermost {...}.
    start, end = text.find("{"), text.rfind("}")
    try:
        data = json.loads(text[start:end + 1]) if start != -1 and end > start else {}
    except json.JSONDecodeError:
        data = {}
    try:
        step_id = int(data.get("id", -1))
    except (TypeError, ValueError):
        step_id = -1
    say = str(data.get("say") or "").strip() or FALLBACK_SAY
    return {"id": step_id, "say": say, "done": data.get("done") is True}


PLAN_SYSTEM = """You are Turo, an expert tutor for Windows apps (Office, File Explorer, Settings).
Give the exact sequence of on-screen controls to click to do the user's task, starting from the app's
normal screen. Use the control names exactly as they appear in the app (ribbon tab, button, menu item).
Reply with JSON only: {"steps": [{"click": string, "say": string}]}
- click: the visible name of the control, e.g. "Insert", "Table".
- say: one short sentence telling the user to click it. Use the user's language; if they wrote Taglish, answer in Taglish.
At most 5 steps."""

_plans = {}   # (question, app) -> steps; planned once, matched against the screen every step


def _chat(system, user, use_cloud=False):
    extra = {"reasoning_effort": "none"} if NO_THINK and not use_cloud else {}
    resp = (cloud if use_cloud else client).chat.completions.create(
        model=CLOUD_MODEL if use_cloud else MODEL,
        temperature=0,
        response_format={"type": "json_object"},
        messages=[{"role": "system", "content": system},
                  {"role": "user", "content": user}],
        **extra,
    )
    return resp.choices[0].message.content or ""


def _norm(name):
    return " ".join(name.lower().replace("...", "").replace("&", "and").split())


def _plan(question, app_title, skill=""):
    app = app_title.rsplit(" - ", 1)[-1]   # "Book1 - Excel" -> "Excel"
    key = (question, app)
    if key not in _plans:
        text = _chat(PLAN_SYSTEM + (f"\n\n{skill}" if skill else ""), f"App: {app}\nTask: {question}")
        start, end = text.find("{"), text.rfind("}")
        try:
            steps = json.loads(text[start:end + 1]).get("steps", [])
            _plans[key] = [s for s in steps if isinstance(s, dict) and str(s.get("click", "")).strip()]
        except (json.JSONDecodeError, AttributeError):
            _plans[key] = []
        print(f"[brain] plan: {[s['click'] for s in _plans[key]]}")
    return _plans[key]


def _match(plan, items):
    # The furthest plan step that is on screen and not already open is the next click.
    for n in range(len(plan) - 1, -1, -1):
        want = _norm(str(plan[n]["click"]))
        for exact in (True, False):
            for i in items:
                have = _norm(i["name"])
                if "(selected)" in i["type"]:
                    continue
                if have == want if exact else have.startswith(want):
                    say = str(plan[n].get("say") or "").strip() or FALLBACK_SAY
                    return {"id": i["id"], "say": say, "done": n == len(plan) - 1}
    return None


def _pick(question, app_title, items, history, use_cloud=False):
    controls = "\n".join(f'{i["id"]} | {i["type"]} | {i["name"]}' for i in items)
    shown = "\n".join(f"- {h}" for h in history) or "none"
    user = (f"Question: {question}\nApp window: {app_title}\n"
            f"Steps already shown:\n{shown}\n\nControls:\n{controls}")
    return _parse(_chat(SYSTEM, user, use_cloud))


VISION_SYSTEM = """You are Turo, a friendly tutor who teaches people how to use any app on Windows by looking at
their screen. You see a screenshot of the user's screen.
First look carefully: which app or website is open, what tab, panel or menu is showing, what is already done.
Then give the ONE next step. If an app SKILL is given below, use its layout and recipes to plan the steps,
but only pick what is actually visible in the screenshot.

Reply with JSON only:
{"action": "click" | "type" | "explain", "bbox_2d": [x1, y1, x2, y2], "label": string, "text": string,
 "say": string, "done": boolean}
- action "click": bbox_2d is the box around the element to click; label is its visible text or icon name.
- action "type": bbox_2d is the text box to type into; text is a good, specific example the user can type
  (for prompting tasks, write a clear prompt that shows good practice).
- action "explain": the question needs an answer, not a click (e.g. "how do I write a good prompt?");
  bbox_2d is []. say holds the answer in up to two short sentences.
- bbox_2d uses a 0-1000 grid over the screenshot (0,0 = top-left, 1000,1000 = bottom-right).
- say: one short, friendly sentence telling the user what to do and why. Use the user's language.
- done: true only when the task is finished after this step.
Only pick things visible in the screenshot. If the button you need is already visible (for example on the tab
that is open now), pick it directly. If it is hidden, pick the tab or menu that opens it.
Do not repeat a step listed in "Steps already shown"."""


def locate(question, app_title, image_b64, history, use_cloud=False, skill=""):
    """Main path: the vision model reads the screenshot. Returns action, box center in 0-1000 (or None),
    label, text to type, say, done."""
    shown = "\n".join(f"- {h}" for h in history) or "none"
    text = f"Task: {question}\nApp in front: {app_title}\nSteps already shown:\n{shown}"
    content = [{"type": "image_url", "image_url": {"url": f"data:image/jpeg;base64,{image_b64}"}},
               {"type": "text", "text": text}]
    t = time.time()
    system = VISION_SYSTEM + (f"\n\n{skill}" if skill else "")
    raw = _chat(system, content, use_cloud)
    start, end = raw.find("{"), raw.rfind("}")
    point, data = None, {}
    try:
        data = json.loads(raw[start:end + 1]) if start != -1 and end > start else {}
        box = [float(v) for v in data.get("bbox_2d") or []]
        if len(box) == 4 and all(0 <= v <= 1000 for v in box):
            point = ((box[0] + box[2]) / 2, (box[1] + box[3]) / 2)
        elif len(box) == 2 and all(0 <= v <= 1000 for v in box):
            point = (box[0], box[1])
    except (json.JSONDecodeError, TypeError, ValueError, AttributeError):
        data = data if isinstance(data, dict) else {}
    action = str(data.get("action") or "").lower()
    if action not in ("click", "type", "explain"):
        action = "click" if point else "explain"
    say = str(data.get("say") or "").strip() or FALLBACK_SAY
    reply = {"action": action, "point": point, "label": str(data.get("label") or "").strip(),
             "text": str(data.get("text") or "").strip(), "say": say, "done": data.get("done") is True}
    print(f"[brain] vision {time.time() - t:.1f}s {reply}")
    return reply


def next_step(question, app_title, items, history, use_cloud=False, skill=""):
    t = time.time()
    if use_cloud and cloud:   # only ever reached after the user pressed the cloud key
        reply = _pick(question, app_title, items, history, use_cloud=True)
    else:
        reply = _match(_plan(question, app_title, skill), items) or _pick(question, app_title, items, history)
    print(f"[brain] {time.time() - t:.1f}s {reply}")
    return reply


if __name__ == "__main__":
    demo = [{"id": 1, "type": "TabItem", "name": "Home"},
            {"id": 2, "type": "TabItem", "name": "View"},
            {"id": 3, "type": "Button", "name": "Bold"}]
    print(next_step("paano mag-freeze ng top row?", "Book1 - Excel", demo, []))
