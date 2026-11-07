"""A synthetic accepted-looking video reply must not trigger a paid retry."""

import json
import os
from http.server import BaseHTTPRequestHandler, HTTPServer
from pathlib import Path
import subprocess
import sys
from threading import Thread
import unittest


SCRIPT = Path(__file__).resolve().parent.parent / "examples" / "video_python.py"


class VideoExampleTests(unittest.TestCase):
    def test_missing_task_id_keeps_response_private_and_submits_once(self):
        requests = []

        class Handler(BaseHTTPRequestHandler):
            def do_POST(self):
                requests.append(self.path)
                body = json.dumps({"data": {"status": "IN_PROGRESS",
                                            "private_detail": "synthetic-private-marker"}}).encode()
                self.send_response(200)
                self.send_header("Content-Type", "application/json")
                self.send_header("Content-Length", str(len(body)))
                self.end_headers()
                self.wfile.write(body)

            def log_message(self, *args):
                pass

        server = HTTPServer(("127.0.0.1", 0), Handler)
        thread = Thread(target=server.serve_forever, daemon=True)
        thread.start()
        try:
            env = dict(os.environ, AIWAVE_API_KEY="synthetic-only",
                       AIWAVE_BASE_URL=f"http://127.0.0.1:{server.server_port}/v1")
            result = subprocess.run([sys.executable, str(SCRIPT), "synthetic prompt"],
                                    env=env, capture_output=True, text=True, timeout=10)
        finally:
            server.shutdown()
            server.server_close()
            thread.join(timeout=5)
        self.assertNotEqual(result.returncode, 0)
        self.assertEqual(requests, ["/v1/video/generations"])
        self.assertIn("Check task history and usage", result.stderr)
        self.assertNotIn("synthetic-private-marker", result.stdout + result.stderr)


if __name__ == "__main__":
    unittest.main()
