#!/usr/bin/env python3
"""PostToolUse hook: when a tool call puts an image into assets/<name>/src/, remind Claude to run the
intake check and, if the sheet falls short, offer the user the generated regeneration prompt."""
import json, re, sys

try:
    data = json.load(sys.stdin)
except Exception:
    sys.exit(0)
inp = data.get("tool_input") or {}
text = " ".join(str(v) for v in (inp.get("command"), inp.get("file_path")) if v)
m = re.search(r"assets/([\w.-]+)/src/[\w. -]+\.(png|jpe?g|webp)", text, re.I)
if not m:
    sys.exit(0)
name = m.group(1)
print(json.dumps({"hookSpecificOutput": {"hookEventName": "PostToolUse", "additionalContext": (
    f"Sprite-sheet workflow: a source image was added to assets/{name}/src/. Before any pixel work run "
    f"`uv run python -I tools/sheet_assess.py <image> --spec assets/{name}/sprite.json --out assets/{name}/assess` "
    "(omit --spec if there is none yet), read assess/contact.png, and if the verdict is not GO show the user the "
    f"prompt in assets/{name}/assess/regen_prompt.md so they can steer the image generator (Gemini) to fix it.")}}))
