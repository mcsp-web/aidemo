"""
llm.py — the generation half of the system.

Takes the question plus the retrieved passages and asks an LLM to answer using
ONLY those passages. Provider is chosen with the LLM_PROVIDER env var, so the
same app can run on Claude or GPT with no code change — a useful thing to be
able to show a client.
"""

from __future__ import annotations

import os

SYSTEM_PROMPT = (
    "You answer questions about a document using only the passages provided. "
    "If the answer is not in the passages, say you couldn't find it in the "
    "document rather than guessing. Be concise and quote figures exactly."
)


def _build_user_message(question: str, passages: list[str]) -> str:
    context = "\n\n".join(f"[Passage {i + 1}]\n{p}" for i, p in enumerate(passages))
    return (
        f"Here are the relevant passages from the document:\n\n{context}\n\n"
        f"Question: {question}\n\n"
        "Answer using only the passages above."
    )


def answer(question: str, passages: list[str]) -> str:
    provider = os.getenv("LLM_PROVIDER", "anthropic").lower()
    user_message = _build_user_message(question, passages)

    if provider == "anthropic":
        from anthropic import Anthropic

        client = Anthropic()  # reads ANTHROPIC_API_KEY from the environment
        model = os.getenv("LLM_MODEL", "claude-haiku-4-5-20251001")
        resp = client.messages.create(
            model=model,
            max_tokens=600,
            system=SYSTEM_PROMPT,
            messages=[{"role": "user", "content": user_message}],
        )
        return "".join(block.text for block in resp.content if block.type == "text")

    if provider == "openai":
        from openai import OpenAI

        client = OpenAI()  # reads OPENAI_API_KEY from the environment
        model = os.getenv("LLM_MODEL", "gpt-4o-mini")
        resp = client.chat.completions.create(
            model=model,
            max_tokens=600,
            messages=[
                {"role": "system", "content": SYSTEM_PROMPT},
                {"role": "user", "content": user_message},
            ],
        )
        return resp.choices[0].message.content or ""

    raise ValueError(f"Unknown LLM_PROVIDER: {provider!r} (use 'anthropic' or 'openai')")
