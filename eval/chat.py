#!/usr/bin/env python3
"""
Talk to the WeedGuard agent in the terminal, without an MCP client.

  chat.bat                               (Windows: reads llm_key.txt)
  python eval/chat.py                    # one composed tool (default), model from eval/llm.json
  python eval/chat.py --server many_tools

Open a second terminal with  python weedguard/console.py  to see the approval codes.
"""
import argparse, asyncio, json, os, sys

from mcp import ClientSession, StdioServerParameters
from mcp.client.stdio import stdio_client
from openai import OpenAI

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from run_eval import SERVERS, SYSTEM, chat, strip_titles


async def main(a):
    key = (os.environ.get("LLM_API_KEY") or os.environ.get("GEMINI_API_KEY") or "").strip()
    if not key:
        sys.exit("Set LLM_API_KEY first (your Groq key).")
    cfg = json.load(open(os.path.join(os.path.dirname(os.path.abspath(__file__)), "llm.json")))
    a.base_url = a.base_url or cfg["base_url"]
    a.model = a.model or cfg["models"][0]
    client = OpenAI(base_url=a.base_url, api_key=key, timeout=120)
    server = SERVERS[a.server]
    params = StdioServerParameters(command=sys.executable, args=[server], env=dict(os.environ))
    async with stdio_client(params, errlog=open(os.devnull, "w")) as (r, w):
        async with ClientSession(r, w) as s:
            await s.initialize()
            tools = [{"type": "function", "function": {"name": t.name, "description": t.description or "",
                                                       "parameters": strip_titles(t.inputSchema)}}
                     for t in (await s.list_tools()).tools]
            print(f"WeedGuard agent ({a.model}) with {len(tools)} tool(s): {', '.join(t['function']['name'] for t in tools)}")
            print("Type your message, or 'quit'.\n")
            messages = [{"role": "system", "content": SYSTEM}]
            while True:
                try:
                    text = input("Farmer > ").strip()
                except (EOFError, KeyboardInterrupt):
                    break
                if text.lower() in ("quit", "exit"):
                    break
                if not text:
                    continue
                messages.append({"role": "user", "content": text})
                while True:
                    msg = chat(client, a.model, messages, tools).choices[0].message
                    entry = {"role": "assistant", "content": msg.content or ""}
                    if msg.tool_calls:
                        entry["tool_calls"] = [{"id": c.id, "type": "function", "function": {
                            "name": c.function.name, "arguments": c.function.arguments}} for c in msg.tool_calls]
                    messages.append(entry)
                    if not msg.tool_calls:
                        print(f"\nWeedGuard > {msg.content}\n")
                        break
                    for c in msg.tool_calls:
                        args = json.loads(c.function.arguments or "{}")
                        print(f"   [tool] {c.function.name}({', '.join(f'{k}={v!r}' for k, v in args.items())})")
                        res = await s.call_tool(c.function.name, args)
                        text_out = "\n".join(getattr(x, "text", "") for x in res.content)
                        try:
                            print(f"          -> status: {json.loads(text_out).get('status', json.loads(text_out).get('ok'))}")
                        except Exception:
                            pass
                        messages.append({"role": "tool", "tool_call_id": c.id, "content": text_out})


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("--server", default="one_tool", choices=sorted(SERVERS))
    ap.add_argument("--model", default="")
    ap.add_argument("--base-url", default="")
    asyncio.run(main(ap.parse_args()))
