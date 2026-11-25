"""
Baseline for the comparison: the same WeedGuard functions exposed one by one as ten separate
MCP tools, which is what you get by exposing every function. The agent has to chain them itself
and decide on its own when to check quality, protect maize and ask for approval.
"""
from __future__ import annotations

import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "weedguard"))

from mcp.server.fastmcp import FastMCP
import field, vision, safety, planner, actuator

mcp = FastMCP("weedguard-many-tools")

for fn in (field.list_plots, field.capture_plot_image, vision.check_image_quality, vision.detect_plants,
           safety.select_weed_targets, planner.plan_weeding, planner.request_operator_confirmation,
           actuator.execute_weeding_plan, actuator.fire_laser, actuator.get_action_log):
    mcp.tool(name=fn.__name__, description=fn.__doc__.strip())(fn)

if __name__ == "__main__":
    mcp.run()
