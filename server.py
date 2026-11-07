from __future__ import annotations
from http import HTTPStatus
from http.server import SimpleHTTPRequestHandler, ThreadingHTTPServer
import json
from pathlib import Path
import threading
from typing import Any
import webbrowser

from c_compiler.pipeline import CompilerPipeline
from c_compiler.presets import PRESETS


STATIC_DIR = Path(__file__).resolve().parent / "static"
_PIPELINE: CompilerPipeline | None = None
_PIPELINE_LOCK = threading.Lock()


def _get_pipeline() -> CompilerPipeline:
    global _PIPELINE
    if _PIPELINE is None:
        _PIPELINE = CompilerPipeline()
    return _PIPELINE


class CompilerRequestHandler(SimpleHTTPRequestHandler):
    def __init__(self, *args: Any, **kwargs: Any) -> None:
        super().__init__(*args, directory=str(STATIC_DIR), **kwargs)

    def log_message(self, format: str, *args: Any) -> None:
        if self.path.startswith("/api/"):
            super().log_message(format, *args)

    def _send_json(self, payload: Any, status: int = HTTPStatus.OK) -> None:
        raw = json.dumps(payload, ensure_ascii=False).encode("utf-8")
        self.send_response(status)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Content-Length", str(len(raw)))
        self.send_header("Cache-Control", "no-store")
        self.end_headers()
        self.wfile.write(raw)

    def do_GET(self) -> None:
        if self.path == "/api/presets":
            self._send_json({"presets": PRESETS})
            return
        if self.path == "/api/health":
            self._send_json({"status": "ok"})
            return
        super().do_GET()

    def do_POST(self) -> None:
        if self.path == "/api/compile":
            try:
                content_len = int(self.headers.get("Content-Length", "0"))
                body = self.rfile.read(content_len).decode("utf-8")
                data = json.loads(body) if body else {}
                source_code = str(data.get("code", ""))
                run_ast = bool(data.get("runAst", True))
                run_python = bool(data.get("runPython", True))

                with _PIPELINE_LOCK:
                    result = _get_pipeline().process(
                        source_code=source_code,
                        run_ast=run_ast,
                        run_python=run_python,
                    )
                self._send_json(result)
            except Exception as exc:
                self._send_json(
                    {"success": False, "error": f"Внутрішня помилка сервера: {exc}"},
                    status=HTTPStatus.INTERNAL_SERVER_ERROR,
                )
            return

        self._send_json({"error": "Невідомий маршрут API"}, status=HTTPStatus.NOT_FOUND)


def start_server(host: str = "127.0.0.1", port: int = 8000, open_browser: bool = True) -> None:
    server_addr = (host, port)
    httpd = ThreadingHTTPServer(server_addr, CompilerRequestHandler)
    url = f"http://{host}:{port}"
    print(f"Сервер запущено: {url}")

    if open_browser:
        threading.Timer(0.5, lambda: webbrowser.open(url)).start()

    try:
        httpd.serve_forever()
    except KeyboardInterrupt:
        print("\nСервер зупинено.")
    finally:
        httpd.server_close()


if __name__ == "__main__":
    start_server()
