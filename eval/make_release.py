#!/usr/bin/env python3
"""Copy only the files the public repository needs into release/weedguard/.

Keys, caches, run state, the Synapse tools folder and the helper files used while building are left out.
Run from the project folder: python eval/make_release.py
"""
import glob, os, shutil, sys

REPO = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
OUT = os.path.join(REPO, "release", "weedguard")

KEEP = [
    # project front page and Windows helpers
    "README.md", "LICENSE", ".gitignore", "1_setup.bat", "2_build_with_synapse.bat", "3_run_comparison.bat", "chat.bat", "console.bat", "4_make_release.bat",
    # the Synapse project: building blocks, the generated tool, the request, the simulated farm
    "weedguard/_common.py", "weedguard/field.py", "weedguard/vision.py", "weedguard/safety.py",
    "weedguard/planner.py", "weedguard/actuator.py", "weedguard/console.py", "weedguard/weed_plot_server.py",
    "weedguard/SYNAPSE_QUERY.txt", "weedguard/field.json", "weedguard/requirements.txt",
    "weedguard/SETUP_AND_DEMO.md", "weedguard/field_images/*.jpg",
    # tests, comparison and analysis
    "eval/smoke_test.py", "eval/run_eval.py", "eval/tasks.json", "eval/many_tools_server.py", "eval/analyze.py",
    "eval/synapse_build.py", "eval/check_key.py", "eval/chat.py", "eval/requirements.txt", "eval/make_release.py",
    "eval/synapse_history/README.md", "eval/synapse_history/v1_weed_plot_server.py",
    "eval/synapse_history/v2_weed_plot_server.py",
    # results and write-up
    "docs/WRITEUP.md", "docs/RESULTS.md", "docs/comparison.svg", "docs/comparison_runs.jsonl", "docs/DETECTOR.md",
    # the existing detector project that WeedGuard is built on
    "detector.py", "app.py", "requirements.txt", "packages.txt", ".streamlit/config.toml",
    "models/*/robot_config.json", "models/*/*/metadata.yaml", "models/*/*/model.ncnn.param", "models/*/*/model.ncnn.bin",
    "robot/*.py", "robot/requirements-pi.txt", "robot/src/*.py", "robot/src/*.json",
    "notebooks/*.ipynb", "samples/*.jpg",
]
NEVER = ("synapse_key.txt", "llm_key.txt", "gemini_key.txt", "llm.json")

if os.path.exists(OUT):
    shutil.rmtree(OUT)
copied, missing = [], []
for pattern in KEEP:
    matches = sorted(glob.glob(os.path.join(REPO, pattern)))
    if not matches:
        missing.append(pattern)
    for src in matches:
        rel = os.path.relpath(src, REPO)
        if os.path.basename(rel) in NEVER:
            sys.exit(f"refusing to copy a key file: {rel}")
        dst = os.path.join(OUT, rel)
        os.makedirs(os.path.dirname(dst), exist_ok=True)
        shutil.copy2(src, dst)
        copied.append((rel.replace(os.sep, "/"), os.path.getsize(src)))
# the newest approval picture from a real run of the console becomes the example in the README
pics = sorted(glob.glob(os.path.join(REPO, "weedguard", "state", "captures", "*_approval.jpg")), key=os.path.getmtime)
if pics:
    dst = os.path.join(OUT, "docs", "approval_example.jpg")
    shutil.copy2(pics[-1], dst)
    copied.append(("docs/approval_example.jpg", os.path.getsize(dst)))
else:
    missing.append("docs/approval_example.jpg (run one job with console.bat open first)")
total = sum(b for _, b in copied)
for rel, b in copied:
    print(f"{b:>10,}  {rel}")
print(f"\n{len(copied)} files, {total / 1e6:.1f} MB copied to {OUT}")
if missing:
    print("MISSING (check these):", ", ".join(missing))
    sys.exit(1)
