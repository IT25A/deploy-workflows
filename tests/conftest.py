from __future__ import annotations

import json
import sys
import threading
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path

import pytest

SCRIPTS = Path(__file__).resolve().parents[1] / "scripts"
sys.path.insert(0, str(SCRIPTS))


class StubDeployer:
    """Minimal stand-in for the deployer API; records requests and replays scripted answers."""

    def __init__(self) -> None:
        self.requests: list[tuple[str, str, dict | None, str]] = []
        self.responses: dict[tuple[str, str], list[tuple[int, dict]]] = {}
        self.server: ThreadingHTTPServer | None = None

    def reply(self, method: str, path: str, *answers: tuple[int, dict]) -> None:
        self.responses[(method, path)] = list(answers)

    @property
    def url(self) -> str:
        return f"http://127.0.0.1:{self.server.server_port}"  # type: ignore[union-attr]

    def start(self) -> None:
        stub = self

        class Handler(BaseHTTPRequestHandler):
            def log_message(self, *args):  # noqa: D401
                pass

            def _handle(self, method: str) -> None:
                length = int(self.headers.get("Content-Length") or 0)
                body = json.loads(self.rfile.read(length)) if length else None
                path = self.path.split("?")[0]
                if path == "/oidc":
                    status, payload = 200, {"value": "oidc-token"}
                else:
                    stub.requests.append((method, self.path, body, self.headers.get("Authorization", "")))
                    queue = stub.responses.get((method, path)) or [(500, {"error": f"unscripted {method} {path}"})]
                    status, payload = queue[0] if len(queue) == 1 else queue.pop(0)
                raw = json.dumps(payload).encode()
                self.send_response(status)
                self.send_header("Content-Type", "application/json")
                self.send_header("Content-Length", str(len(raw)))
                self.end_headers()
                self.wfile.write(raw)

            def do_GET(self):  # noqa: N802
                self._handle("GET")

            def do_POST(self):  # noqa: N802
                self._handle("POST")

        self.server = ThreadingHTTPServer(("127.0.0.1", 0), Handler)
        threading.Thread(target=self.server.serve_forever, daemon=True).start()


@pytest.fixture
def stub(monkeypatch, tmp_path):
    server = StubDeployer()
    server.start()
    monkeypatch.setenv("ACTIONS_ID_TOKEN_REQUEST_URL", server.url + "/oidc?x=1")
    monkeypatch.setenv("ACTIONS_ID_TOKEN_REQUEST_TOKEN", "request-token")
    monkeypatch.setenv("GITHUB_REPOSITORY", "IT25A/Demo")
    monkeypatch.setenv("GITHUB_SHA", "abcdef1234567890" * 2 + "abcdef12")
    monkeypatch.setenv("GITHUB_OUTPUT", str(tmp_path / "output"))
    monkeypatch.setenv("GITHUB_STEP_SUMMARY", str(tmp_path / "summary"))
    monkeypatch.delenv("GITHUB_ACTIONS", raising=False)
    import it25a_ci

    monkeypatch.setattr(it25a_ci, "POLL_INTERVAL", 0.01)
    yield server
    server.server.shutdown()  # type: ignore[union-attr]


def read_outputs(tmp_path: Path) -> dict[str, str]:
    result: dict[str, str] = {}
    path = tmp_path / "output"
    if not path.exists():
        return result
    for line in path.read_text().splitlines():
        key, _, value = line.partition("=")
        result[key] = value
    return result
