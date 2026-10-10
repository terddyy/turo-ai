import base64
import ctypes
import ctypes.wintypes
import io
import math
import re
import time
import unicodedata
import uuid

import mss
import uiautomation as auto
from uiautomation.uiautomation import _AutomationClient
from PIL import Image

from turo.config import MAX_ITEMS

CLICKABLE = {"ButtonControl", "SplitButtonControl", "MenuItemControl", "TabItemControl",
             "CheckBoxControl", "RadioButtonControl", "ComboBoxControl", "EditControl",
             "HyperlinkControl", "ListItemControl"}
SKIP = {"DataGridControl", "TableControl"}   # spreadsheet cells: thousands of items


def _clean(name):
    # Drop invisible format chars (e.g. U+202A in Excel's file names): they waste prompt tokens.
    return "".join(c for c in name if unicodedata.category(c) != "Cf").strip()


def _walk(ctrl, depth, items, max_items, max_depth):
    if depth > max_depth:
        return
    try:
        children = ctrl.GetChildren()
    except Exception:   # element vanished mid-scan (menu closed, etc.)
        return
    for child in children:
        if len(items) >= max_items:
            return
        try:
            kind = child.ControlTypeName
            if kind in SKIP:
                continue
            if child.IsOffscreen:
                continue
            name = _clean(child.Name) if kind in CLICKABLE else ""
            if name and child.IsEnabled:
                r = child.BoundingRectangle
                if r.width() > 0 and r.height() > 0:
                    # The model needs to know which ribbon tab is already open.
                    selected = kind == "TabItemControl" and child.GetSelectionItemPattern().IsSelected
                    items.append({
                        "id": len(items) + 1,
                        "type": kind.replace("Control", "") + (" (selected)" if selected else ""),
                        "name": name[:60],
                        "rect": (r.left, r.top, r.right, r.bottom),
                    })
        except Exception:
            continue
        _walk(child, depth + 1, items, max_items, max_depth)


# --- Chromium / Electron (Chrome, Edge, Claude, ChatGPT, VS Code...) ----------------------------------
# Their web content sits 20-40 levels deep (the walk stops at 16) and is only built once a screen-reader-style
# client asks for IAccessible2 (measured in Chrome: 38 controls before, 273 after, within 0.3 s).
_nudged = set()


class _GUID(ctypes.Structure):
    _fields_ = [("a", ctypes.wintypes.DWORD), ("b", ctypes.wintypes.WORD), ("c", ctypes.wintypes.WORD),
                ("d", ctypes.c_ubyte * 8)]


def _guid(text):
    g = _GUID()
    ctypes.memmove(ctypes.byref(g), uuid.UUID(text).bytes_le, 16)
    return g


IID_IACCESSIBLE = _guid("618736E0-3C3D-11CF-810C-00AA00389B71")
IID_ISERVICEPROVIDER = _guid("6D5140C1-7436-11CE-8034-00AA006009FA")
IID_IACCESSIBLE2 = _guid("E89F726E-C4F4-4C19-BB19-B647D7FA8478")


def _com(ptr, index, *argtypes):
    vtable = ctypes.cast(ptr, ctypes.POINTER(ctypes.POINTER(ctypes.c_void_p))).contents
    return ctypes.WINFUNCTYPE(ctypes.HRESULT, ctypes.c_void_p, *argtypes)(vtable[index])


