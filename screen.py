import base64
import io
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


def grab(handle, max_side=960):
    """Screenshot of the window as base64 JPEG, plus how to map image px back to screen px."""
    win = auto.ControlFromHandle(handle) if handle else auto.GetForegroundControl().GetTopLevelControl()
    r = win.BoundingRectangle
    box = {"left": r.left, "top": r.top, "width": max(r.width(), 1), "height": max(r.height(), 1)}
    with mss.MSS() as s:
        shot = s.grab(box)
    img = Image.frombytes("RGB", shot.size, shot.rgb)
    img.thumbnail((max_side, max_side))
    buf = io.BytesIO()
    img.save(buf, "JPEG", quality=80)
    return base64.b64encode(buf.getvalue()).decode(), (r.left, r.top, box["width"], box["height"])


if __name__ == "__main__":
    time.sleep(3)   # switch to Excel now
    t = time.time()
    title, items = list_controls()
    print(title, len(items), f"{time.time() - t:.1f}s")
    for it in items:
        print(it["id"], it["type"], it["name"], it["rect"])
