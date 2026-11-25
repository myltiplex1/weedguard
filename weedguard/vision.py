"""Looking at a plot photo: image quality check and maize/weed detection.

detect_plants() runs the same YOLO26n NCNN model and the same robot filters as
robot/weed_robot.py: per-class thresholds from robot_config.json, size limits and merging
of overlapping boxes so each plant gets one box.
"""
import os

import cv2

from _common import (MAX_AREA, MAX_BRIGHTNESS, MERGE_OVERLAP, MIN_AREA, MIN_BRIGHTNESS, MIN_SHARPNESS,
                     _detector, _load_db, _lock, _merge_boxes, _next_id, _now, _save_db, _state_dir)


def _quality(img):
    grey = cv2.cvtColor(img, cv2.COLOR_BGR2GRAY)
    sharp = float(cv2.Laplacian(grey, cv2.CV_64F).var())
    bright = float(grey.mean())
    problems = []
    if sharp < MIN_SHARPNESS:
        problems.append(f"too blurry (sharpness {sharp:.0f}, need at least {MIN_SHARPNESS:.0f}): clean the lens or slow down")
    if bright < MIN_BRIGHTNESS:
        problems.append(f"too dark (brightness {bright:.0f}, need at least {MIN_BRIGHTNESS:.0f}): wait for daylight or add a light")
    if bright > MAX_BRIGHTNESS:
        problems.append(f"overexposed (brightness {bright:.0f}): avoid direct glare")
    return {"ok": not problems, "sharpness": round(sharp, 1), "brightness": round(bright, 1), "problems": problems}


def check_image_quality(image_path: str) -> dict:
    """Check whether a plot photo is sharp and bright enough for the detector to be trusted.

    image_path: path returned by capture_plot_image.
    Returns {"ok": bool, "sharpness", "brightness", "problems": [str]}. If ok is False the
    robot must not act on this photo; tell the user the problem instead.
    """
    img = cv2.imread(image_path) if image_path and os.path.exists(image_path) else None
    if img is None:
        return {"ok": False, "sharpness": None, "brightness": None, "problems": [f"cannot read image '{image_path}'"]}
    return _quality(img)


def detect_plants(image_path: str, model_name: str = "yolo26n") -> dict:
    """Find every maize plant and weed in a plot photo with the robot's YOLO model.

    image_path: path returned by capture_plot_image. model_name: "yolo26n" (default) or "yolo11n".
    Returns {"ok": True, "scan_id", "plot_id", "maize_count", "weed_count", "maize": [...],
    "weeds": [...], "preview_path", "quality"}. Each plant is {"id", "conf", "box"} with box =
    [x1, y1, x2, y2] as fractions of the image (0-1). The scan_id is needed by
    select_weed_targets. Nothing on the farm changes when this runs.
    """
    img = cv2.imread(image_path) if image_path and os.path.exists(image_path) else None
    if img is None:
        return {"ok": False, "error_code": "bad_image", "message": f"cannot read image '{image_path}'"}
    det = _detector(model_name)
    h, w = img.shape[:2]
    maize, weeds = [], []
    for d in det.predict(img):
        b = d["box"]
        area = (b[2] - b[0]) * (b[3] - b[1]) / (w * h)
        if not (MIN_AREA <= area <= MAX_AREA):
            continue
        (maize if d["name"] == "maize" else weeds).append((b, d["conf"]))
    maize = _merge_boxes(maize, MERGE_OVERLAP)
    weeds = _merge_boxes(weeds, MERGE_OVERLAP)

    def _norm(items, prefix):
        out = []
        for i, (b, c) in enumerate(sorted(items, key=lambda t: (t[0][1], t[0][0])), 1):
            out.append({"id": f"{prefix}{i}", "conf": round(float(c), 3),
                        "box": [round(b[0] / w, 4), round(b[1] / h, 4), round(b[2] / w, 4), round(b[3] / h, 4)]})
        return out

    maize_n, weeds_n = _norm(maize, "M"), _norm(weeds, "W")
    quality = _quality(img)
    with _lock:
        db = _load_db()
        scan_id = _next_id(db, "SCAN")
        cap = db["captures"].get(image_path, {})
        preview = os.path.join(_state_dir(), "captures", f"{scan_id}_preview.jpg")
        _draw(img, maize_n, weeds_n, preview)
        db["scans"][scan_id] = {"scan_id": scan_id, "plot_id": cap.get("plot_id"), "image_path": image_path,
                                "time": _now(), "model": model_name, "maize": maize_n, "weeds": weeds_n,
                                "quality": quality, "image_size": [w, h]}
        _save_db(db)
    return {"ok": True, "scan_id": scan_id, "plot_id": cap.get("plot_id"), "maize_count": len(maize_n),
            "weed_count": len(weeds_n), "maize": maize_n, "weeds": weeds_n, "preview_path": preview, "quality": quality}


def _draw(img, maize, weeds, path):
    h, w = img.shape[:2]
    v = img.copy()
    for items, col in ((maize, (83, 200, 0)), (weeds, (214, 64, 255))):
        for p in items:
            x1, y1, x2, y2 = [int(p["box"][i] * (w if i % 2 == 0 else h)) for i in range(4)]
            cv2.rectangle(v, (x1, y1), (x2, y2), col, 2)
            cv2.putText(v, p["id"], (x1, max(y1 - 4, 12)), cv2.FONT_HERSHEY_SIMPLEX, 0.45, col, 1, cv2.LINE_AA)
    os.makedirs(os.path.dirname(path), exist_ok=True)
    cv2.imwrite(path, v)
