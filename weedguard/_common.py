"""Shared plumbing for WeedGuard: paths, the state store and box geometry.

Every function here starts with an underscore on purpose: Synapse only offers public
functions as building blocks, and none of these should be called by an agent directly.
The geometry helpers are copied from robot/weed_robot.py (that file parses command-line
arguments when imported, so it cannot be imported as a library).
"""
import json
import os
import sys
import threading
import time
from datetime import datetime

HERE = os.path.dirname(os.path.abspath(__file__))
REPO = os.path.dirname(HERE)
if REPO not in sys.path:
    sys.path.insert(0, REPO)

MODEL_DIRS = {
    "yolo26n": os.path.join(REPO, "models", "maize_weed_yolo26n_ncnn_416"),
    "yolo11n": os.path.join(REPO, "models", "maize_weed_yolo11n_ncnn_416"),
}
FIELD_FILE = os.path.join(HERE, "field.json")

# Robot settings, same defaults as robot/weed_robot.py
PROTECT_MARGIN = 0.15      # each maize box grows by this fraction on every side
MIN_AREA = 0.0005          # ignore boxes smaller than this fraction of the frame
MAX_AREA = 0.5             # ignore boxes larger than this fraction of the frame
MERGE_OVERLAP = 0.5        # merge same-class boxes that overlap more than this

# Image quality limits (variance of the Laplacian, mean grey level 0-255)
MIN_SHARPNESS = 150.0
MIN_BRIGHTNESS = 45.0
MAX_BRIGHTNESS = 230.0

CONFIRM_TTL_S = 600        # a confirmation code is valid for 10 minutes

_lock = threading.Lock()
_detectors = {}


def _state_dir():
    d = os.environ.get("WEEDGUARD_STATE") or os.path.join(HERE, "state")
    os.makedirs(d, exist_ok=True)
    return d


def _db_path():
    return os.path.join(_state_dir(), "db.json")


def _load_db():
    p = _db_path()
    if os.path.exists(p):
        with open(p) as f:
            return json.load(f)
    return {"scans": {}, "plans": {}, "confirmations": {}, "actions": [], "captures": {}, "counter": 0}


def _save_db(db):
    p = _db_path()
    tmp = p + ".tmp"
    with open(tmp, "w") as f:
        json.dump(db, f, indent=1)
    os.replace(tmp, p)


def _next_id(db, prefix):
    db["counter"] = db.get("counter", 0) + 1
    return f"{prefix}{db['counter']:04d}"


def _now():
    return time.time()


def _stamp(t=None):
    return datetime.fromtimestamp(t or time.time()).isoformat(timespec="seconds")


def _load_field():
    with open(FIELD_FILE) as f:
        return json.load(f)


def _detector(model_name):
    if model_name not in MODEL_DIRS:
        raise ValueError(f"unknown model '{model_name}', choose one of {sorted(MODEL_DIRS)}")
    if model_name not in _detectors:
        from detector import Detector   # the NCNN detector used by the web app
        _detectors[model_name] = Detector(MODEL_DIRS[model_name])
    return _detectors[model_name]


# ---------------------------------------------------------------- geometry (from weed_robot.py)
def _expand(b, m, w, h):
    bw, bh = b[2] - b[0], b[3] - b[1]
    return [max(0, b[0] - m * bw), max(0, b[1] - m * bh), min(w, b[2] + m * bw), min(h, b[3] + m * bh)]


def _overlaps(a, b):
    return not (a[2] < b[0] or b[2] < a[0] or a[3] < b[1] or b[3] < a[1])


def _merge_boxes(dets, thr):
    """Keep the most confident box; drop same-class boxes that overlap it too much."""
    keep = []
    for b, c in sorted(dets, key=lambda d: -d[1]):
        ok = True
        for k, _ in keep:
            iw = max(0, min(b[2], k[2]) - max(b[0], k[0]))
            ih = max(0, min(b[3], k[3]) - max(b[1], k[1]))
            inter = iw * ih
            if inter == 0:
                continue
            a1 = (b[2] - b[0]) * (b[3] - b[1])
            a2 = (k[2] - k[0]) * (k[3] - k[1])
            if inter / (a1 + a2 - inter) > thr or inter / min(a1, a2) > max(thr, 0.7):
                ok = False
                break
        if ok:
            keep.append((b, c))
    return keep


def _point_in_any_zone(x, y, zones):
    """x, y and zones in normalised 0-1 image coordinates."""
    return any(z[0] <= x <= z[2] and z[1] <= y <= z[3] for z in zones)
