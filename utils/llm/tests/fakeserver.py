"""A scripted OpenAI-compatible server for offline tests of the agent model layer.

Each POST to ``/v1/chat/completions`` pops the next scripted response. A
response is either a dict (sent as one JSON body) or a list of chunk dicts (sent
as a server-sent-event stream). Requests are recorded for assertions.
"""

from __future__ import annotations

import json
import threading
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from typing import Any


class FakeServer:
    def __init__(self, script: list[Any]) -> None:
        self.script = list(script)
        self.requests: list[dict[str, Any]] = []
        outer = self

        class Handler(BaseHTTPRequestHandler):
            def log_message(self, *args: Any) -> None:  # silence
                pass

            def do_POST(self) -> None:  # noqa: N802
                n = int(self.headers.get("Content-Length") or 0)
                body = json.loads(self.rfile.read(n) or b"{}")
                outer.requests.append(body)
                item = outer.script.pop(0) if outer.script else {"choices": []}
                if isinstance(item, tuple) and item[0] == "status":
                    self.send_response(item[1])
                    self.end_headers()
                    self.wfile.write(b'{"error": "scripted"}')
                    return
                if isinstance(item, list):
                    self.send_response(200)
                    self.send_header("Content-Type", "text/event-stream")
                    self.end_headers()
                    try:
                        for chunk in item:
                            self.wfile.write(f"data: {json.dumps(chunk, ensure_ascii=False)}\n\n".encode())
                            self.wfile.flush()
                        self.wfile.write(b"data: [DONE]\n\n")
                    except (BrokenPipeError, ConnectionResetError):
                        pass  # the client closed the stream (runaway cut)
                    return
                data = json.dumps(item).encode()
                self.send_response(200)
                self.send_header("Content-Type", "application/json")
                self.send_header("Content-Length", str(len(data)))
                self.end_headers()
                self.wfile.write(data)

        self.httpd = ThreadingHTTPServer(("127.0.0.1", 0), Handler)
        self.thread = threading.Thread(target=self.httpd.serve_forever, daemon=True)

    @property
    def base_url(self) -> str:
        return f"http://127.0.0.1:{self.httpd.server_address[1]}/v1"

    def __enter__(self) -> "FakeServer":
        self.thread.start()
        return self

    def __exit__(self, *exc: Any) -> None:
        self.httpd.shutdown()
        self.httpd.server_close()


def body(content: str | None = "", *, tool_calls: list[dict] | None = None, finish: str = "stop",
         reasoning: str | None = None, token_ids: list[int] | None = None, model: str = "fake",
         completion_tokens: int = 10) -> dict[str, Any]:
    """A non-streamed completion body."""
    msg: dict[str, Any] = {"role": "assistant", "content": content}
    if tool_calls:
        msg["tool_calls"] = tool_calls
    if reasoning:
        msg["reasoning"] = reasoning
    choice: dict[str, Any] = {"index": 0, "message": msg, "finish_reason": finish}
    if token_ids is not None:
        choice["token_ids"] = token_ids
    return {"model": model, "choices": [choice],
            "usage": {"prompt_tokens": 5, "completion_tokens": completion_tokens,
                      "total_tokens": 5 + completion_tokens}}


def stream(*pieces: dict[str, Any], finish: str = "stop", model: str = "fake") -> list[dict[str, Any]]:
    """A streamed completion: one chunk per delta, then a finish chunk and usage."""
    chunks = [{"model": model, "choices": [{"index": 0, "delta": p}]} for p in pieces]
    chunks.append({"model": model, "choices": [{"index": 0, "delta": {}, "finish_reason": finish}]})
    chunks.append({"model": model, "choices": [], "usage": {"prompt_tokens": 5, "completion_tokens": 7}})
    return chunks


def native_call(name: str, arguments: str, cid: str = "call_1") -> dict[str, Any]:
    return {"id": cid, "type": "function", "function": {"name": name, "arguments": arguments}}
