"""Run with: python app.py --serve  (or --json for a CLI result)."""

import argparse
import json
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path

from model import calculate
from scenario_analysis import analyze

ROOT = Path(__file__).resolve().parent


class Handler(BaseHTTPRequestHandler):
    def send_json(self, status, payload):
        data = json.dumps(payload, allow_nan=False).encode("utf-8")
        self.send_response(status)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Content-Length", str(len(data)))
        self.end_headers()
        self.wfile.write(data)

    def do_GET(self):
        files = {"/": ("index.html", "text/html"), "/style.css": ("style.css", "text/css"), "/dashboard.js": ("dashboard.js", "text/javascript")}
        if self.path == "/api/defaults":
            return self.send_json(200, calculate())
        if self.path not in files:
            return self.send_json(404, {"error": "Not found"})
        filename, content_type = files[self.path]
        data = (ROOT / filename).read_bytes()
        self.send_response(200)
        self.send_header("Content-Type", content_type + "; charset=utf-8")
        self.send_header("Content-Length", str(len(data)))
        self.end_headers()
        self.wfile.write(data)

    def do_POST(self):
        if self.path not in {"/api/calculate", "/api/scenario-analysis"}:
            return self.send_json(404, {"error": "Not found"})
        try:
            size = int(self.headers.get("Content-Length", "0"))
            if size < 1 or size > 100_000:
                raise ValueError("Request size must be between 1 and 100000 bytes")
            updates = json.loads(self.rfile.read(size))
            result = analyze(updates) if self.path == "/api/scenario-analysis" else calculate(updates)
            return self.send_json(200, result)
        except (ValueError, json.JSONDecodeError) as exc:
            return self.send_json(400, {"error": str(exc)})


def main():
    parser = argparse.ArgumentParser(description="Basecamp cloud repatriation cost model")
    mode = parser.add_mutually_exclusive_group(required=True)
    mode.add_argument("--serve", action="store_true", help="Open local dashboard API")
    mode.add_argument("--json", action="store_true", help="Print calculation as JSON")
    parser.add_argument("--inputs", type=Path, help="JSON file containing input overrides")
    parser.add_argument("--port", type=int, default=8000)
    args = parser.parse_args()
    if args.json:
        updates = json.loads(args.inputs.read_text(encoding="utf-8")) if args.inputs else {}
        print(json.dumps(calculate(updates), indent=2))
    else:
        print(f"Dashboard: http://127.0.0.1:{args.port}", flush=True)
        ThreadingHTTPServer(("127.0.0.1", args.port), Handler).serve_forever()


if __name__ == "__main__":
    main()
