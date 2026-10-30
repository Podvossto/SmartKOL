"""A throwaway local web server, so browser-facing code is tested against real HTTP and a real Chromium."""
import threading
from contextlib import contextmanager
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer


class _Handler(BaseHTTPRequestHandler):
    def do_GET(self):
        entry = self.server.routes.get(self.path.split("?")[0])
        status, headers, body = (404, {}, "not found") if entry is None else (
            (200, {}, entry) if isinstance(entry, str) else entry)
        self.send_response(status)
        for key, value in {"Content-Type": "text/html; charset=utf-8", **headers}.items():
            self.send_header(key, value)
        self.end_headers()
        self.wfile.write(body.encode("utf-8"))

    def log_message(self, *args):  # keep test output clean
        pass


@contextmanager
def serve(routes: dict):
    """routes: path -> html string, or (status, headers, body)."""
    server = ThreadingHTTPServer(("127.0.0.1", 0), _Handler)
    server.routes = routes
    threading.Thread(target=server.serve_forever, daemon=True).start()
    try:
        yield f"http://127.0.0.1:{server.server_address[1]}"
    finally:
        server.shutdown()
        server.server_close()
