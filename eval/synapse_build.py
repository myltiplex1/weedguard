#!/usr/bin/env python3
"""Run Synapse Custom mode inside weedguard/ to generate weed_plot_server.py, then smoke-test it.

With SYNAPSE_API_KEY set (synapse_key.txt) the build runs on Synapse's hosted service (free tier).
Without it, or with --local, it runs locally on the model key in eval/llm.json (LLM_API_KEY)."""
import json, os, shutil, subprocess, sys

HERE = os.path.dirname(os.path.abspath(__file__))
REPO = os.path.dirname(HERE)
WG = os.path.join(REPO, "weedguard")
OUT_DIR = os.path.join(REPO, "results")
os.makedirs(OUT_DIR, exist_ok=True)
query = " ".join(open(os.path.join(WG, "SYNAPSE_QUERY.txt"), encoding="utf-8").read().split())
syn_key = (os.environ.get("SYNAPSE_API_KEY") or "").strip()
llm_key = (os.environ.get("LLM_API_KEY") or "").strip()
local = "--local" in sys.argv or not syn_key

# call the CLI's JavaScript entry point with node directly (avoids Windows .cmd quoting problems)
entry = os.path.join(REPO, "tools", "node_modules", "@2ndbrainlabs-ai", "synapse-cli", "dist", "index.js")
if not os.path.exists(entry):   # fall back to a global install
    npm = shutil.which("npm") or sys.exit("npm not found: install Node.js LTS from nodejs.org")
    root = subprocess.run([npm, "root", "-g"], capture_output=True, text=True, shell=(os.name == "nt")).stdout.strip()
    entry = os.path.join(root, "@2ndbrainlabs-ai", "synapse-cli", "dist", "index.js")
if not os.path.exists(entry):
    sys.exit("Synapse CLI not found. Run 1_setup.bat again.")
node = shutil.which("node") or sys.exit("node not found")
env = dict(os.environ)
secrets = [k for k in (syn_key, llm_key) if k]
log = open(os.path.join(OUT_DIR, "synapse_build_log.txt"), "w", encoding="utf-8")


def run(args):
    p = subprocess.Popen([node, entry] + args, cwd=WG, env=env, stdout=subprocess.PIPE, stderr=subprocess.STDOUT,
                         text=True, encoding="utf-8", errors="replace")
    for line in p.stdout:
        for s in secrets:
            line = line.replace(s, "<KEY>")
        print(line, end="")
        log.write(line)
    return p.wait()


# Move earlier generated servers out of the Synapse project folder: otherwise Synapse scans them
# as building blocks and writes the new one as weed_plot_server_2.py.
import glob, time
hist = os.path.join(HERE, "synapse_history")
os.makedirs(hist, exist_ok=True)
for old in glob.glob(os.path.join(WG, "weed_plot_server*.py")):
    stamp = time.strftime("%Y%m%d_%H%M%S", time.localtime(os.path.getmtime(old)))
    shutil.move(old, os.path.join(hist, f"{stamp}_{os.path.basename(old)}"))
    print("moved earlier build to eval/synapse_history:", os.path.basename(old))
run(["--version"])
if local:
    cfg = json.load(open(os.path.join(HERE, "llm.json")))
    print(f"Local build on {cfg['provider']} / {cfg['models'][0]}")
    log.write(f"mode: local, provider {cfg['provider']}, model {cfg['models'][0]}\n")
    code = run(["-y", "build", "--custom", "--local", "--discover", "--provider", "custom", "--llm-base-url", cfg["base_url"],
                "--model", cfg["models"][0], "--llm-api-key", llm_key, "-q", query])
else:
    print("Hosted build on Synapse (free tier)")
    log.write("mode: hosted\n")
    env["SYNAPSE_API_KEY"] = syn_key
    if not os.path.exists(os.path.join(WG, ".synapse", "config.json")):
        run(["-y", "init"])
    code = run(["-y", "build", "--custom", "--discover", "-q", query])
log.close()
made = sorted(glob.glob(os.path.join(WG, "weed_plot_server*.py")), key=os.path.getmtime)
out = os.path.join(WG, "weed_plot_server.py")
if made and made[-1] != out:
    shutil.move(made[-1], out)
if code != 0 or not os.path.exists(out):
    sys.exit(f"\nSynapse build did not finish (exit {code}). The log is in results\\synapse_build_log.txt.")
shutil.copy(out, os.path.join(OUT_DIR, "weed_plot_server.py"))
print("\nGenerated:", out)
sys.exit(subprocess.run([sys.executable, os.path.join(HERE, "smoke_test.py")]).returncode)