def _wake_chromium(hwnd):
    """Ask the window for IAccessible2 once, so Chromium builds the page's controls. True if just asked."""
    if hwnd in _nudged:
        return False
    _nudged.add(hwnd)
    ctypes.windll.ole32.CoInitialize(None)   # already initialized on UIA threads: harmless
    acc, provider, ia2 = ctypes.c_void_p(), ctypes.c_void_p(), ctypes.c_void_p()
    try:
        if ctypes.windll.oleacc.AccessibleObjectFromWindow(hwnd, 0xFFFFFFFC, ctypes.byref(IID_IACCESSIBLE),
                                                           ctypes.byref(acc)) != 0:   # OBJID_CLIENT
            return False
        _com(acc, 0, ctypes.POINTER(_GUID), ctypes.POINTER(ctypes.c_void_p))(
            acc, ctypes.byref(IID_ISERVICEPROVIDER), ctypes.byref(provider))
        _com(provider, 3, ctypes.POINTER(_GUID), ctypes.POINTER(_GUID), ctypes.POINTER(ctypes.c_void_p))(
            provider, ctypes.byref(IID_IACCESSIBLE), ctypes.byref(IID_IACCESSIBLE2), ctypes.byref(ia2))
        return True
    except OSError:   # not Chromium after all, or it refused: the bulk scan still finds what is there
        return False
    finally:
        for ptr in (ia2, provider, acc):
            if ptr.value:
                _com(ptr, 2)(ptr)   # IUnknown::Release


