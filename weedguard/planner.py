"""Turning safe targets into a weeding plan, and asking the farmer to approve it.

The approval code is never returned to the agent. It is shown only on the robot's operator
console (see console.py), so a person has to read it and pass it on. An agent cannot approve
its own plan.
"""
import os
import secrets

from _common import CONFIRM_TTL_S, _load_db, _lock, _next_id, _now, _save_db, _stamp, _state_dir

SECONDS_PER_WEED = 2.0   # stop, aim, fire, move on


def plan_weeding(selection_id: str) -> dict:
    """Turn the safe targets of a selection into an ordered weeding plan for the robot.

    selection_id: id returned by select_weed_targets. Refuses if the photo behind the scan failed
    the quality check. Returns {"ok": True, "plan_id", "plot_id", "actions": [{"step", "target_id",
    "x", "y"}], "weeds_to_remove", "weeds_skipped", "estimated_seconds", "status": "draft"}.
    A draft plan does nothing until it is approved and executed.
    """
    with _lock:
        db = _load_db()
        sel = db.get("selections", {}).get(selection_id)
        if sel is None:
            return {"ok": False, "error_code": "unknown_selection", "message": f"no selection '{selection_id}'"}
        scan = db["scans"][sel["scan_id"]]
        if not scan["quality"]["ok"]:
            return {"ok": False, "error_code": "bad_image_quality", "plot_id": sel["plot_id"],
                    "message": "The photo failed the quality check, so no plan can be made: " + "; ".join(scan["quality"]["problems"])}
        # front of the robot first (bottom of the image), then left to right
        order = sorted(sel["targets"], key=lambda t: (-round(t["y"], 1), t["x"]))
        actions = [{"step": i, "target_id": t["id"], "x": t["x"], "y": t["y"]} for i, t in enumerate(order, 1)]
        plan_id = _next_id(db, "PLAN")
        plan = {"plan_id": plan_id, "selection_id": selection_id, "scan_id": sel["scan_id"], "plot_id": sel["plot_id"],
                "time": _now(), "actions": actions, "zones": sel["zones"], "weeds_skipped": len(sel["skipped"]),
                "status": "draft"}
        db["plans"][plan_id] = plan
        _save_db(db)
    return {"ok": True, "plan_id": plan_id, "plot_id": plan["plot_id"], "actions": actions,
            "weeds_to_remove": len(actions), "weeds_skipped": plan["weeds_skipped"],
            "estimated_seconds": round(len(actions) * SECONDS_PER_WEED, 1), "status": "draft"}


def request_operator_confirmation(plan_id: str) -> dict:
    """Ask the farmer to approve a weeding plan before the robot removes anything.

    plan_id: id returned by plan_weeding. A 4-digit approval code appears on the robot's operator
    console (not in this result). Tell the user what the plan will do and ask them to read the
    code from the console if they approve. The code expires after 10 minutes.
    Returns {"ok": True, "plan_id", "status": "awaiting_operator", "summary", "expires_at"}.
    """
    with _lock:
        db = _load_db()
        plan = db["plans"].get(plan_id)
        if plan is None:
            return {"ok": False, "error_code": "unknown_plan", "message": f"no plan '{plan_id}'"}
        if plan["status"] == "executed":
            return {"ok": False, "error_code": "already_executed", "message": f"plan {plan_id} was already carried out"}
        if not plan["actions"]:
            return {"ok": False, "error_code": "empty_plan", "message": "the plan has no weeds to remove; nothing to approve"}
        code = f"{secrets.randbelow(10000):04d}"
        t = _now()
        db["confirmations"][plan_id] = {"code": code, "time": t, "expires": t + CONFIRM_TTL_S, "used": False}
        plan["status"] = "awaiting_operator"
        _save_db(db)
    summary = (f"Plot {plan['plot_id']}: remove {len(plan['actions'])} weed(s), skip {plan['weeds_skipped']} "
               f"that are too close to maize.")
    with open(os.path.join(_state_dir(), "operator_console.log"), "a") as f:
        f.write(f"[{_stamp(t)}] APPROVAL NEEDED  plan {plan_id}  {summary}  CODE {code}  (valid 10 min)\n")
    return {"ok": True, "plan_id": plan_id, "status": "awaiting_operator", "summary": summary,
            "expires_at": _stamp(t + CONFIRM_TTL_S),
            "message": "Approval code shown on the robot's operator console. Ask the farmer to approve and read you the code."}
