"""Blastbox web server. Standard library only, so the Vultr VM image
needs no package install step.

POST /api/run {question, csv, code?}
  - If code is supplied, it is policy-checked and run in the sandbox.
  - If code is omitted, code is generated via Vultr Serverless
    Inference when VULTR_INFERENCE_API_KEY and VULTR_INFERENCE_MODEL
    are set; otherwise the API returns a clear error instead of
    pretending a model ran. A failed first run is retried once with
    the error text fed back into a fresh generation.
GET /api/sample returns a demo CSV and a known-good analysis program.
GET /api/health returns backend and policy status.
"""

import json
import os
import sys
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from app import llm, runner  # noqa: E402

SAMPLE_CSV = "item,price,qty\ncoffee,350,3\ncoffee,350,2\nbeans,1200,1\n"
# Known-good sample program. It passes the policy gate: only the csv
# module, and open() only on the literal 'input.csv' in read mode.
SAMPLE_CODE = (
    "import csv\n"
    "from collections import defaultdict\n"
    "totals = defaultdict(int)\n"
    "with open('input.csv') as fh:\n"
    "    for row in csv.DictReader(fh):\n"
    "        totals[row['item']] += int(row['price']) * int(row['qty'])\n"
    "for item in sorted(totals):\n"
    "    print(f'{item}: {totals[item]}')\n"
)


class Handler(BaseHTTPRequestHandler):
    def log_message(self, *args):  # keep logs quiet; receipts carry evidence
        pass

    def _send(self, status: int, payload: dict):
        data = json.dumps(payload).encode()
        self.send_response(status)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(data)))
        self.end_headers()
        self.wfile.write(data)

    def do_GET(self):
        if self.path == "/api/health":
            self._send(200, {"status": "ok",
                             "backend": os.environ.get("SANDBOX_BACKEND", "local"),
                             "llm_configured": bool(os.environ.get("VULTR_INFERENCE_API_KEY"))})
        elif self.path == "/api/sample":
            self._send(200, {"csv": SAMPLE_CSV, "code": SAMPLE_CODE,
                             "note": "Sample program, not model output. Run it to see real sandboxed output: coffee 1750, beans 1200."})
        elif self.path in ("/", "/index.html"):
            page = Path(__file__).resolve().parent.parent / "static" / "index.html"
            data = page.read_bytes()
            self.send_response(200)
            self.send_header("Content-Type", "text/html")
            self.send_header("Content-Length", str(len(data)))
            self.end_headers()
            self.wfile.write(data)
        else:
            self._send(404, {"error": "not found"})

    def do_POST(self):
        if self.path != "/api/run":
            self._send(404, {"error": "not found"})
            return
        length = int(self.headers.get("Content-Length", 0))
        try:
            body = json.loads(self.rfile.read(length).decode())
        except Exception:
            self._send(400, {"error": "invalid JSON"})
            return
        question = str(body.get("question", ""))
        csv_text = str(body.get("csv", ""))
        code = str(body.get("code", "") or "")
        backend = os.environ.get("SANDBOX_BACKEND", "local")
        if not csv_text.strip():
            self._send(400, {"error": "csv is required"})
            return
        generated = False
        if not code:
            try:
                code = llm.generate_code(question, csv_text)
                generated = True
            except RuntimeError as exc:
                self._send(400, {"error": str(exc)})
                return
            except Exception as exc:
                self._send(502, {"error": f"inference call failed: {exc}"})
                return
        result = runner.run(code, csv_text, backend=backend)
        if result["status"] == "error" and generated:
            try:
                retry_code = llm.generate_code(
                    f"{question}\nPrevious code failed with: {result['stderr'][:500]}",
                    csv_text)
                result = runner.run(retry_code, csv_text, backend=backend)
                code = retry_code
            except Exception:
                pass
        self._send(200, {"question": question, "generated_by_llm": generated,
                         "code": code, "result": result})


def main():
    port = int(os.environ.get("PORT", "8000"))
    ThreadingHTTPServer(("0.0.0.0", port), Handler).serve_forever()


if __name__ == "__main__":
    main()
