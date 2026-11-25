"""The farm: which plots exist and how to get a camera image of one.

On the real robot capture_plot_image() would drive to the plot and grab a frame from the Pi
camera. In the simulation each plot is linked to a stored field photo, and some plots are set
up to fail the way the real robot can (camera not detected, blurry lens, dusk light).
"""
import os
import shutil

from _common import HERE, _load_db, _load_field, _next_id, _now, _save_db, _stamp, _state_dir, _lock


def list_plots() -> dict:
    """List every plot on the farm with its id, name, size and last weeding time.

    Use this first when the user does not give a plot id, or names a plot that may not exist.
    Returns {"plots": [{"plot_id", "name", "area_m2", "last_weeded"}]}.
    """
    field = _load_field()
    db = _load_db()
    last = {}
    for a in db["actions"]:
        last[a["plot_id"]] = a["time"]
    return {"plots": [
        {"plot_id": p["plot_id"], "name": p["name"], "area_m2": p["area_m2"], "last_weeded": last.get(p["plot_id"])}
        for p in field["plots"]
    ]}


def capture_plot_image(plot_id: str) -> dict:
    """Drive the robot to a plot and take a top-down camera photo of it.

    plot_id: id from list_plots, e.g. "P1".
    Returns {"ok": True, "plot_id", "image_path", "captured_at"} or, if the plot does not
    exist or the camera fails, {"ok": False, "error_code", "message"}. error_code is one of
    "unknown_plot" or "camera_unavailable". Nothing on the farm changes when this runs.
    """
    field = _load_field()
    plot = next((p for p in field["plots"] if p["plot_id"].lower() == str(plot_id).strip().lower()), None)
    if plot is None:
        return {"ok": False, "error_code": "unknown_plot",
                "message": f"There is no plot '{plot_id}'. Known plots: {', '.join(p['plot_id'] for p in field['plots'])}."}
    if plot.get("camera") == "offline":
        return {"ok": False, "error_code": "camera_unavailable", "plot_id": plot["plot_id"],
                "message": "The Pi camera was not detected (no camera found on the CSI port). "
                           "Check the ribbon cable and run 'rpicam-hello --list-cameras' on the robot."}
    src = os.path.join(HERE, plot["image"])
    with _lock:
        db = _load_db()
        cap_id = _next_id(db, "CAP")
        dst_dir = os.path.join(_state_dir(), "captures")
        os.makedirs(dst_dir, exist_ok=True)
        dst = os.path.join(dst_dir, f"{cap_id}_{plot['plot_id']}{os.path.splitext(src)[1]}")
        shutil.copyfile(src, dst)
        t = _now()
        db["captures"][dst] = {"plot_id": plot["plot_id"], "time": t, "capture_id": cap_id}
        _save_db(db)
    return {"ok": True, "plot_id": plot["plot_id"], "image_path": dst, "captured_at": _stamp(t)}
