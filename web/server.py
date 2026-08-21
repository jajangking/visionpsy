#!/usr/bin/env python3
import json, re, html, sys, urllib.request, urllib.parse, http.server, os, socketserver
import memory

WEB_DIR = os.path.dirname(os.path.abspath(__file__))
UA = ("Mozilla/5.0 (Linux; Android 15; TECNO-LJ8k) AppleWebKit/537.36 "
      "(KHTML, like Gecko) Chrome/130.0 Mobile Safari/537.36")

def fetch(url, timeout=12):
    req = urllib.request.Request(url, headers={
        "User-Agent": UA, "Accept": "*/*",
        "Accept-Language": "id-ID,id;q=0.9,en;q=0.8"})
    with urllib.request.urlopen(req, timeout=timeout) as r:
        return r.read().decode("utf-8", "replace")

def google(q):
    url = "https://www.google.com/search?num=6&hl=id&q=" + urllib.parse.quote(q)
    try:
        body = fetch(url)
    except Exception:
        return []
    titles = re.findall(r"<h3[^>]*>(.*?)</h3>", body, re.S)
    titles = [html.unescape(re.sub("<.*?>", "", t)).strip() for t in titles]
    snippets = re.findall(r'<div class="[^"]*(?:VwiC3b|aCOpRe|BNeawe)[^"]*"[^>]*>(.*?)</div>', body, re.S)
    snippets = [html.unescape(re.sub("<.*?>", "", s)).strip() for s in snippets]
    urls = [u for u in re.findall(r'href="/url\?q=(http[^&"]+)', body)]
    out = []
    for i, t in enumerate(titles[:6]):
        if not t: continue
        u = urls[i] if i < len(urls) else ""
        s = snippets[i] if i < len(snippets) else ""
        out.append((t, u, s))
    return out

def ddg_html(q):
    url = "https://html.duckduckgo.com/html/?q=" + urllib.parse.quote(q)
    try:
        body = fetch(url)
    except Exception:
        return []
    out = []
    for m in re.finditer(
            r'class="result__a"[^>]*>(.*?)</a>(?s:.*?)class="result__snippet"[^>]*>(.*?)</a>',
            body):
        t = html.unescape(re.sub("<.*?>", "", m.group(1))).strip()
        s = html.unescape(re.sub("<.*?>", "", m.group(2))).strip()
        if t: out.append((t, "", s))
    if not out:
        for m in re.finditer(r'class="result__a"[^>]*>(.*?)</a>', body):
            t = html.unescape(re.sub("<.*?>", "", m.group(1))).strip()
            if t: out.append((t, "", ""))
    return out[:5]

def wiki_summary(q):
    try:
        d = json.loads(fetch("https://id.wikipedia.org/w/api.php?action=opensearch"
                             "&search=" + urllib.parse.quote(q) + "&limit=1&format=json&origin=*"))
        ttl = d[1][0] if d[1] else None
        if not ttl: return None
        s = json.loads(fetch("https://id.wikipedia.org/api/rest_v1/page/summary/"
                             + urllib.parse.quote(ttl)))
        return (ttl, s.get("extract", ""))
    except Exception:
        return None

IDN_Q = "Q252"
def wikidata_leader(line_text):
    try:
        d = json.loads(fetch("https://www.wikidata.org/wiki/Special:EntityData/" + IDN_Q + ".json"))
        ent = d["entities"][IDN_Q]
        out = []
        for prop, label in (("P35", "Kepala negara Indonesia (presiden)"),
                            ("P6", "Kepala pemerintahan Indonesia")):
            claims = ent["claims"].get(prop)
            if not claims: continue
            vid = claims[-1]["mainsnak"].get("datavalue", {}).get("value", {}).get("id")
            if not vid: continue
            try:
                e = json.loads(fetch("https://www.wikidata.org/wiki/Special:EntityData/" + vid + ".json"))
                name = e["entities"][vid]["labels"].get("id", {}).get("value") or \
                       e["entities"][vid]["labels"].get("en", {}).get("value", "?")
                out.append(label + ": " + name)
            except Exception:
                pass
        if out: return line_text + "\n" + "\n".join(out)
    except Exception:
        pass
    return None

def do_search(q):
    out = {"query": q, "hasil": "", "sumber": []}
    ql = q.lower()
    if any(k in ql for k in ("presiden indonesia", "presiden ri", "wapres indonesia", "wakil presiden indonesia")):
        w = wikidata_leader("DATA TERCATAT (dari Wikidata, terbaru):")
        if w:
            out["sumber"].append("wikidata")
            out["hasil"] += w
    items = google(q)
    if items:
        out["sumber"].append("google")
        out["hasil"] += (("\n\n" if out["hasil"] else "") + "HASIL GOOGLE:\n" +
                         "\n".join("* " + (t + " :: " + s if s else t)[:240] for t, u, s in items))
    if not items:
        items = ddg_html(q)
        if items:
            out["sumber"].append("duckduckgo")
            out["hasil"] += (("\n\n" if out["hasil"] else "") + "HASIL WEB:\n" +
                             "\n".join("* " + (t + " :: " + s if s else t)[:240] for t, u, s in items))
    w = wiki_summary(q)
    if w and w[1]:
        out["sumber"].append("wikipedia id")
        out["hasil"] += (("\n\n" if out["hasil"] else "") +
                         'WIKIPEDIA id "' + w[0] + '": ' + w[1][:700])
    out["instruksi"] = ('Berikut SATU-SATUNYA data yang boleh dipakai. Jawab HANYA dari isi "hasil". '
                        'Jika tidak ada yang menyebut jawabannya, katakan datanya tidak ditemukan. '
                        'JANGAN menebak atau memakai ingatan.')
    if not out["hasil"]:
        out["hasil"] = "(tidak ada hasil dari google/ddg/wikipedia)"
    return out

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
        if self.path.startswith("/search"):
            try:
                q = urllib.parse.parse_qs(urllib.parse.urlsplit(self.path).query).get("q", [""])[0]
                data = json.dumps(do_search(q), ensure_ascii=False).encode()
            except Exception as e:
                data = json.dumps({"query": "", "hasil": "", "error": str(e)},
                                  ensure_ascii=False).encode()
            self.send_response(200)
            self.send_header("Content-Type", "application/json; charset=utf-8")
            self.send_header("Access-Control-Allow-Origin", "*")
            self.send_header("Content-Length", str(len(data)))
            self.end_headers()
            self.wfile.write(data)
            return
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
    print("web server + search proxy on :%d" % port)
    httpd.serve_forever()