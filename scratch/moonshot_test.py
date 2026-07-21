#!/usr/bin/env python3
"""Moonshot (Kimi) API smoke test.

Setup (one time, key NEVER in this file or in chat):
  nano ~/.zshrc   ->  add:  export MOONSHOT_API_KEY="your-new-key"
  source ~/.zshrc

Run:  python3 scratch/moonshot_test.py
"""
import os
import sys

from openai import OpenAI

key = os.environ.get("MOONSHOT_API_KEY", "")
if not key:
    sys.exit('MOONSHOT_API_KEY not set. Add to ~/.zshrc:  export MOONSHOT_API_KEY="..."  then: source ~/.zshrc')

client = OpenAI(api_key=key, base_url="https://api.moonshot.ai/v1")

print("== models available to this key ==")
models = [m.id for m in client.models.list().data]
for m in models:
    print(" -", m)

# pick a kimi chat model from whatever the account actually offers
pick = next((m for m in models if "kimi" in m or "moonshot" in m), models[0] if models else None)
if not pick:
    sys.exit("no models returned — key may lack access")

print(f"\n== smoke test on {pick} ==")
resp = client.chat.completions.create(
    model=pick,
    messages=[{"role": "user", "content": "Reply with exactly: OK"}],
    max_tokens=8,
    temperature=0,
)
print("response:", resp.choices[0].message.content)
print("\nPASS — key works, endpoint reachable, model answers.")
