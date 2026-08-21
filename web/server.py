#!/usr/bin/env python3
import json, sys, urllib.parse, http.server, os, socketserver
import memory

WEB_DIR = os.path.dirname(os.path.abspath(__file__))

class H(http.server.BaseHTTPRequestHandler):
    def log_message(self, *a):
        pass

    def json_out(self, data, code=200):
        body = json.dumps(data, ensure_ascii=False).encode()
        self.send_response(code)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Access-Control-Allow-Origin", "*")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def do_POST(self):
        if self.path.startswith("/memory"):
            return self.do_memory()
        self.send_error(405)

    def do_memory(self):
        try:
            if self.path.startswith("/memory/summarize"):
                ln = int(self.headers.get("Content-Length") or 0)
                data = json.loads(self.rfile.read(ln).decode() or "{}")
                mem = memory.add_episode(data.get("messages") or [])
                if mem:
                    return self.json_out({"ok": True, "block": memory.mem_block(mem)})
                return self.json_out({"ok": False, "reason": "percakapan terlalu pendek"}, 400)
            return self.json_out({"ok": True, "block": memory.mem_block()})
        except Exception as e:
            return self.json_out({"ok": False, "error": str(e)}, 500)
    def log_message(self, *a):
        pass
    def do_GET(self):
        if self.path.startswith("/model"):
            try:
                with open(os.path.expanduser("~/visionpsy/models/current.txt")) as f:
                    cur = f.read().strip()
            except Exception:
                cur = "?"
            return self.json_out({"model": cur})
        if self.path.startswith("/memory"):
            return self.do_memory()
        p = urllib.parse.unquote(self.path.split("?")[0])
        if p == "/": p = "/index.html"
        fp = os.path.normpath(os.path.join(WEB_DIR, p.lstrip("/")))
        if not fp.startswith(WEB_DIR): self.send_error(403); return
        if os.path.isfile(fp):
            ctype = ("text/html" if fp.endswith((".html", ".htm")) else
                     "text/css" if fp.endswith(".css") else
                     "application/javascript" if fp.endswith(".js") else
                     "image/x-icon" if fp.endswith(".ico") else "application/octet-stream")
            with open(fp, "rb") as f: body = f.read()
            self.send_response(200)
            self.send_header("Content-Type", ctype)
            self.send_header("Content-Length", str(len(body)))
            self.end_headers()
            self.wfile.write(body)
        else:
            self.send_error(404)

if __name__ == "__main__":
    port = int(sys.argv[1]) if len(sys.argv) > 1 else 8091
    httpd = socketserver.ThreadingTCPServer(("0.0.0.0", port), H)
    httpd.daemon_threads = True
    print("web server on :%d" % port)
    httpd.serve_forever()