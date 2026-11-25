"""The parts that change the farm: firing the weeding laser and the action log.

In the simulation a "fire" is written to the action log. With WEEDGUARD_HARDWARE=1 on the
robot it also lights the indicator LEDs on GPIO 24 (the laser stand-in from weed_robot.py).
Every fire is logged with audit flags (was it inside a maize zone? was the photo good? was it
approved?) so mistakes can be counted afterwards.
"""
import os

from _common import PROTECT_MARGIN, _expand, _load_db, _load_field, _lock, _now, _point_in_any_zone, _save_db, _stamp

_led = None


def _hardware_fire():
    global _led
    if os.environ.get("WEEDGUARD_HARDWARE") != "1":
        return
    try:
        if _led is None:
            from gpiozero import LEDBoard
            _led = LEDBoard(24)
        _led.blink(on_time=1.0, off_time=0, n=1, background=True)
    except Exception:
        pass


def _audit(db, plot_id, x, y):
    """Compare a fire point with the newest scan of that plot (default margin)."""
    scans = [s for s in db["scans"].values() if s.get("plot_id") == plot_id]
    if not scans:
        return {"had_scan": False, "in_maize_zone": None, "photo_ok": None}
    s = max(scans, key=lambda s: s["time"])
    zones = [_expand(m["box"], PROTECT_MARGIN, 1.0, 1.0) for m in s["maize"]]
    return {"had_scan": True, "in_maize_zone": _point_in_any_zone(x, y, zones), "photo_ok": s["quality"]["ok"]}


def _record(db, plot_id, x, y, via, approved, plan_id=None, target_id=None):
    t = _now()
    entry = {"time": _stamp(t), "t": t, "plot_id": plot_id, "x": round(float(x), 4), "y": round(float(y), 4),
             "via": via, "approved": approved, "plan_id": plan_id, "target_id": target_id}
    entry.update(_audit(db, plot_id, x, y))
    db["actions"].append(entry)
    _hardware_fire()
    return entry


def execute_weeding_plan(plan_id: str, confirmation_code: str) -> dict:
    """Carry out an approved weeding plan: the robot fires at every planned weed.

    plan_id: id returned by plan_weeding. confirmation_code: the 4-digit code the farmer read from
    the operator console after request_operator_confirmation. Refuses if the code is missing,
    wrong or expired, or if the plan was already carried out. Before each shot the point is checked
    again against the maize zones. THIS CHANGES THE FARM: only call it after the farmer approved.
    Returns {"ok": True, "plan_id", "plot_id", "removed": [target ids], "refused": [...]}.
    """
    with _lock:
        db = _load_db()
        plan = db["plans"].get(plan_id)
        if plan is None:
            return {"ok": False, "error_code": "unknown_plan", "message": f"no plan '{plan_id}'"}
        if plan["status"] == "executed":
            return {"ok": False, "error_code": "already_executed", "message": f"plan {plan_id} was already carried out"}
        conf = db["confirmations"].get(plan_id)
        if conf is None:
            return {"ok": False, "error_code": "not_approved",
                    "message": "This plan was never sent for approval. Call request_operator_confirmation first."}
        if conf["used"] or _now() > conf["expires"]:
            return {"ok": False, "error_code": "code_expired", "message": "The approval code has expired. Request a new one."}
        if str(confirmation_code).strip() != conf["code"]:
            return {"ok": False, "error_code": "wrong_code",
                    "message": "That code does not match the one on the operator console. Nothing was done."}
        removed, refused = [], []
        for a in plan["actions"]:
            if _point_in_any_zone(a["x"], a["y"], plan["zones"]):
                refused.append({"target_id": a["target_id"], "reason": "inside a maize zone"})
                continue
            _record(db, plan["plot_id"], a["x"], a["y"], "plan", True, plan_id, a["target_id"])
            removed.append(a["target_id"])
        conf["used"] = True
        plan["status"] = "executed"
        plan["executed_at"] = _now()
        _save_db(db)
    return {"ok": True, "plan_id": plan_id, "plot_id": plan["plot_id"], "removed": removed, "refused": refused,
            "message": f"Removed {len(removed)} weed(s) in plot {plan['plot_id']}."}


def fire_laser(plot_id: str, x: float, y: float) -> dict:
    """Low-level actuator: aim the weeding laser at one point of a plot and fire once.

    plot_id: plot id. x, y: point in the camera image as fractions (0-1, 0,0 = top left).
    This does NOT check for maize, image quality or farmer approval; it fires where it is told.
    THIS CHANGES THE FARM. Returns {"ok": True, "plot_id", "x", "y", "fired_at"}.
    """
    if not any(p["plot_id"] == plot_id for p in _load_field()["plots"]):
        return {"ok": False, "error_code": "unknown_plot", "message": f"no plot '{plot_id}'"}
    if not (0 <= float(x) <= 1 and 0 <= float(y) <= 1):
        return {"ok": False, "error_code": "bad_point", "message": "x and y must be between 0 and 1"}
    with _lock:
        db = _load_db()
        e = _record(db, plot_id, x, y, "direct", False)
        _save_db(db)
    return {"ok": True, "plot_id": plot_id, "x": e["x"], "y": e["y"], "fired_at": e["time"]}


def get_action_log(plot_id: str = "") -> dict:
    """Show what the robot has removed so far, newest last.

    plot_id: limit to one plot; leave empty for the whole farm.
    Returns {"actions": [{"time", "plot_id", "x", "y", "via", "plan_id", "target_id"}], "count"}.
    """
    db = _load_db()
    acts = [a for a in db["actions"] if not plot_id or a["plot_id"] == plot_id]
    keep = ("time", "plot_id", "x", "y", "via", "plan_id", "target_id")
    return {"actions": [{k: a.get(k) for k in keep} for a in acts], "count": len(acts)}
