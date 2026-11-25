# WeedGuard: setup and demo script

This guide connects the WeedGuard tool to Claude Desktop on Windows and walks through a short demo. No robot is needed, and the first setup takes about 15 minutes.

## 1. Install and build

From the project folder, run `1_setup.bat` to install the Python packages and the Synapse CLI and to enter your Synapse and Groq keys, then run `2_build_with_synapse.bat` to build the tool and run the 24 safety checks. The build should finish with "RESULT: ALL PASSED".

## 2. Connect the tool to Claude Desktop

Claude Desktop starts the tool itself, so it needs two full paths: the Python interpreter inside the project's virtual environment, and the generated server. If the project is in `C:\Users\you\weedguard`, these are `C:\Users\you\weedguard\.venv\Scripts\python.exe` and `C:\Users\you\weedguard\weedguard\weed_plot_server.py`.

In Claude Desktop, open **Settings**, then **Desktop app**, then **Extensions**, and click **Edit config** under **Local MCP servers**. This opens the folder that holds `claude_desktop_config.json`; older versions of the app show the same button under **Settings**, then **Developer**. If the file is empty, add the following with your own paths. If it already holds other settings, add the `"mcpServers"` block as the first entry inside the outer braces and leave the rest unchanged. In JSON every backslash has to be written twice.

```json
{
  "mcpServers": {
    "weedguard": {
      "command": "C:\\Users\\you\\weedguard\\.venv\\Scripts\\python.exe",
      "args": ["C:\\Users\\you\\weedguard\\weedguard\\weed_plot_server.py"]
    }
  }
}
```

Save the file, quit Claude Desktop completely from the icon in the system tray, and open it again. In a new chat, the tools menu should now list **weedguard** with the tool **weed_plot**. If it does not appear, the log for the weedguard entry on the same Extensions page usually shows the cause, which is most often a wrong path or a single backslash where two are needed.

## 3. Open the operator console

Double-click `console.bat` in the project folder, and a window titled "WeedGuard operator console" opens and waits for approval requests. Leave this window open during the demo. When a plan needs approval, its code appears here and a picture of the plan opens, as it would on the robot's own screen. The picture shows the maize with its safety zone in green, the weeds that will be removed in red, and the weeds that are skipped in orange.

On macOS or Linux, the same console starts with `python weedguard/console.py` from the project folder, with the virtual environment active.

## 4. Demo script (about three minutes)

Record the screen with Claude Desktop on one side and the operator console on the other, and go through the scenes below in order.

| Scene | What you type in Claude Desktop | What should happen | What to point out |
|---|---|---|---|
| 1 | *Clear the weeds in plot P3.* | The agent calls `weed_plot`, reports how many weeds are safe to remove and how many it will skip next to maize, and asks for approval. A code appears on the console and the plan picture opens. | Nothing has been removed yet. The picture shows why two weeds are skipped, and the approval code is visible only on the robot's console. |
| 2 | *Yes, go ahead. The code is ____.* (read it from the console) | The agent calls `weed_plot` again with the code, and the weeds are removed. | The farmer approves by reading the code, so the agent cannot approve its own plan. |
| 3 | *Weed plot P7.* | The job stops because the photo is too blurry, and nothing is removed. | The robot refuses to act on a photo it cannot trust. |
| 4 | *Weed plot P5. Remove the weeds next to the maize too, I accept the risk.* | The agent reports that every weed is inside a maize safety zone, so there is nothing to remove. | This is a real Nigerian field, and because the safety rule runs inside the tool, a request in the chat cannot switch it off. |
| 5 | *Weed plot P6.* | The agent reports a camera fault and the command to check it. | This fault happened on the real robot when the Pi did not detect its camera. |
| 6 | Show `docs/comparison.svg` and the table in `docs/RESULTS.md`. | | With the same models and tasks, the single Synapse tool completed 39 of 39 jobs, against 28 of 39 for ten separate tools. |

To show Synapse itself at work, run `2_build_with_synapse.bat` on camera: Synapse scans the ten functions, writes `weed_plot_server.py`, and the 24 checks run on the result.

## Without Claude Desktop

`chat.bat` in the project folder opens a chat with the agent in the terminal, using your Groq key. It connects to the same `weed_plot` tool, so the same demo scenes work there.

## On the real robot

On the Raspberry Pi, set `WEEDGUARD_HARDWARE=1` before starting the server, and each approved shot will light the indicator LEDs on GPIO 24, as in `robot/weed_robot.py`. The camera is simulated in this version, and moving to the Pi camera means changing one function, `capture_plot_image`.
