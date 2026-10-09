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


def _plan(question, app_title):
    app = app_title.rsplit(" - ", 1)[-1]   # "Book1 - Excel" -> "Excel"
    key = (question, app)
    if key not in _plans:
        text = _chat(PLAN_SYSTEM, f"App: {app}\nTask: {question}")
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


VISION_SYSTEM = """You are Turo, an on-screen tutor for Windows. You see a screenshot of the user's screen.
Look at it carefully: which app is open, which tab or menu is showing, what is already done.
Then find the ONE element the user should click next to do their task.
Reply with JSON only:
{"bbox_2d": [x1, y1, x2, y2], "label": string, "say": string, "done": boolean}
- bbox_2d: box around that element on a 0-1000 grid over the screenshot (0,0 = top-left, 1000,1000 = bottom-right).
  Use [] if the element is not visible anywhere.
- label: the element's visible text or name, e.g. "View", "Freeze Panes", "New folder".
- say: one short, friendly sentence telling the user what to click and why. Use the user's language.
- done: true only when the task is finished after this click.
Rules: tabs, menus and buttons must be visible in the screenshot to be picked. If the needed feature is not
visible, pick the tab or menu that opens it. Do not pick something the steps already shown say was clicked."""


def locate(question, app_title, image_b64, history, use_cloud=False):
    """Main path: the vision model reads the screenshot. Returns the box center in 0-1000, or None."""
    shown = "\n".join(f"- {h}" for h in history) or "none"
    text = f"Task: {question}\nApp in front: {app_title}\nSteps already shown:\n{shown}"
    content = [{"type": "image_url", "image_url": {"url": f"data:image/jpeg;base64,{image_b64}"}},
               {"type": "text", "text": text}]
    t = time.time()
    raw = _chat(VISION_SYSTEM, content, use_cloud)
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
        pass
    say = str(data.get("say") or "").strip() or FALLBACK_SAY
    reply = {"point": point, "label": str(data.get("label") or "").strip(), "say": say,
             "done": data.get("done") is True}
    print(f"[brain] vision {time.time() - t:.1f}s {reply}")
    return reply


def next_step(question, app_title, items, history, use_cloud=False):
    t = time.time()
    if use_cloud and cloud:   # only ever reached after the user pressed the cloud key
        reply = _pick(question, app_title, items, history, use_cloud=True)
    else:
        reply = _match(_plan(question, app_title), items) or _pick(question, app_title, items, history)
    print(f"[brain] {time.time() - t:.1f}s {reply}")
    return reply


if __name__ == "__main__":
    demo = [{"id": 1, "type": "TabItem", "name": "Home"},
            {"id": 2, "type": "TabItem", "name": "View"},
            {"id": 3, "type": "Button", "name": "Bold"}]
    print(next_step("paano mag-freeze ng top row?", "Book1 - Excel", demo, []))
