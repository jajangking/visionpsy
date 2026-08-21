#!/usr/bin/env python3
# VisionPsy CLI - talks to llama-server over HTTP (server kept alive by launcher).
import sys, os, re, base64, json, socket, urllib.request, urllib.error, signal
from pathlib import Path

URL = "http://127.0.0.1:8090/v1/chat/completions"

E = chr(27)
R, B, D, CY, GR, YE, RD, MG, WH = (E + s for s in
    ["[0m", "[1m", "[2m", "[36m", "[32m", "[33m", "[31m", "[35m", "[97m"])

HELP = B + "Perintah:" + R + """
  """ + GR + "/img <file>" + R + """     lampirkan gambar ke pesan berikutnya
  """ + GR + "/sys <txt>" + R + """      set system prompt ("/sys off" = hapus)
  """ + GR + "/clr" + R + """            bersihkan riwayat
  """ + GR + "/t <n>" + R + """          batas token jawaban (default 128)
  """ + GR + "/help" + R + """           bantuan ini
  """ + GR + "/quit" + R + """           keluar (server tetap jalan)
"""


def complete(messages, max_tokens=128, temp=0.5):
    body = json.dumps({"messages": messages, "max_tokens": max_tokens,
                       "temperature": temp, "stream": False}).encode()
    req = urllib.request.Request(URL, data=body, headers={"Content-Type": "application/json"})
    try:
        with urllib.request.urlopen(req, timeout=600) as resp:
            data = json.loads(resp.read().decode())
        return data["choices"][0]["message"]["content"], None
    except Exception as ex:
        return None, str(ex)


def img_part(path):
    mime = "image/jpeg"
    if path.lower().endswith(".png"):
        mime = "image/png"
    elif path.lower().endswith(".webp"):
        mime = "image/webp"
    b64 = base64.b64encode(open(path, "rb").read()).decode()
    return {"type": "image_url", "image_url": {"url": "data:%s;base64,%s" % (mime, b64)}}


def session(msgs):
    print(GR + "bot: " + R + (msgs or "(kosong)").strip())


def ask(img, q, max_tokens=256):
    content = [{"type": "text", "text": q}, img_part(img)]
    res, err = complete([{"role": "user", "content": content}], max_tokens=max_tokens)
    if err:
        print(RD + "error: " + err + R)
    else:
        session(res)


def chat():
    messages, system, max_tokens, pending = [], None, 128, None
    print(D + "Chat. /help untuk bantuan. /quit keluar (server tetap nyala)." + R)
    while True:
        try:
            tag = MG + "[img]" + R if pending else ""
            line = input(CY + "kamu" + tag + ": " + R).strip()
        except (EOFError, KeyboardInterrupt):
            print()
            return
        if not line:
            continue
        if line.startswith("/"):
            p = line[1:].split(maxsplit=1)
            c, a = p[0].lower(), (p[1] if len(p) > 1 else "").strip()
            if c in ("quit", "q", "exit"):
                return
            elif c in ("help", "h"):
                print(HELP)
            elif c == "clr":
                messages, pending = [], None
                print(D + "riwayat dibersihkan" + R)
            elif c == "sys":
                system = None if (not a or a.lower() == "off") else a
                print(D + ("system prompt: " + system if system else "system prompt dihapus") + R)
            elif c in ("img", "image"):
                p2 = os.path.expanduser(a)
                if os.path.exists(p2):
                    pending = p2
                    print(D + "gambar dilampirkan: " + os.path.basename(p2) + R)
                else:
                    print(RD + "tidak ada: " + p2 + R)
            elif c == "t":
                try:
                    max_tokens = int(a)
                    print(D + "max_tokens = " + str(max_tokens) + R)
                except ValueError:
                    print(YE + "pemakaian: /t <angka>" + R)
            else:
                print(YE + "tidak dikenal: /" + c + R)
            continue

        content = [{"type": "text", "text": line}]
        if pending:
            content.append(img_part(pending))
            pending = None
        full = []
        if system:
            full.append({"role": "system", "content": system})
        full += messages + [{"role": "user", "content": content}]
        print(D + "..." + R, end="", flush=True)
        res, err = complete(full, max_tokens=max_tokens)
        print()
        if err:
            print(RD + "error: " + err + R)
            continue
        messages.append({"role": "user", "content": content})
        messages.append({"role": "assistant", "content": res})
        session(res)


if __name__ == "__main__":
    signal.signal(signal.SIGINT, lambda *_: print())
    argv = sys.argv[1:]
    if argv and argv[0] == "img":
        ask(argv[1], "Describe this image in detail.")
    elif argv and argv[0] == "ask" and len(argv) >= 3:
        ask(argv[1], " ".join(argv[2:]))
    else:
        chat()