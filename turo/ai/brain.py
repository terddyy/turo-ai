import json
import threading
import time

from openai import OpenAI

from turo.config import BASE_URL, CLOUD_API_KEY, CLOUD_BASE_URL, CLOUD_MODEL, MODEL, NO_THINK

client = OpenAI(base_url=BASE_URL, api_key="local")
cloud = OpenAI(base_url=CLOUD_BASE_URL, api_key=CLOUD_API_KEY) if CLOUD_API_KEY else None

# The laptop GPU powers down after ~5 s idle; waking it adds ~2.5 s to the next call (measured: 3.5 s vs 1.1 s).
# While a session is active, a 1-token ping every 3 s keeps it awake. The ping reuses the last system prompt
# so Ollama's cached prompt prefix survives.
_warm_until = 0.0
_last_system = "ok"


def _warm_loop():
    while time.time() < _warm_until:
        try:
            client.chat.completions.create(model=MODEL, max_tokens=1, messages=[
                {"role": "system", "content": _last_system}, {"role": "user", "content": "ok"}])
        except Exception:   # Ollama down: the ready-check reports it, nothing to do here
            return
        time.sleep(3)


def keep_warm(seconds=60):
    """Call when the user starts interacting (hotkey, wake word, each step)."""
    global _warm_until
    idle = time.time() >= _warm_until
    _warm_until = max(_warm_until, time.time() + seconds)
    if idle:
        threading.Thread(target=_warm_loop, daemon=True).start()

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
{"action": "click" | "type" | "explain", "control_id": number | null, "bbox_2d": [x1, y1, x2, y2], "label": string, "text": string,
 "say": string, "done": boolean}
- action "click": bbox_2d is the box around the element to click; label is its visible text or icon name.
- action "type": bbox_2d is the text box to type into; text is a good, specific example the user can type
  (for prompting tasks, write a clear prompt that shows good practice).
- action "explain": the question needs an answer, not a click (e.g. "how do I write a good prompt?");
  bbox_2d is []. say holds the answer in up to two short sentences.
- bbox_2d uses a 0-1000 grid over the screenshot (0,0 = top-left, 1000,1000 = bottom-right).
- Visible accessibility controls may be listed with IDs and their boxes on the same grid.
  When the target appears in that list, return its control_id and copy its visible name into label exactly.
  Otherwise use control_id null. Never invent an ID or choose a different control just because it is nearby.
- For an icon-only menu opener, name the visible icon (e.g. "+"), not the hidden final menu item.
  If the requested item is not visible, first open its menu. If a menu is already open, pick its visible row.
- Ignore Turo's blue pointer, its instruction bubble, and task card; those are overlays, not app controls.
- text: "" unless action is "type".
- If the task is not something to do on this screen (small talk, a greeting, or too unclear to act on), use
  action "explain" and in say ask briefly and kindly what they want to do.
- Lines starting with 'User replied:' are what the user told you about the last step. Believe them.
- say: one short, friendly sentence telling the user what to do and why. Use the user's language.
- done: true only when the task is finished after this step.
Only pick things visible in the screenshot. If the button you need is already visible (for example on the tab
that is open now), pick it directly. If it is hidden, pick the tab or menu that opens it.
Previous instructions are history, not proof that the user completed them. Follow the current screen;
if a menu did not open yet, it is OK to point to its opener again."""


def locate(question, app_title, image_b64, history, use_cloud=False, skill="", context="", memory="",
           items=None, viewport=None, avoid=""):
    """Main path: the vision model reads the screenshot. Returns action, box center in 0-1000 (or None),
    label, text to type, say, done. avoid: a control the user already clicked (breaks repeat loops)."""
    global _last_system
    shown = "\n".join(f"- {h}" for h in history) or "none"
    text = f"Task: {question}\nApp in front: {app_title}\nSteps already shown:\n{shown}"
    if avoid:
        text += (f"\nThe user already clicked \"{avoid}\" and that step is done. Do NOT point to \"{avoid}\" again: "
                 "give the next step toward the task on the current screen.")
    sent_ids = set()
    if memory:   # Turo's own memory: the click path that finished a similar task before
        text += f"\nThis worked before for a similar task in this app: {memory}. Follow it if it fits the screen."
    if context:   # a follow-up: the user's earlier question, for context only
        text += f"\nEarlier question in this conversation: {context}"
    if items and viewport:
        ml, mt, mw, mh = viewport
        visible = [i for i in items if i["rect"][0] < ml + mw and i["rect"][2] > ml and
                   i["rect"][1] < mt + mh and i["rect"][3] > mt]
        # Popup rows first; retain both the toolbar and composer when a long page fills the tree.
        menus = [i for i in visible if i["type"] == "MenuItem"]
        other = [i for i in visible if i not in menus]
        remaining = max(0, 40 - len(menus))
        front = (remaining + 1) // 2
        candidates = (menus + other[:front] + (other[-(remaining - front):] if remaining > front else []))[:40]
        candidates = list({i["id"]: i for i in candidates}.values())
        sent_ids = {i["id"] for i in candidates}
        controls = []
        for i in candidates:
            l, t, r, b = i["rect"]
            box = [round(max(0, min(1000, v))) for v in
                   ((l-ml)*1000/mw, (t-mt)*1000/mh, (r-ml)*1000/mw, (b-mt)*1000/mh)]
            controls.append(f'{i["id"]} | {i["type"]} | {i["name"]} | {box}')
        text += "\nVisible controls (ID | type | exact name | bbox_2d):\n" + "\n".join(controls)
    content = [{"type": "image_url", "image_url": {"url": f"data:image/jpeg;base64,{image_b64}"}},
               {"type": "text", "text": text}]
    t = time.time()
    system = VISION_SYSTEM + (f"\n\n{skill}" if skill else "")
    if not use_cloud:
        _last_system = system
    raw = _chat(system, content, use_cloud)
    start, end = raw.find("{"), raw.rfind("}")
    point, valid_box, data = None, None, {}
    try:
        data = json.loads(raw[start:end + 1]) if start != -1 and end > start else {}
        box = [float(v) for v in data.get("bbox_2d") or []]
        if (len(box) == 4 and all(0 <= v <= 1000 for v in box)
                and box[0] < box[2] and box[1] < box[3]):
            valid_box = tuple(box)
            point = ((box[0] + box[2]) / 2, (box[1] + box[3]) / 2)
        elif len(box) == 2 and all(0 <= v <= 1000 for v in box):
            point = (box[0], box[1])
    except (json.JSONDecodeError, TypeError, ValueError, AttributeError):
        data = data if isinstance(data, dict) else {}
    say = str(data.get("say") or "").strip() or FALLBACK_SAY
    control_id = data.get("control_id")
    if isinstance(control_id, bool) or not isinstance(control_id, (int, str)):
        control_id = None
    else:
        try:
            control_id = int(control_id)
        except ValueError:
            control_id = None
    if control_id not in sent_ids:
        control_id = None
    action = str(data.get("action") or "").lower()
    if action not in ("click", "type", "explain"):
        action = "click" if point or control_id is not None else "explain"
    reply = {"action": action, "point": point, "label": str(data.get("label") or "").strip(),
             "box": valid_box, "control_id": control_id,
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
