#!/usr/bin/env python3
"""Check the model key and find the models that can call tools. Writes eval/llm.json.

The provider is recognised from the key: gsk_... = Groq, sk-or-... = OpenRouter, AIza.../AQ.... = Google Gemini.
On failure it prints the provider's full error message."""
import json, os, sys
from openai import OpenAI

HERE = os.path.dirname(os.path.abspath(__file__))
PROVIDERS = {
    "groq": ("https://api.groq.com/openai/v1", ["openai/gpt-oss-120b", "qwen/qwen3.8-27b", "openai/gpt-oss-20b",
                                                "llama-3.3-70b-versatile", "moonshotai/kimi-k2-instruct"]),
    "openrouter": ("https://openrouter.ai/api/v1", ["openai/gpt-oss-120b:free", "qwen/qwen3-coder:free", "deepseek/deepseek-chat-v3.1:free"]),
    "gemini": ("https://generativelanguage.googleapis.com/v1beta/openai/", ["gemini-2.5-flash", "gemini-flash-latest", "gemini-2.5-flash-lite"]),
}


def provider_for(key):
    if key.startswith("gsk_"):
        return "groq"
    if key.startswith("sk-or-"):
        return "openrouter"
    if key.startswith("AIza") or key.startswith("AQ."):
        return "gemini"
    sys.exit("Unknown key type. Use a Groq key (starts with gsk_).")


key = (os.environ.get("LLM_API_KEY") or "").strip()
if not key:
    sys.exit("No key: llm_key.txt is empty.")
prov = provider_for(key)
base, prefer = PROVIDERS[prov]
client = OpenAI(base_url=base, api_key=key, timeout=60, max_retries=1)
try:
    ids = sorted(m.id.replace("models/", "") for m in client.models.list())
except Exception as e:
    sys.exit(f"KEY PROBLEM ({prov}): could not list models: {getattr(e, 'body', None) or e}")
print(f"Provider: {prov}. The key can list {len(ids)} models.")

tool = [{"type": "function", "function": {"name": "ping", "description": "Reply ping",
         "parameters": {"type": "object", "properties": {"x": {"type": "string"}}, "required": ["x"]}}}]
working = []
for m in [m for m in prefer if m in ids]:
    try:
        r = client.chat.completions.create(model=m, messages=[{"role": "user", "content": "Call the ping tool with x='hi'."}],
                                           tools=tool, max_tokens=300)
        if r.choices[0].message.tool_calls:
            working.append(m)
            print(f"  {m}: OK (calls tools)")
        else:
            print(f"  {m}: answered but did not call the tool")
    except Exception as e:
        print(f"  {m}: FAILED: {getattr(e, 'body', None) or e}")
if not working:
    print("\nNo working model found. The messages above explain why.")
    sys.exit(1)
json.dump({"provider": prov, "base_url": base, "models": working}, open(os.path.join(HERE, "llm.json"), "w"), indent=1)
print(f"\nOK: {len(working)} model(s) ready: {', '.join(working)}")
