import base64
import ctypes
import ctypes.wintypes
import io
import math
import re
import time
import unicodedata

import mss
import uiautomation as auto
from PIL import Image

from config import MAX_ITEMS

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
            name = _clean(child.Name) if kind in CLICKABLE else ""
            if name:
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


def snap(x, y, label, items, reach=160, action="click"):
    """Turn the model's point into an exact box. Prefer a control named like the model's label
    near the point (fixes small aim errors), else the smallest control under the point.
    Returns (rect, name) or a small box around the point when the app exposes no controls."""
    label = LABEL_NOISE.sub("", label or "").strip(" '\"")
    if label:
        named = [i for i in items if _norm(i["name"]) == _norm(label)]
        # "View" can be a ribbon tab and a checkbox; a tutorial means the tab (vision mixed them up in testing).
        tabs = [i for i in named if i["type"] == "TabItem"]
        if tabs:
            return tabs[0]["rect"], tabs[0]["name"]
        if named:
            def dist(i):
                l, t, r, b = i["rect"]
                return math.hypot((l + r) / 2 - x, (t + b) / 2 - y)
            best = min(named, key=dist)
            if dist(best) <= reach:
                return best["rect"], best["name"]
    hit = _clickable_at(int(x), int(y), typing=action == "type")
    if hit:
        return hit
    return (x - 20, y - 20, x + 20, y + 20), label


TYPABLE = CLICKABLE | {"DocumentControl", "GroupControl"}   # chat boxes are often Document/Group in browsers


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
            if (ctrl.ControlTypeName in kinds and 0 < r.width() <= max_w and 0 < r.height() <= max_h
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
