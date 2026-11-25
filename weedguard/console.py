"""Robot operator console: shows approval codes, and the plan as a picture, to the farmer.

Run it in its own window next to the AI chat:
    python console.py
When the agent asks for approval, a line with a 4-digit code appears here and a picture of the plan opens:
green boxes and dashed safety zones around the maize, red crosses on the weeds that will be removed, and
orange crosses on the weeds that are skipped because they touch a safety zone. Reading the code to the agent
is how the farmer says "yes". The agent never sees the code itself.
Set WEEDGUARD_CONSOLE_NO_IMAGES=1 to show the text only.
"""
import json
import os
import re
import subprocess
import sys
import time

import cv2

from _common import _state_dir


def _dashed_rect(img, p1, p2, color, dash=8):
    x1, y1 = p1
    x2, y2 = p2
    for x in range(x1, x2, dash * 2):
        cv2.line(img, (x, y1), (min(x + dash, x2), y1), color, 1)
        cv2.line(img, (x, y2), (min(x + dash, x2), y2), color, 1)
    for y in range(y1, y2, dash * 2):
        cv2.line(img, (x1, y), (x1, min(y + dash, y2)), color, 1)
        cv2.line(img, (x2, y), (x2, min(y + dash, y2)), color, 1)


def _cross(img, x, y, color, size=9, thick=2):
    cv2.line(img, (x - size, y - size), (x + size, y + size), color, thick, cv2.LINE_AA)
    cv2.line(img, (x - size, y + size), (x + size, y - size), color, thick, cv2.LINE_AA)


def _approval_image(plan_id):
    """Draw the plan on the plot photo and return the path of the picture (or None)."""
    db_path = os.path.join(_state_dir(), "db.json")
    if not os.path.exists(db_path):
        return None
    db = json.load(open(db_path))
    plan = db["plans"].get(plan_id)
    if not plan:
        return None
    scan = db["scans"].get(plan["scan_id"])
    sel = db.get("selections", {}).get(plan["selection_id"])
    img = cv2.imread(scan["image_path"]) if scan else None
    if img is None or sel is None:
        return None
    h, w = img.shape[:2]
    px = lambda v, size: int(round(v * size))
    green, red, orange, white = (60, 200, 60), (40, 40, 230), (0, 165, 255), (255, 255, 255)
    for m, z in zip(scan["maize"], sel["zones"]):
        b = m["box"]
        cv2.rectangle(img, (px(b[0], w), px(b[1], h)), (px(b[2], w), px(b[3], h)), green, 2)
        _dashed_rect(img, (px(z[0], w), px(z[1], h)), (px(z[2], w), px(z[3], h)), green)
        cv2.putText(img, m["id"], (px(b[0], w) + 3, px(b[1], h) + 16), cv2.FONT_HERSHEY_SIMPLEX, 0.5, green, 2, cv2.LINE_AA)
    skipped = {s["id"] for s in sel["skipped"]}
    for wd in scan["weeds"]:
        b = wd["box"]
        x, y = px((b[0] + b[2]) / 2, w), px((b[1] + b[3]) / 2, h)
        _cross(img, x, y, orange if wd["id"] in skipped else red, size=11, thick=3)
    # title bar
    bar = 34
    out = cv2.copyMakeBorder(img, bar, 0, 0, 0, cv2.BORDER_CONSTANT, value=(30, 30, 30))
    text = (f"{plan_id}  plot {plan['plot_id']}:  remove {len(plan['actions'])} (red)   "
            f"skip {len(skipped)} near maize (orange)   maize safety zones (green)")
    cv2.putText(out, text, (8, 23), cv2.FONT_HERSHEY_SIMPLEX, 0.5, white, 1, cv2.LINE_AA)
    path = os.path.join(_state_dir(), "captures", f"{plan_id}_approval.jpg")
    cv2.imwrite(path, out)
    return path


def _open(path):
    try:
        if os.name == "nt":
            os.startfile(path)
        elif sys.platform == "darwin":
            subprocess.Popen(["open", path])
        else:
            subprocess.Popen(["xdg-open", path], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    except Exception:
        pass


def _follow():
    path = os.path.join(_state_dir(), "operator_console.log")
    show = os.environ.get("WEEDGUARD_CONSOLE_NO_IMAGES") != "1"
    print("WeedGuard operator console - waiting for approval requests (Ctrl+C to quit)\n", flush=True)
    pos = os.path.getsize(path) if os.path.exists(path) else 0
    while True:
        if os.path.exists(path):
            size = os.path.getsize(path)
            if size < pos:
                pos = 0
            if size > pos:
                with open(path) as f:
                    f.seek(pos)
                    for line in f.read().splitlines():
                        print("  >>> " + line, flush=True)
                        m = re.search(r"plan (PLAN\d+)", line)
                        if show and m:
                            pic = _approval_image(m.group(1))
                            if pic:
                                print(f"      plan picture: {pic}", flush=True)
                                _open(pic)
                    pos = f.tell()
        time.sleep(0.5)


if __name__ == "__main__":
    try:
        _follow()
    except KeyboardInterrupt:
        pass
