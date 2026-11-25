"""Maize protection: decide which weeds are safe to target.

Same rule as robot/weed_robot.py: every maize box is enlarged by a safety margin, and any
weed whose box touches one of those zones is skipped. Maize always wins.
"""
from _common import PROTECT_MARGIN, _expand, _load_db, _lock, _next_id, _now, _overlaps, _save_db


def select_weed_targets(scan_id: str, protect_margin: float = PROTECT_MARGIN) -> dict:
    """Apply the maize-protection rule to a scan and list the weeds that are safe to remove.

    scan_id: id returned by detect_plants. protect_margin: how much each maize box is enlarged
    on every side (0.15 = 15 %, the robot default; values below 0.10 are refused).
    Returns {"ok": True, "selection_id", "plot_id", "maize_count", "weed_count", "safe_target_count",
    "skipped_near_maize", "targets": [{"id", "x", "y", "conf"}], "skipped": [{"id", "reason"}],
    "maize_zones": [[x1, y1, x2, y2]]} with x, y = weed centre as fractions of the image.
    safe_target_count is 0 when every weed is too close to maize. The selection_id is needed by plan_weeding.
    """
    if protect_margin < 0.10:
        return {"ok": False, "error_code": "margin_too_small",
                "message": "protect_margin below 0.10 is not allowed: it would put maize at risk."}
    with _lock:
        db = _load_db()
        scan = db["scans"].get(scan_id)
        if scan is None:
            return {"ok": False, "error_code": "unknown_scan", "message": f"no scan '{scan_id}'; run detect_plants first"}
        zones = [_expand(m["box"], protect_margin, 1.0, 1.0) for m in scan["maize"]]
        targets, skipped = [], []
        for wd in scan["weeds"]:
            b = wd["box"]
            hit = [scan["maize"][i]["id"] for i, z in enumerate(zones) if _overlaps(b, z)]
            if hit:
                skipped.append({"id": wd["id"], "reason": f"too close to maize {', '.join(hit)}"})
            else:
                targets.append({"id": wd["id"], "x": round((b[0] + b[2]) / 2, 4), "y": round((b[1] + b[3]) / 2, 4),
                                "conf": wd["conf"]})
        sel_id = _next_id(db, "SEL")
        db.setdefault("selections", {})[sel_id] = {
            "selection_id": sel_id, "scan_id": scan_id, "plot_id": scan["plot_id"], "time": _now(),
            "protect_margin": protect_margin, "zones": [[round(v, 4) for v in z] for z in zones],
            "targets": targets, "skipped": skipped}
        _save_db(db)
    return {"ok": True, "selection_id": sel_id, "plot_id": scan["plot_id"], "maize_count": len(scan["maize"]),
            "weed_count": len(scan["weeds"]), "safe_target_count": len(targets), "skipped_near_maize": len(skipped),
            "targets": targets, "skipped": skipped, "maize_zones": db["selections"][sel_id]["zones"]}
