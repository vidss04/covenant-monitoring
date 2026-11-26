"""Thin Claude client wrapper with usage logging. Only used when ANTHROPIC_API_KEY is set."""
import os
import time

from cov.common import load_settings

USAGE = []  # one row per call: purpose, model, input/output tokens, latency


def available():
    return bool(os.environ.get("ANTHROPIC_API_KEY"))


def client():
    import anthropic
    return anthropic.Anthropic()


def call(purpose, **kwargs):
    kwargs.setdefault("model", load_settings()["agent"]["llm_model"])
    kwargs.setdefault("max_tokens", 2000)
    kwargs.setdefault("temperature", 0)
    t0 = time.time()
    resp = client().messages.create(**kwargs)
    USAGE.append({"purpose": purpose, "model": kwargs["model"], "input_tokens": resp.usage.input_tokens,
                  "output_tokens": resp.usage.output_tokens, "latency_s": round(time.time() - t0, 2)})
    return resp


def forced_tool(purpose, system, user, tool_name, schema, **kw):
    """Structured output: force a single tool call and return its validated input dict."""
    resp = call(purpose, system=system, messages=[{"role": "user", "content": user}],
                tools=[{"name": tool_name, "description": "Return the structured result.", "input_schema": schema}],
                tool_choice={"type": "tool", "name": tool_name}, **kw)
    for b in resp.content:
        if b.type == "tool_use":
            return b.input
    raise ValueError("no structured output returned")
