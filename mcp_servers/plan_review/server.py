"""plan-review MCP server: one tool, ``review_plan``, backed by OpenAI.

A small stdio MCP server that takes an implementation-plan text, asks OpenAI
(ChatGPT) to point out the missing parts and risks, and returns the review.

It is independent of CoilForge's engineering code. It only reuses the repo's
existing OpenAI key-loading convention (``OPENAI_API_KEY`` via env / repo-root
``.env``) so a single key serves both the PDF OCR path and this tool.
"""

from __future__ import annotations

import os
from pathlib import Path

from mcp.server.fastmcp import FastMCP

# Default model; override with the PLAN_REVIEW_MODEL env var.
DEFAULT_MODEL = "gpt-4o"

# The review brief sent as the system message. The final instruction steers the
# output language to match the plan, per the user's choice.
SYSTEM_PROMPT = (
    "You are a senior software engineer doing a critical pre-build review of an "
    "implementation plan. Point out what is missing or risky. Cover: "
    "(1) missing pieces and gaps in the plan, "
    "(2) risks, edge cases, and failure modes, "
    "(3) ordering or dependency problems between steps, and "
    "(4) untested assumptions. "
    "Be specific and actionable, and prioritize the most important issues first. "
    "Do not rewrite the plan; review it. "
    "Respond in the SAME language as the plan text."
)


def _load_dotenv_if_available() -> None:
    """Load environment variables from a standard .env and the repo-root .env.

    Mirrors ``src/coilforge/submittal/pdf_intake.py`` so one .env serves both.
    This file lives at ``<repo>/mcp_servers/plan_review/server.py``, so the repo
    root is ``parents[2]``.
    """
    try:
        from dotenv import load_dotenv  # type: ignore

        load_dotenv()
        repo_env = Path(__file__).resolve().parents[2] / ".env"
        if repo_env.exists():
            load_dotenv(repo_env)
    except Exception:
        return


def review_plan_text(plan: str) -> str:
    """Send ``plan`` to OpenAI and return the review text.

    Never raises: missing-key and API errors are returned as a readable
    ``"ERROR: ..."`` string so the MCP tool degrades gracefully.
    """
    plan = (plan or "").strip()
    if not plan:
        return "ERROR: No plan text was provided. Pass the plan as the `plan` argument."

    _load_dotenv_if_available()
    model = os.environ.get("PLAN_REVIEW_MODEL", DEFAULT_MODEL)
    api_key = os.environ.get("OPENAI_API_KEY", "")
    if not api_key:
        return (
            "ERROR: OPENAI_API_KEY was not found in environment or .env. "
            "Set it (e.g. in the repo-root .env) and try again."
        )

    try:
        import openai  # type: ignore

        client = openai.OpenAI(api_key=api_key)
        response = client.chat.completions.create(
            model=model,
            temperature=0,
            max_tokens=int(os.environ.get("PLAN_REVIEW_MAX_TOKENS", "2000")),
            messages=[
                {"role": "system", "content": SYSTEM_PROMPT},
                {
                    "role": "user",
                    "content": (
                        "Review this implementation plan and point out its missing "
                        "parts and risks:\n\n" + plan
                    ),
                },
            ],
        )
        review = (response.choices[0].message.content or "").strip()
        if not review:
            return "ERROR: OpenAI returned an empty review."
        return review
    except Exception as exc:  # network / API / SDK errors -> readable message
        return f"ERROR: OpenAI request failed: {exc}"


mcp = FastMCP("plan-review")


@mcp.tool()
def review_plan(plan: str) -> str:
    """Review an implementation plan and point out missing parts and risks.

    Args:
        plan: The implementation-plan text to review.

    Returns:
        The review text (or a readable ``ERROR: ...`` message on failure).
    """
    return review_plan_text(plan)


if __name__ == "__main__":
    mcp.run()  # stdio transport (Claude Code default)
