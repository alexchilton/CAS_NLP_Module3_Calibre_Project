#!/usr/bin/env python3
"""Drive the Calibre MCP server from any Ollama model, and compare models.

Ollama supports tool calling but is not an MCP client, so this sits between
the two: it starts the MCP server over stdio, converts its tools to Ollama's
schema, runs the agent loop, and reports what each model actually did.

    # one model, see every tool call
    python -u mcp_ollama_compare.py --model qwen3-coder:30b-100k \
        --prompt "How many books are in the library?"

    # same prompt across models, summary table
    python -u mcp_ollama_compare.py --compare qwen3-coder:30b-100k,qwen3.8:27b-q4_K_M \
        --prompt "Find duplicate books by Tolkien"
"""

import argparse
import asyncio
import json
import os
import time

import httpx
from fastmcp import Client
from fastmcp.client.transports import StdioTransport

REPO = os.path.dirname(os.path.abspath(__file__))
OLLAMA = os.environ.get("OLLAMA_HOST", "http://127.0.0.1:11434")
LIBRARY = os.environ.get("CALIBRE_LIBRARY_PATH", "/Users/alexchilton/Calibre Library")

SYSTEM = (
    "You are a librarian with tools over a Calibre library. "
    "Use a tool when one can answer the question. "
    "Answer from tool results only, never from memory."
)


def mcp_transport():
    env = dict(os.environ)
    env.update({
        "CALIBRE_LIBRARY_PATH": LIBRARY,
        "PYTHONPATH": REPO,
        "PATH": "/Applications/calibre.app/Contents/MacOS:" + env.get("PATH", ""),
    })
    return StdioTransport(
        command=os.path.join(REPO, "venv", "bin", "python"),
        args=["-m", "calibre_mcp.app"],
        env=env,
        cwd=REPO,
    )


def as_ollama_tools(mcp_tools, only=None):
    """Convert MCP tool definitions to Ollama's function-calling schema."""
    out = []
    for t in mcp_tools:
        if only and t.name not in only:
            continue
        out.append({
            "type": "function",
            "function": {
                "name": t.name,
                "description": (t.description or "").strip()[:400],
                # MCP SDK v2 renamed inputSchema; keep both so either version works.
                "parameters": (getattr(t, "input_schema", None)
                               or {"type": "object", "properties": {}}),
            },
        })
    return out


def text_of(result):
    parts = [getattr(b, "text", "") for b in (result.content or [])]
    return "\n".join(p for p in parts if p)


async def run(model, prompt, tools, client, max_rounds, verbose):
    """Run one model to completion. Returns a record of what it did."""
    messages = [{"role": "system", "content": SYSTEM}, {"role": "user", "content": prompt}]
    calls, errors = [], 0
    started = time.time()

    async with httpx.AsyncClient(timeout=600) as http:
        for _ in range(max_rounds):
            resp = await http.post(
                f"{OLLAMA}/api/chat",
                json={"model": model, "messages": messages, "tools": tools, "stream": False},
            )
            resp.raise_for_status()
            msg = resp.json().get("message", {})
            messages.append(msg)

            tool_calls = msg.get("tool_calls") or []
            if not tool_calls:
                return {
                    "model": model,
                    "answer": (msg.get("content") or "").strip(),
                    "calls": calls,
                    "errors": errors,
                    "seconds": time.time() - started,
                }

            for tc in tool_calls:
                fn = tc.get("function", {})
                name = fn.get("name", "")
                args = fn.get("arguments") or {}
                if isinstance(args, str):
                    try:
                        args = json.loads(args)
                    except json.JSONDecodeError:
                        args = {}
                calls.append(name)
                if verbose:
                    print(f"  -> {name}({json.dumps(args)[:120]})", flush=True)
                try:
                    result = await client.call_tool(name, args)
                    content = text_of(result)[:4000]
                except Exception as exc:
                    errors += 1
                    content = f"ERROR: {exc}"
                if verbose:
                    print(f"     {content[:160].replace(chr(10), ' ')}", flush=True)
                messages.append({"role": "tool", "name": name,
                                 "tool_name": name, "content": content})

    return {"model": model, "answer": "(hit max rounds)", "calls": calls,
            "errors": errors, "seconds": time.time() - started}


async def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--model", help="a single Ollama model to run")
    ap.add_argument("--compare", help="comma-separated models to run on the same prompt")
    ap.add_argument("--prompt", required=True)
    ap.add_argument("--tools", help="comma-separated tool names, to narrow the tool list")
    ap.add_argument("--max-rounds", type=int, default=8)
    args = ap.parse_args()

    models = [m.strip() for m in args.compare.split(",")] if args.compare else [args.model]
    if not models or not models[0]:
        ap.error("give --model or --compare")

    only = set(args.tools.split(",")) if args.tools else None

    async with Client(mcp_transport()) as client:
        mcp_tools = await client.list_tools()
        tools = as_ollama_tools(mcp_tools, only)
        print(f"{len(tools)} tools exposed to the model\n", flush=True)

        results = []
        for model in models:
            print(f"=== {model}", flush=True)
            try:
                r = await run(model, args.prompt, tools, client, args.max_rounds, verbose=True)
            except Exception as exc:
                r = {"model": model, "answer": f"FAILED: {exc}", "calls": [],
                     "errors": 1, "seconds": 0.0}
            results.append(r)
            print(f"  answer: {r['answer'][:400]}\n", flush=True)

    print(f"{'model':<42} {'calls':>5} {'errors':>6} {'secs':>7}  tools used")
    for r in results:
        used = ", ".join(dict.fromkeys(r["calls"])) or "-"
        print(f"{r['model']:<42} {len(r['calls']):>5} {r['errors']:>6} "
              f"{r['seconds']:>7.1f}  {used[:60]}")


if __name__ == "__main__":
    asyncio.run(main())