"""Vultr Serverless Inference client (OpenAI-compatible).

Endpoint: https://api.vultrinference.com/v1 (from the event brief).
Model and API key come from the environment (VULTR_INFERENCE_MODEL,
VULTR_INFERENCE_API_KEY). No default model is claimed: the key and
model are deployment configuration, supplied on the Vultr VM, and the
key is never written to disk, logs, or the sandbox.

Code generation contract: the model must return Python that reads
input.csv from the current directory with the csv module and prints
its answer to stdout. Anything else is still passed through the
policy gate and the sandbox, so a non-conforming answer cannot
escape containment; it can only fail.
"""

import json
import os
import urllib.request

BASE_URL = "https://api.vultrinference.com/v1"


def build_prompt(question: str, csv_text: str) -> str:
    header = csv_text.splitlines()[0] if csv_text.strip() else ""
    return (
        "Write a short Python program that answers this question about a CSV file.\n"
        "Rules: read input.csv from the current directory using only the csv, json, "
        "math, statistics, collections, re, or datetime modules. Print only the answer. "
        "Do not import anything else. open() is allowed only as open('input.csv') in read mode.\n"
        f"CSV header: {header}\n"
        f"Question: {question}\n"
        "Return only the Python code, no markdown fences, no explanation."
    )


def parse_completion(payload: dict) -> str:
    return payload["choices"][0]["message"]["content"].strip()


def generate_code(question: str, csv_text: str, base_url: str = BASE_URL) -> str:
    api_key = os.environ.get("VULTR_INFERENCE_API_KEY", "")
    model = os.environ.get("VULTR_INFERENCE_MODEL", "")
    if not api_key or not model:
        raise RuntimeError("VULTR_INFERENCE_API_KEY and VULTR_INFERENCE_MODEL are not set")
    body = json.dumps({
        "model": model,
        "messages": [{"role": "user", "content": build_prompt(question, csv_text)}],
        "temperature": 0,
    }).encode()
    req = urllib.request.Request(
        f"{base_url}/chat/completions", data=body,
        headers={"Authorization": f"Bearer {api_key}", "Content-Type": "application/json"},
        method="POST",
    )
    with urllib.request.urlopen(req, timeout=60) as resp:
        return parse_completion(json.loads(resp.read().decode()))