def _bulk(win, items, max_items):
    """All visible clickable controls in one cross-process call (~0.2 s for 1,200 nodes; the walk needs 3 s)."""
    uia = _AutomationClient.instance().IUIAutomation
    prop, kinds = auto.PropertyId, [getattr(auto.ControlType, k) for k in sorted(CLICKABLE)]
    cond = uia.CreateAndCondition(
        uia.CreateOrConditionFromArray([uia.CreatePropertyCondition(prop.ControlTypeProperty, k) for k in kinds]),
        uia.CreatePropertyCondition(prop.IsOffscreenProperty, False))
    cache = uia.CreateCacheRequest()
    for p in (prop.NameProperty, prop.ControlTypeProperty, prop.BoundingRectangleProperty, prop.IsEnabledProperty,
              prop.SelectionItemIsSelectedProperty):
        cache.AddProperty(p)
    found = win.Element.FindAllBuildCache(4, cond, cache)   # 4 = TreeScope_Descendants
    rows = []
    for n in range(found.Length):
        e = found.GetElement(n)
        name, r = _clean(e.CachedName or ""), e.CachedBoundingRectangle
        if name and e.CachedIsEnabled and r.right - r.left >= 4 and r.bottom - r.top >= 4:
            kind = auto.ControlTypeNames[e.CachedControlType]
            selected = kind == "TabItemControl" and bool(e.GetCachedPropertyValue(prop.SelectionItemIsSelectedProperty))
            rows.append((kind.replace("Control", "") + (" (selected)" if selected else ""), name[:60],
                         (r.left, r.top, r.right, r.bottom)))
    room = max_items - len(items)
    if len(rows) > room:   # keep both ends: the sidebar/toolbar comes first, the message box last
        rows = rows[:room // 2] + rows[len(rows) - (room - room // 2):]
    for kind, name, rect in rows:
        items.append({"id": len(items) + 1, "type": kind, "name": name, "rect": rect})


def list_controls(handle=None, max_items=MAX_ITEMS, max_depth=16):
    win = auto.ControlFromHandle(handle) if handle else auto.GetForegroundControl().GetTopLevelControl()
    pid = win.ProcessId
    # Open menus are separate top-level windows of the same app, so scan those too.
    # Scan them before the main window so a full ribbon can't push menu items past max_items.
    roots = [w for w in auto.GetRootControl().GetChildren()
             if w.ProcessId == pid and w.NativeWindowHandle != win.NativeWindowHandle]
    roots.append(win)
    items = []
    for root in roots:
        if root.ClassName.startswith("Chrome_WidgetWin"):
            if _wake_chromium(root.NativeWindowHandle):
                time.sleep(0.3)   # Chromium fills in the page tree right after the first request
            try:
                _bulk(root, items, max_items)
            except Exception as err:   # fall back to the walk rather than fail the step
                print("[screen] bulk scan failed:", err)
                _walk(root, 0, items, max_items, max_depth)
        else:   # Office, File Explorer, Settings: the proven walk
            _walk(root, 0, items, max_items, max_depth)
    return win.Name, items


def exe_of(handle):
    """Program file name of a window, e.g. 'EXCEL.EXE' (used to pick the app's skill)."""
    pid = ctypes.wintypes.DWORD()
    ctypes.windll.user32.GetWindowThreadProcessId(handle, ctypes.byref(pid))
    proc = ctypes.windll.kernel32.OpenProcess(0x1000, False, pid.value)   # QUERY_LIMITED_INFORMATION
    if not proc:
        return ""
    try:
        buf, size = ctypes.create_unicode_buffer(520), ctypes.wintypes.DWORD(520)
        ok = ctypes.windll.kernel32.QueryFullProcessImageNameW(proc, 0, buf, ctypes.byref(size))
        return buf.value.rsplit("\\", 1)[-1] if ok else ""
    finally:
        ctypes.windll.kernel32.CloseHandle(proc)


def grab(handle, max_side=1280):
    """Screenshot of the whole monitor the app is on (so open menus are included), as base64 JPEG,
    plus (left, top, width, height) to map the model's 0-1000 grid back to screen px."""
    win = auto.ControlFromHandle(handle) if handle else auto.GetForegroundControl().GetTopLevelControl()
    r = win.BoundingRectangle
    cx, cy = (r.left + r.right) // 2, (r.top + r.bottom) // 2
    with mss.MSS() as s:
        mons = s.monitors[1:]
        mon = next((m for m in mons if m["left"] <= cx < m["left"] + m["width"]
                    and m["top"] <= cy < m["top"] + m["height"]), mons[0])
        shot = s.grab(mon)
    img = Image.frombytes("RGB", shot.size, shot.rgb)
    img.thumbnail((max_side, max_side))
    buf = io.BytesIO()
    img.save(buf, "JPEG", quality=85)
    return base64.b64encode(buf.getvalue()).decode(), (mon["left"], mon["top"], mon["width"], mon["height"])


def _norm(name):
    return " ".join(name.lower().replace("...", "").replace("&", "and").split())


LABEL_NOISE = re.compile(r"\s+(tab|button|icon|menu|option|link|box|field|dropdown)$", re.IGNORECASE)
LABEL_WORDS = {"click", "select", "choose", "the", "a", "an", "in", "on", "from", "or", "and",
               "option", "button", "icon", "menu", "dropdown", "tab", "link", "field", "box"}


def label_score(label, name):
    """Match visible names without confusing a descriptive label with the adjacent menu row."""
    if not label or not name:
        return 0
    if _norm(clean_label(label)) == _norm(name):
        return 1
    if _norm(clean_label(label)) in {"+", "plus", "plus sign"} and re.search(r"\b(add|attach)\b", name.lower()):
        return 0.7
    def words(text):
        return {w[:-1] if len(w) > 4 and w.endswith("s") else w
                for w in re.findall(r"[a-z0-9]+", text.lower()) if w not in LABEL_WORDS}
    want, have = words(label), words(name)
    if not want or not have:
        return 0
    if want == have:
        return 0.95
    if want <= have:
        return 0.8 * len(want) / len(have)
    if have < want and min(want, key=label.lower().find) in have:
        # Short accessible name for a longer visible label: "Add" for "Add files or connectors".
        return 0.5 * len(have) / len(want)
    return 0


def _distance(x, y, rect):
    l, t, r, b = rect
    return math.hypot(max(l - x, 0, x - r), max(t - y, 0, y - b))


def _nearby_controls(x, y):
    """Inspect a small local subtree when the full window scan stopped before a popup/composer."""
    items = []
    try:
        ctrl = auto.ControlFromPoint(int(x), int(y))
        for _ in range(3):
            if ctrl is None:
                break
            if (ctrl.ControlTypeName in CLICKABLE and ctrl.Name and ctrl.IsEnabled and not ctrl.IsOffscreen):
                r = ctrl.BoundingRectangle
                if r.width() > 0 and r.height() > 0:
                    items.append({"id": len(items)+1, "type": ctrl.ControlTypeName.replace("Control", ""),
                                  "name": _clean(ctrl.Name), "rect": (r.left,r.top,r.right,r.bottom)})
            _walk(ctrl, 0, items, 60, 2)
            if len(items) >= 60:
                break
            ctrl = ctrl.GetParentControl()
    except Exception:
        pass
    return items


def resolve_target(x, y, label, items, reach=160, action="click", box=None, control_id=None):
    """Return (rect, visible name, verified). Never silently substitute an unrelated control."""
    label = clean_label(label)
    usable = [i for i in items if "(selected)" not in i["type"] and
              (action != "type" or i["type"] in {"Edit", "Document", "Group", "ComboBox"})]
    if control_id is not None:
        chosen = next((i for i in usable if i["id"] == control_id), None)
        if chosen and (not label or label_score(label, chosen["name"]) > 0):
            return chosen["rect"], chosen["name"], True
    nearby = [i for i in usable if _distance(x, y, i["rect"]) <= reach and label_score(label, i["name"]) > 0]
    if not nearby:
        nearby = [i for i in _nearby_controls(x, y) if _distance(x, y, i["rect"]) <= reach
                  and label_score(label, i["name"]) > 0 and "(selected)" not in i["type"]
                  and (action != "type" or i["type"] in {"Edit", "Document", "Group", "ComboBox"})]
    if nearby:
        best = max(nearby, key=lambda i: (label_score(label, i["name"]), i["type"] == "TabItem",
                                         -_distance(x, y, i["rect"])))
        return best["rect"], best["name"], True
    hit = _clickable_at(int(x), int(y), typing=action == "type")
    if hit:
        rect, name = hit
        if name and label_score(label, name) > 0:
            return rect, name, True
        # A named neighboring element contradicts the model. Do not point there as if it matched.
        if name:
            return None, label, False
    # Some canvas/custom apps expose no accessibility labels: preserve the actual visual box,
    # mark it as an estimate, and never permit agent clicks based on it.
    return box, label, False


def snap(x, y, label, items, reach=160, action="click"):
    return resolve_target(x, y, label, items, reach, action)[:2]


def verify_target(rect, label, action="click"):
    l, t, r, b = rect
    hit = _clickable_at(int((l + r) / 2), int((t + b) / 2), typing=action == "type")
    return bool(hit and label_score(label, hit[1]) > 0)


def clean_label(label):
    """ "View tab" -> "View": the name as it appears on screen (used for snapping and for memory)."""
    return LABEL_NOISE.sub("", (label or "").strip(" '\"")).strip()


def find_named(label, items):
    """The visible control with exactly this name (a ribbon tab first), or None."""
    named = [i for i in items if _norm(i["name"]) == _norm(clean_label(label)) and "(selected)" not in i["type"]]
    tabs = [i for i in named if i["type"] == "TabItem"]
    choices = tabs or named
    return choices[0] if len(choices) == 1 else None


TYPABLE = {"EditControl", "ComboBoxControl", "DocumentControl", "GroupControl"}


def _clickable_at(x, y, typing=False):
    """The control Windows reports under the point, climbing to the nearest clickable or typable parent.
    Works inside browsers, where scanning the whole tree is too slow."""
    try:
        kinds, max_w, max_h = (TYPABLE, 1400, 400) if typing else (CLICKABLE, 500, 160)
        ctrl = auto.ControlFromPoint(x, y)
        for _ in range(5):
            if ctrl is None:
                break
            r = ctrl.BoundingRectangle
            if (ctrl.ControlTypeName in kinds and ctrl.IsEnabled and not ctrl.IsOffscreen
                    and 0 < r.width() <= max_w and 0 < r.height() <= max_h
                    and r.left <= x <= r.right and r.top <= y <= r.bottom):
                return (r.left, r.top, r.right, r.bottom), _clean(ctrl.Name or "")
            ctrl = ctrl.GetParentControl()
    except Exception:
        pass
    return None


if __name__ == "__main__":
    time.sleep(3)   # switch to Excel now
    t = time.time()
    title, items = list_controls()
    print(title, len(items), f"{time.time() - t:.1f}s")
    for it in items:
        print(it["id"], it["type"], it["name"], it["rect"])
