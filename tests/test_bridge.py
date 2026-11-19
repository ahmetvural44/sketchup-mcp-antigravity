import json
from socketserver import StreamRequestHandler, TCPServer
from threading import Thread
from unittest import TestCase

from sketchup_mcp.server import SketchupConnection


class OneRequestHandler(StreamRequestHandler):
    """Match the SketchUp bridge's single request per TCP connection."""
    def handle(self):
        request = json.loads(self.rfile.readline())
        self.server.methods.append(request["method"])
        request_id = request["id"]
        reply = {"id": request_id, "result": {"sequence": request_id}}
        self.wfile.write(json.dumps(reply).encode() + b"\n")


class BridgeTests(TestCase):
    def test_consecutive_tool_calls_return_their_own_replies(self):
        with TCPServer(("127.0.0.1", 0), OneRequestHandler) as host:
            host.methods = []
            worker = Thread(target=host.serve_forever, daemon=True)
            worker.start()
            try:
                bridge = SketchupConnection(*host.server_address)
                for seq in (1, 2):
                    result = bridge.send_command("tools/call", {"name": "get_selection", "arguments": {}}, seq)
                    self.assertEqual(result["sequence"], seq)
                self.assertEqual(host.methods, ["tools/call", "tools/call"])
            finally:
                host.shutdown()
                worker.join()
