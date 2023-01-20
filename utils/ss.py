#!/usr/bin/env python3

import sys
import http.server

msg = "hi"

class SimpleEndpoint(http.server.BaseHTTPRequestHandler):
    def do_GET(self):
        self.send_response(200)
        self.end_headers()
        self.wfile.write(bytes(msg + "\n", "utf-8"))

def main():
    if len(sys.argv) != 2:
        print("Expecting a single argument of string to serve")
        return

    global msg
    msg = sys.argv[1]
    s = http.server.HTTPServer(("0.0.0.0", 8000), SimpleEndpoint)
    s.serve_forever()

main()
