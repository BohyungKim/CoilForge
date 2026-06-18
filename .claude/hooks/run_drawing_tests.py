#!/usr/bin/env python3
"""Claude Code PostToolUse hook: run the drawing-engine tests after a relevant edit.

Reads the hook JSON from stdin, extracts the edited file path, and runs pytest
ONLY when the change touches the drawing engine or its tests. On failure it exits
with code 2 and writes the pytest output to stderr, which Claude Code feeds back
into the session so Claude can fix the regression in the same turn.

Place at: <repo>/.claude/hooks/run_drawing_tests.py
Wire up in: <repo>/.claude/settings.json  (see the PostToolUse snippet in chat)
"""
import json
import subprocess
import sys

# Edits under these paths trigger the drawing tests. Adjust as the engine grows.
WATCHED = ("src/coilforge/drawing/", "tests/test_schematic_renderer.py")
TEST_TARGET = "tests/test_schematic_renderer.py"


def main() -> int:
    try:
        event = json.load(sys.stdin)
    except (json.JSONDecodeError, ValueError):
        return 0  # No/!malformed hook input -> nothing to do.

    file_path = (event.get("tool_input") or {}).get("file_path", "")
    norm = file_path.replace("\\", "/")  # normalize Windows separators
    if not any(token in norm for token in WATCHED):
        return 0  # Edit unrelated to the drawing engine -> skip.

    # sys.executable -> use the same interpreter/venv Claude Code launched with.
    result = subprocess.run(
        [sys.executable, "-m", "pytest", TEST_TARGET, "-q"],
        capture_output=True,
        text=True,
    )
    if result.returncode != 0:
        # Exit 2 + stderr => Claude Code surfaces this back to Claude as context.
        sys.stderr.write(result.stdout + result.stderr)
        return 2
    return 0


if __name__ == "__main__":
    sys.exit(main())
