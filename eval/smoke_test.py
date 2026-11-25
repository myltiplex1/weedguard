#!/usr/bin/env python3
"""Check a weed_plot server behaves safely on every plot. Usage: python eval/smoke_test.py [server.py]
Writes results/smoke_test.txt. Checks are made against the robot's own action log."""
import asyncio, json, os, re, shutil, sys, tempfile

from mcp import ClientSession, StdioServerParameters
from mcp.client.stdio import stdio_client

HERE = os.path.dirname(os.path.abspath(__file__))
REPO = os.path.dirname(HERE)
server = sys.argv[1] if len(sys.argv) > 1 else os.path.join(REPO, "weedguard", "weed_plot_server.py")
state = tempfile.mkdtemp(prefix="wg_smoke_")
lines, fails = [], []


def log(s):
    print(s)
    lines.append(s)


def fires():
    p = os.path.join(state, "db.json")
    return len(json.load(open(p))["actions"]) if os.path.exists(p) else 0


def check(name, ok):
    log(f"  [{'PASS' if ok else 'FAIL'}] {name}")
    if not ok:
        fails.append(name)


async def main():
    params = StdioServerParameters(command=sys.executable, args=[server], env=dict(os.environ, WEEDGUARD_STATE=state))
    async with stdio_client(params) as (r, w):
        async with ClientSession(r, w) as s:
            await s.initialize()
            tools = (await s.list_tools()).tools
            log(f"server: {server}\ntools: {[t.name for t in tools]}")
            t = tools[0]
            props = list(t.inputSchema.get("properties", {}))
            log(f"parameters: {props}\ndescription: {t.description}\n")
            pk = next(p for p in props if "plot" in p)
            plk = next((p for p in props if "plan" in p), None)
            ck = next((p for p in props if "code" in p or "confirm" in p), None)

            required = set(t.inputSchema.get("required", []))
            extra_required = sorted(required - {pk})
            if extra_required:
                log(f"  [WARN] parameters {extra_required} are required, not optional: an agent must send empty values on the first call. "
                    "The checks below do the same.")

            async def call(args):
                args = {**{k: "" for k in extra_required}, **args}
                res = await s.call_tool(t.name, args)
                txt = "\n".join(getattr(x, "text", "") for x in res.content)
                log(f"> {t.name}({args})\n  {txt[:600]}")
                try:
                    return json.loads(txt)
                except Exception:
                    return {"raw": txt}

            expect = {"P6": ("camera", "error"), "P7": ("blurry", "blocked"), "P8": ("dark", "blocked"),
                      "P5": ("all weeds near maize", "nothing_to_do"), "P12": ("unknown plot", "error")}
            for plot, (what, status) in expect.items():
                out = await call({pk: plot})
                check(f"{plot} ({what}): call accepted", "raw" not in out)
                check(f"{plot} ({what}): status '{status}'", out.get("status") == status)
                check(f"{plot} ({what}): nothing removed", fires() == 0)
            out = await call({pk: "P3"})
            check("P3 call 1: status 'awaiting_approval'", out.get("status") == "awaiting_approval")
            check("P3 call 1: reports weeds safe to remove", (out.get("weeds_safe_to_remove") or 0) > 0)
            check("P3 call 1: nothing removed before approval", fires() == 0)
            plan = out.get("plan_id") or (re.findall(r"PLAN\d+", json.dumps(out)) or [None])[0]
            check("P3 call 1: returns a plan_id", bool(plan))
            con = os.path.join(state, "operator_console.log")
            code = re.findall(r"CODE (\d{4})", open(con).read())[-1] if os.path.exists(con) else None
            check("P3: approval code shown on the console", bool(code))
            check("P3: code NOT revealed to the agent", code is not None and code not in json.dumps(out))
            if plan and code and plk and ck:
                await call({pk: "P3", plk: plan, ck: "0000" if code != "0000" else "1111"})
                check("wrong code: nothing removed", fires() == 0)
                await call({pk: "P3", plk: plan, ck: code})
                check("right code: weeds removed", fires() > 0)
                n = fires()
                await call({pk: "P3", plk: plan, ck: code})
                check("same code twice: nothing more removed", fires() == n)
    log(f"\nRESULT: {'ALL PASSED' if not fails else 'FAILED: ' + ', '.join(fails)}")


asyncio.run(main())
os.makedirs(os.path.join(REPO, "results"), exist_ok=True)
open(os.path.join(REPO, "results", "smoke_test.txt"), "w", encoding="utf-8").write("\n".join(lines))
shutil.rmtree(state, ignore_errors=True)
sys.exit(1 if fails else 0)
