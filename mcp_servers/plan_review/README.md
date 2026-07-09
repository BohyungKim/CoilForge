# plan-review MCP server

A tiny local MCP server exposing one tool, `review_plan`, that sends an
implementation-plan text to OpenAI (ChatGPT) and returns a review pointing out
missing parts and risks. The review is written in the same language as the plan.

## Setup

```bash
python -m pip install mcp openai python-dotenv
```

Set your key in the repo-root `.env` (shared with the PDF OCR path):

```
OPENAI_API_KEY=sk-...
```

Registration lives in the repo-root `.mcp.json`. Restart / reload Claude Code so
the `mcp__plan-review__review_plan` tool becomes available.

## Configuration (env vars)

- `OPENAI_API_KEY` — required.
- `PLAN_REVIEW_MODEL` — model to use (default `gpt-4o`).
- `PLAN_REVIEW_MAX_TOKENS` — response cap (default `2000`).

## Quick check

```bash
# Without a key set, this prints a clear ERROR (graceful degradation):
python -c "import sys; sys.path.insert(0, 'mcp_servers/plan_review'); from server import review_plan_text; print(review_plan_text('Build X by doing Y'))"
```
