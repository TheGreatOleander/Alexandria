# HTTP bridge for Android Tasker

from http.server import BaseHTTPRequestHandler, HTTPServer
import json
from alexandria.hypothesis import Hypothesis
from generators.interface import GeneratorAdapter

class TaskerBridgeAdapter(GeneratorAdapter):

    def propose(self):

        class Handler(BaseHTTPRequestHandler):
            def do_POST(self):
                length = int(self.headers['Content-Length'])
                body = self.rfile.read(length)
                self.server.data = json.loads(body)
                self.send_response(200)
                self.end_headers()

        server = HTTPServer(("0.0.0.0", 8080), Handler)
        server.handle_request()

        return Hypothesis(**server.data)