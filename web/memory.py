#!/usr/bin/env python3
"""Memory module VisionPsy: ingatan jangka panjang lokal.

Ringkasan percakapan + fakta tentang pengguna disimpan di memory.json,
dirangkum oleh MODEL LOKAL sendiri (llama-server :8090) - tanpa layanan
eksternal. Blok ingatan diinjeksikan ke system prompt agar model terlihat
pintar dan personal di sesi berikutnya.
"""
import os, re, json, urllib.request
from datetime import datetime

MEM_FILE = os.path.join(os.path.dirname(os.path.abspath(__file__)), "memory.json")
API = os.environ.get("VPSY_URL", "http://127.0.0.1:8090")
MAX_POIN = 6        # jumlah entri ringkasan tersimpan
MAX_FAKTA = 12      # jumlah fakta pengguna tersimpan
MAX_MSG = 20        # pesan terakhir yang dirangkum
CHARS_PER_MSG = 250 # potong tiap pesan biar muat context 4096


def _now():
    return datetime.now().strftime("%d %b %Y %H:%M")


def load():
    try:
        with open(MEM_FILE, encoding="utf-8") as f:
            m = json.load(f)
        return {
            "ringkasan": m.get("ringkasan", ""),
            "fakta": [str(x) for x in m.get("fakta", [])],
            "diperbarui": m.get("diperbarui", ""),
        }
    except Exception:
        return {"ringkasan": "", "fakta": [], "diperbarui": ""}


def save(mem):
    tmp = MEM_FILE + ".tmp"
    with open(tmp, "w", encoding="utf-8") as f:
        json.dump(mem, f, ensure_ascii=False, indent=1)
    os.replace(tmp, MEM_FILE)


def _complete(messages, max_tokens=400):
    body = json.dumps({
        "model": "visionpsy", "messages": messages,
        "max_tokens": max_tokens, "temperature": 0.2, "stream": False,
    }).encode()
    req = urllib.request.Request(
        API + "/v1/chat/completions", data=body,
        headers={"Content-Type": "application/json"})
    with urllib.request.urlopen(req, timeout=300) as r:
        d = json.loads(r.read().decode())
    return d["choices"][0]["message"].get("content") or ""


def transcript(messages):
    """Buat transkrip teks dari riwayat pesan (gambar -> [gambar])."""
    labels = {"user": "User", "assistant": "Asisten",
              "system": "Sistem", "tool": "Hasil tool"}
    lines = []
    for m in messages[-MAX_MSG:]:
        c = m.get("content")
        if isinstance(c, list):
            parts = []
            for i in c:
                if not isinstance(i, dict):
                    continue
                if i.get("type") == "image_url":
                    parts.append("[gambar]")
                elif i.get("text"):
                    parts.append(str(i["text"]))
            c = " ".join(parts)
        if not c:
            tc = m.get("tool_calls")
            if tc:
                c = "[tool: " + ", ".join(t["function"]["name"] for t in tc) + "]"
            else:
                continue
        lines.append((labels.get(m.get("role"), m.get("role")) + ": "
                      + str(c)[:CHARS_PER_MSG]))
    return "\n".join(lines)


def _parse_summary(out):
    """Ambil JSON dari jawaban model, fallback ke teks polos."""
    m = re.search(r"\{.*\}", out, re.S)
    try:
        d = json.loads(m.group(0)) if m else {}
        ring = str(d.get("ringkasan", "")).strip()
        fakta = [str(x).strip() for x in d.get("fakta", []) if str(x).strip()]
        return {"ringkasan": ring, "fakta": fakta}
    except Exception:
        return {"ringkasan": out.strip()[:400], "fakta": []}


def summarize(messages):
    """Minta model lokal merangkum percakapan. None jika transkrip terlalu pendek."""
    t = transcript(messages)
    if len(t) < 40:
        return None
    sys = (
        "Kamu adalah modul ingatan. Dari transkrip percakapan di bawah, buat "
        "ringkasan padat Bahasa Indonesia untuk diingat jangka panjang, DITULIS "
        "langsung sebagai fakta alami, contoh: 'Pengguna bernama Budi, suka "
        "fotografi, berencana ke Bromo minggu depan'. Sebutkan nama pengguna "
        "jika ada. Sertakan topik yang dibahas, keputusan/kesimpulan, hal yang "
        "sedang dikerjakan, tugas yang diminta, dan preferensi pengguna. "
        "Ekstrak juga FAKTA tersendiri tentang pengguna (nama, kesukaan, info "
        "pribadi yang dia ceritakan). "
        'JAWAB HANYA JSON: {"ringkasan": "2-4 kalimat", '
        '"fakta": ["3-6 fakta singkat"]}. Jika tidak ada fakta, isi "fakta": []. '
        "Jangan keluarkan teks lain di luar JSON.")
    out = _complete([{"role": "system", "content": sys},
                     {"role": "user", "content": "TRANSKRIP:\n" + t}],
                    max_tokens=400)
    return _parse_summary(out)


def add_episode(messages):
    """Rangkum percakapan lalu simpan ke memori. Mengembalikan memori baru."""
    s = summarize(messages)
    if not s:
        return None
    mem = load()
    now = _now()
    if s["ringkasan"]:
        pts = [p.strip() for p in mem["ringkasan"].split("\n· ") if p.strip()]
        pts.append("· " + now + ": " + s["ringkasan"])
        mem["ringkasan"] = "\n".join(pts[-MAX_POIN:])
    known = {f.lower() for f in mem["fakta"]}
    for f in s["fakta"]:
        if f.lower() not in known:
            mem["fakta"].append(f)
            known.add(f.lower())
    mem["fakta"] = mem["fakta"][-MAX_FAKTA:]
    mem["diperbarui"] = now
    save(mem)
    return mem


def mem_block(mem=None):
    """Blok teks siap-ditempel ke system prompt. Kosong jika belum ada memori."""
    mem = mem or load()
    parts = []
    if mem["ringkasan"]:
        parts.append("Kenangan percakapan sebelumnya:\n" + mem["ringkasan"])
    if mem["fakta"]:
        parts.append("Fakta tentang pengguna (dipakai agar jawaban personal):\n"
                     + "\n".join("- " + f for f in mem["fakta"]))
    if not parts:
        return ""
    head = "Tentang pengguna ini kamu TAHU dari percakapan sebelumnya" + \
           (" (terakhir " + mem["diperbarui"] + ")" if mem["diperbarui"] else "")
    return "[INGATAN] " + head + ":\n" + "\n\n".join(parts) + " [AKHIR INGATAN]"


def inject(base, mem=None):
    """base system prompt + blok ingatan."""
    blk = mem_block(mem)
    return base + "\n\n" + blk if blk else base